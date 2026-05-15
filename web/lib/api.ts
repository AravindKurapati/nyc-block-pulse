import type {
  BBox,
  BlockReport,
  BlockRequest,
  DemographicsGeoJSON,
  EventSignalName,
  EventsGeoJSON,
  SearchResult,
  SignalTrendPoint,
} from "./types";

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
    signal: EventSignalName;
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

  const response = await fetch(`/api/events?${searchParams}`, {
    signal,
  });
  return parseJson<EventsGeoJSON>(response);
}

export async function fetchBlock(
  body: BlockRequest,
  signal?: AbortSignal,
): Promise<BlockReport> {
  const response = await fetch("/api/block", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return parseJson<BlockReport>(response);
}

export async function fetchSignalTrend(
  params: {
    signal: EventSignalName;
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
    `/api/signal-trend?${searchParams}`,
    { signal },
  );
  return parseJson<SignalTrendPoint[]>(response);
}

export async function fetchDemographics(
  params: {
    bbox: BBox;
    limit?: number;
  },
  signal?: AbortSignal,
): Promise<DemographicsGeoJSON> {
  const searchParams = new URLSearchParams({
    bbox: bboxToParam(params.bbox),
    limit: String(params.limit ?? 2000),
  });

  const response = await fetch(`/api/demographics?${searchParams}`, {
    signal,
  });
  return parseJson<DemographicsGeoJSON>(response);
}

export async function searchAddresses(
  query: string,
  signal?: AbortSignal,
): Promise<SearchResult[]> {
  const searchParams = new URLSearchParams({ q: query });
  const response = await fetch(`/api/search?${searchParams}`, {
    signal,
  });
  return parseJson<SearchResult[]>(response);
}
