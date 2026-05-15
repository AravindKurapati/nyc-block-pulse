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

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const signal = params.get("signal") ?? "";
  const lat = Number(params.get("lat"));
  const lon = Number(params.get("lon"));
  const radiusFt = Number(params.get("radius_ft") ?? 500);
  const days = Number(params.get("days") ?? 90);
  if (!SIGNAL_SOURCES[signal]) return error("Invalid signal.");
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return error("Invalid lat.");
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return error("Invalid lon.");
  if (!Number.isInteger(radiusFt) || radiusFt <= 0) return error("radius_ft must be > 0.");
  if (!Number.isInteger(days) || days < 1 || days > 366) return error("days must be between 1 and 366.");

  const rows = await pool.query(
    `WITH day_series AS (
       SELECT generate_series(
         (current_date - (($5 - 1) * interval '1 day'))::date,
         current_date,
         interval '1 day'
       )::date AS day
     ),
     event_counts AS (
       SELECT occurred_at::date AS day, count(*)::integer AS count
       FROM events
       WHERE source = ANY($1::text[])
         AND occurred_at >= now() - ($5 * interval '1 day')
         AND geom IS NOT NULL
         AND ST_DWithin(
           geom::geography,
           ST_SetSRID(ST_MakePoint($3, $2), 4326)::geography,
           $4
         )
       GROUP BY occurred_at::date
     )
     SELECT to_char(day_series.day, 'YYYY-MM-DD') AS date,
            COALESCE(event_counts.count, 0)::integer AS count
     FROM day_series
     LEFT JOIN event_counts ON event_counts.day = day_series.day
     ORDER BY day_series.day`,
    [SIGNAL_SOURCES[signal], lat, lon, radiusFt * 0.3048, days],
  );
  return NextResponse.json(rows.rows);
}
