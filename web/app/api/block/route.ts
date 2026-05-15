import { NextRequest, NextResponse } from "next/server";

import { pool } from "@/lib/db";

export const runtime = "nodejs";

type EventRow = {
  id: string | null;
  source: string | null;
  event_type: string | null;
  summary: string | null;
  occurred_at: Date | string | null;
  category: string | null;
  status: string | null;
  raw_json: unknown;
};

type SignalReport = {
  signal_type: string;
  score: number;
  count: number;
  evidence: Array<{ id: string | null; source: string | null; summary: string | null; date: string | null }>;
};

function error(detail: string, status = 400) {
  return NextResponse.json({ detail }, { status });
}

function text(row: EventRow) {
  return `${row.event_type ?? ""} ${row.category ?? ""} ${row.summary ?? ""}`.toLowerCase();
}

function dateString(value: Date | string | null) {
  if (!value) return "";
  return value instanceof Date ? value.toISOString() : String(value);
}

function evidence(rows: EventRow[]) {
  return rows.slice(0, 10).map((row) => ({
    id: row.id,
    source: row.source,
    summary: row.summary,
    date: dateString(row.occurred_at),
  }));
}

function score(signalType: string, rows: EventRow[], value: number): SignalReport {
  return { signal_type: signalType, score: Math.round(value * 100) / 100, count: rows.length, evidence: evidence(rows) };
}

async function nearbyEvents(sources: string[], lat: number, lon: number, radiusFt: number, days: number) {
  const result = await pool.query<EventRow>(
    `SELECT id, source, event_type, summary, occurred_at, category, status, raw_json
     FROM events
     WHERE source = ANY($1::text[])
       AND occurred_at >= now() - ($5 * interval '1 day')
       AND geom IS NOT NULL
       AND ST_DWithin(
         geom::geography,
         ST_SetSRID(ST_MakePoint($3, $2), 4326)::geography,
         $4
       )
     ORDER BY occurred_at DESC NULLS LAST`,
    [sources, lat, lon, radiusFt * 0.3048, days],
  );
  return result.rows;
}

function scoreConstruction(rows: EventRow[]) {
  const terms = ["alteration", "alt", "new building", "nb", "demolition", "dm"];
  const high = rows.filter((row) => terms.some((term) => text(row).includes(term)));
  return score("construction_pressure", rows, rows.length + high.length * 0.5);
}

function scoreNightlife(rows: EventRow[]) {
  const relevant = rows.filter((row) => row.source !== "nyc_311" || text(row).includes("noise"));
  const liquor = relevant.filter((row) => row.source === "liquor").length;
  const noise = relevant.filter((row) => row.source === "nyc_311").length;
  const restaurants = relevant.filter((row) => row.source === "restaurants").length;
  return score("nightlife_activity", relevant, liquor * 1.5 + noise + restaurants * 0.4);
}

function scoreHousing(rows: EventRow[]) {
  const terms = ["heat", "hot water", "mold", "paint", "leak", "pest", "rodent", "elevator"];
  const relevant = rows.filter((row) => row.source !== "nyc_311" || terms.some((term) => text(row).includes(term)));
  const severe = relevant.filter(
    (row) => `${row.category ?? ""} ${row.event_type ?? ""}`.toLowerCase().includes("class c") || `${row.status ?? ""}`.toLowerCase().includes("open"),
  );
  return score("housing_distress", relevant, relevant.length + severe.length * 0.5);
}

function scoreRestaurants(rows: EventRow[]) {
  const relevant = rows.filter(
    (row) => row.source === "restaurants" || row.source === "liquor" || `${row.category ?? ""}`.toLowerCase().includes("plumbing") || text(row).includes("alteration"),
  );
  const inspections = relevant.filter((row) => row.source === "restaurants").length;
  const liquor = relevant.filter((row) => row.source === "liquor").length;
  const buildout = relevant.filter((row) => row.source === "dob_permits").length;
  return score("restaurant_turnover", relevant, inspections + liquor * 0.5 + buildout * 0.75);
}

function scoreQualityOfLife(rows: EventRow[]) {
  const terms = ["noise", "sanitation", "rodent", "illegal parking", "blocked driveway", "sidewalk", "street condition", "graffiti"];
  const relevant = rows.filter((row) => terms.some((term) => text(row).includes(term)));
  return score("quality_of_life_drift", relevant, relevant.length);
}

function pct(value: unknown) {
  return value == null ? "n/a" : `${Number(value).toFixed(1)}%`;
}

