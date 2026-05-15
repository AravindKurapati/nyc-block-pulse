import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

type NominatimResult = {
  display_name?: string;
  lat?: string;
  lon?: string;
  address?: {
    borough?: string;
    city?: string;
    county?: string;
  };
};

function borough(result: NominatimResult) {
  const raw = result.address?.borough ?? result.address?.city ?? result.address?.county;
  if (!raw) return null;
  return raw.replace(" County", "").replace("The ", "");
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim();
  if (!q) return NextResponse.json({ detail: "q is required." }, { status: 400 });

  const params = new URLSearchParams({
    format: "json",
    q,
    countrycodes: "us",
    viewbox: "-74.27,40.91,-73.68,40.49",
    bounded: "1",
    limit: "5",
    addressdetails: "1",
  });
  let response: Response;
  try {
    response = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
      headers: {
        "User-Agent": "nyc-block-pulse/1.0 (https://nyc-block-pulse.vercel.app)",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Nominatim request failed." }, { status: 502 });
  }
  if (!response.ok) {
    return NextResponse.json({ detail: "Nominatim request failed." }, { status: 502 });
  }

  const payload = (await response.json()) as NominatimResult[];
  return NextResponse.json(
    payload
      .filter((item) => item.lat && item.lon)
      .slice(0, 5)
      .map((item) => ({
        display: item.display_name ?? q,
        lat: Number(item.lat),
        lon: Number(item.lon),
        borough: borough(item),
      })),
  );
}
