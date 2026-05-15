import { NextRequest, NextResponse } from "next/server";

import { pool } from "@/lib/db";

export const runtime = "nodejs";

const SIGNAL_SOURCES: Record<string, string[]> = {
  construction: ["dob_permits"],
  nightlife: ["liquor", "nyc_311", "restaurants"],
  housing: ["hpd_complaints", "hpd_violations", "nyc_311"],
  restaurants: ["restaurants", "liquor", "dob_permits"],
  quality_of_life: ["nyc_311"],
};

function error(detail: string, status = 400) {
  return NextResponse.json({ detail }, { status });
}

function parseBbox(value: string | null) {
  const parts = value?.split(",").map((part) => Number(part.trim()));
  if (!parts || parts.length !== 4 || parts.some((part) => !Number.isFinite(part))) {
    throw new Error("bbox must be four comma-separated numbers: min_lon,min_lat,max_lon,max_lat.");
  }
  const [minLon, minLat, maxLon, maxLat] = parts;
  if (minLon >= maxLon || minLat >= maxLat) {
    throw new Error("bbox min values must be less than max values.");
  }
  if (minLon < -180 || maxLon > 180 || minLat < -90 || maxLat > 90) {
    throw new Error("bbox coordinates are outside valid longitude/latitude ranges.");
  }
  return parts as [number, number, number, number];
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const signal = params.get("signal") ?? "";
  if (!SIGNAL_SOURCES[signal]) return error("Invalid signal.");

  let bbox: [number, number, number, number];
  try {
    bbox = parseBbox(params.get("bbox"));
  } catch (err) {
    return error(err instanceof Error ? err.message : "Invalid bbox.");
  }

  const days = Number(params.get("days") ?? 90);
  const limit = Number(params.get("limit") ?? 5000);
  if (!Number.isInteger(days) || days < 1) return error("days must be >= 1.");
  if (!Number.isInteger(limit) || limit < 1 || limit > 10000) {
    return error("limit must be between 1 and 10000.");
  }

  const [minLon, minLat, maxLon, maxLat] = bbox;
  const base = [SIGNAL_SOURCES[signal], minLon, minLat, maxLon, maxLat, days];
  const total = await pool.query<{ total: string }>(
    `SELECT count(*) AS total
     FROM events
     WHERE source = ANY($1::text[])
       AND occurred_at >= now() - ($6 * interval '1 day')
       AND geom IS NOT NULL
       AND ST_Intersects(geom, ST_MakeEnvelope($2, $3, $4, $5, 4326))`,
    base,
  );
  const totalMatch = Number(total.rows[0]?.total ?? 0);
  const sampled = totalMatch > limit;
  const sql = sampled
    ? `WITH sampled AS (
         SELECT id, source, summary, occurred_at, ST_X(geom) AS lon, ST_Y(geom) AS lat
         FROM events
         WHERE source = ANY($1::text[])
           AND occurred_at >= now() - ($6 * interval '1 day')
           AND geom IS NOT NULL
           AND ST_Intersects(geom, ST_MakeEnvelope($2, $3, $4, $5, 4326))
         ORDER BY random()
         LIMIT $7
       )
       SELECT * FROM sampled ORDER BY occurred_at DESC NULLS LAST`
    : `SELECT id, source, summary, occurred_at, ST_X(geom) AS lon, ST_Y(geom) AS lat
       FROM events
       WHERE source = ANY($1::text[])
         AND occurred_at >= now() - ($6 * interval '1 day')
         AND geom IS NOT NULL
         AND ST_Intersects(geom, ST_MakeEnvelope($2, $3, $4, $5, 4326))
       ORDER BY occurred_at DESC NULLS LAST
       LIMIT $7`;
  const rows = await pool.query(sql, [...base, limit]);
  return NextResponse.json(
    {
      type: "FeatureCollection",
      features: rows.rows.map((row) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [row.lon, row.lat] },
        properties: {
          id: row.id,
          source: row.source,
          summary: row.summary,
          occurred_at: row.occurred_at,
        },
      })),
      sampled,
      total_match: totalMatch,
    },
    { headers: { "Cache-Control": "s-maxage=600, stale-while-revalidate=300" } },
  );
}