function income(value: unknown) {
  return value == null ? "n/a" : `$${Number(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

async function scoreDensityChange(lat: number, lon: number): Promise<SignalReport> {
  const result = await pool.query(
    `SELECT geoid, tract_name, borough, year, median_household_income,
            renter_occupied_pct, bachelors_or_higher_pct, under_5_pct,
            over_65_pct, density_change
     FROM block_demographics
     WHERE geom IS NOT NULL
       AND ST_Intersects(geom, ST_SetSRID(ST_MakePoint($2, $1), 4326))
     ORDER BY year DESC
     LIMIT 1`,
    [lat, lon],
  );
  const row = result.rows[0];
  if (!row) return { signal_type: "density_change", score: 0, count: 0, evidence: [] };
  return {
    signal_type: "density_change",
    score: Math.round(Number(row.density_change ?? 0) * 100) / 100,
    count: 1,
    evidence: [{
      id: row.geoid,
      source: "census_acs",
      summary: `${row.tract_name ?? row.geoid}: income ${income(row.median_household_income)}, renters ${pct(row.renter_occupied_pct)}, bachelor's+ ${pct(row.bachelors_or_higher_pct)}, under 5 ${pct(row.under_5_pct)}, over 65 ${pct(row.over_65_pct)}`,
      date: String(row.year ?? ""),
    }],
  };
}

async function geocode(address: string) {
  const params = new URLSearchParams({
    format: "json",
    q: address,
    countrycodes: "us",
    viewbox: "-74.27,40.91,-73.68,40.49",
    bounded: "1",
    limit: "1",
    addressdetails: "1",
  });
  let response: Response;
  try {
    response = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
      headers: { "User-Agent": "nyc-block-pulse/1.0 (https://nyc-block-pulse.vercel.app)" },
    });
  } catch {
    return null;
  }
  if (!response.ok) return null;
  const [first] = (await response.json()) as Array<{ lat?: string; lon?: string; address?: { borough?: string; city?: string; county?: string } }>;
  if (!first?.lat || !first.lon) return null;
  return {
    lat: Number(first.lat),
    lon: Number(first.lon),
    borough: first.address?.borough ?? first.address?.city ?? first.address?.county ?? null,
    bbl: null,
    bin: null,
  };
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null) as { lat?: unknown; lon?: unknown; address?: unknown; days?: unknown; radius_ft?: unknown } | null;
  if (!body) return error("Invalid JSON body.");

  const days = Number(body.days ?? 90);
  const radiusFt = Number(body.radius_ft ?? 500);
  if (!Number.isInteger(days) || days < 1) return error("days must be >= 1.");
  if (!Number.isInteger(radiusFt) || radiusFt <= 0) return error("radius_ft must be > 0.");

  const address = typeof body.address === "string" ? body.address.trim() : "";
  const location = address
    ? await geocode(address)
    : {
        lat: Number(body.lat),
        lon: Number(body.lon),
        borough: null,
        bbl: null,
        bin: null,
      };
  if (address && !location) {
    return error("Could not resolve address.", 404);
  }
  if (!location || !Number.isFinite(location.lat) || !Number.isFinite(location.lon)) {
    return error("Provide either address or both lat and lon.", 422);
  }

  const [construction, nightlife, housing, restaurants, qualityOfLife, densityChange] = await Promise.all([
    nearbyEvents(["dob_permits"], location.lat, location.lon, radiusFt, days).then(scoreConstruction),
    nearbyEvents(["liquor", "nyc_311", "restaurants"], location.lat, location.lon, radiusFt, days).then(scoreNightlife),
    nearbyEvents(["hpd_complaints", "hpd_violations", "nyc_311"], location.lat, location.lon, radiusFt, days).then(scoreHousing),
    nearbyEvents(["restaurants", "liquor", "dob_permits"], location.lat, location.lon, radiusFt, days).then(scoreRestaurants),
    nearbyEvents(["nyc_311"], location.lat, location.lon, radiusFt, days).then(scoreQualityOfLife),
    scoreDensityChange(location.lat, location.lon),
  ]);

  return NextResponse.json({
    location: { lat: location.lat, lon: location.lon, borough: location.borough, bbl: location.bbl, bin: location.bin },
    window_days: days,
    radius_ft: radiusFt,
    signals: { construction, nightlife, housing, restaurants, quality_of_life: qualityOfLife, density_change: densityChange },
  });
}
