import type {
  BBox,
  BlockReport,
  BlockRequest,
  EventsGeoJSON,
  SearchResult,
  SignalName,
  SignalTrendPoint,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the status-based fallback when the server does not return JSON.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export function bboxToParam(bbox: BBox): string {
  return [bbox.minLon, bbox.minLat, bbox.maxLon, bbox.maxLat].join(",");
}

export async function fetchEvents(
  params: {
    signal: SignalName;
    bbox: BBox;
    days?: number;
    limit?: number;
  },
  signal?: AbortSignal,
): Promise<EventsGeoJSON> {
  const searchParams = new URLSearchParams({
    signal: params.signal,
    bbox: bboxToParam(params.bbox),
    days: String(params.days ?? 90),
    limit: String(params.limit ?? 5000),
  });

  const response = await fetch(`${API_BASE_URL}/api/events?${searchParams}`, {
    signal,
  });
  return parseJson<EventsGeoJSON>(response);
}

export async function fetchBlock(
  body: BlockRequest,
  signal?: AbortSignal,
): Promise<BlockReport> {
  const response = await fetch(`${API_BASE_URL}/api/block`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return parseJson<BlockReport>(response);
}

export async function fetchSignalTrend(
  params: {
    signal: SignalName;
    lat: number;
    lon: number;
    radius_ft?: number;
    days?: number;
  },
  signal?: AbortSignal,
): Promise<SignalTrendPoint[]> {
  const searchParams = new URLSearchParams({
    signal: params.signal,
    lat: String(params.lat),
    lon: String(params.lon),
    radius_ft: String(params.radius_ft ?? 500),
    days: String(params.days ?? 90),
  });

  const response = await fetch(
    `${API_BASE_URL}/api/signal-trend?${searchParams}`,
    { signal },
  );
  return parseJson<SignalTrendPoint[]>(response);
}

export async function searchAddresses(
  query: string,
  signal?: AbortSignal,
): Promise<SearchResult[]> {
  const searchParams = new URLSearchParams({ q: query });
  const response = await fetch(`${API_BASE_URL}/api/search?${searchParams}`, {
    signal,
  });
  return parseJson<SearchResult[]>(response);
}
