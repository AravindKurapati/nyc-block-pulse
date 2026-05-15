import { NextRequest, NextResponse } from "next/server";

import { pool } from "@/lib/db";

export const runtime = "nodejs";

function error(detail: string, status = 400) {
  return NextResponse.json({ detail }, { status });
}

function parseBbox(value: string | null) {
  const parts = value?.split(",").map((part) => Number(part.trim()));
  if (!parts || parts.length !== 4 || parts.some((part) => !Number.isFinite(part))) {
    throw new Error("bbox must be four comma-separated numbers: min_lon,min_lat,max_lon,max_lat.");
  }
  const [minLon, minLat, maxLon, maxLat] = parts;
  if (minLon >= maxLon || minLat >= maxLat) throw new Error("bbox min values must be less than max values.");
  if (minLon < -180 || maxLon > 180 || minLat < -90 || maxLat > 90) {
    throw new Error("bbox coordinates are outside valid longitude/latitude ranges.");
  }
  return parts as [number, number, number, number];
}

export async function GET(request: NextRequest) {
  let bbox: [number, number, number, number];
  try {
    bbox = parseBbox(request.nextUrl.searchParams.get("bbox"));
  } catch (err) {
    return error(err instanceof Error ? err.message : "Invalid bbox.");
  }
  const limit = Number(request.nextUrl.searchParams.get("limit") ?? 2000);
  if (!Number.isInteger(limit) || limit < 1 || limit > 5000) {
    return error("limit must be between 1 and 5000.");
  }

  const rows = await pool.query(
    `SELECT geoid, tract_name, borough, year, median_household_income,
            renter_occupied_pct, bachelors_or_higher_pct, under_5_pct,
            over_65_pct, density_change, ST_AsGeoJSON(geom)::json AS geometry
     FROM block_demographics
     WHERE geom IS NOT NULL
       AND ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
     ORDER BY density_change DESC, geoid
     LIMIT $5`,
    [...bbox, limit],
  );
  return NextResponse.json(
    {
      type: "FeatureCollection",
      features: rows.rows
        .filter((row) => row.geometry)
        .map((row) => ({
          type: "Feature",
          geometry: typeof row.geometry === "string" ? JSON.parse(row.geometry) : row.geometry,
          properties: {
            geoid: row.geoid,
            tract_name: row.tract_name,
            borough: row.borough,
            year: row.year,
            median_household_income: row.median_household_income,
            renter_occupied_pct: row.renter_occupied_pct,
            bachelors_or_higher_pct: row.bachelors_or_higher_pct,
            under_5_pct: row.under_5_pct,
            over_65_pct: row.over_65_pct,
            density_change: row.density_change,
          },
        })),
    },
    { headers: { "Cache-Control": "s-maxage=600, stale-while-revalidate=300" } },
  );
}
