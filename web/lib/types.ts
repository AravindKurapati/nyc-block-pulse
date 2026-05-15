export type SignalName =
  | "construction"
  | "nightlife"
  | "housing"
  | "restaurants"
  | "quality_of_life";

export type EventFeature = {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    id: string;
    source: string;
    summary: string | null;
    occurred_at: string | null;
  };
};

export type EventsGeoJSON = {
  type: "FeatureCollection";
  features: EventFeature[];
  sampled: boolean;
  total_match: number;
};

export type SearchResult = {
  display: string;
  lat: number;
  lon: number;
  borough: string | null;
};

export type SignalEvidence = {
  id: string | null;
  source: string | null;
  summary: string | null;
  date: string | null;
};

export type SignalReport = {
  signal_type: string;
  score: number;
  count: number;
  evidence: SignalEvidence[];
};

export type SignalTrendPoint = {
  date: string;
  count: number;
};

export type SignalTrends = Partial<Record<SignalName, SignalTrendPoint[]>>;

export type BlockReport = {
  location: {
    lat: number;
    lon: number;
    borough: string | null;
    bbl: string | null;
    bin: string | null;
  };
  window_days: number;
  radius_ft: number;
  signals: Record<SignalName, SignalReport>;
};

export type BBox = {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
};

export type BlockRequest =
  | {
      lat: number;
      lon: number;
      days?: number;
      radius_ft?: number;
    }
  | {
      address: string;
      days?: number;
      radius_ft?: number;
    };
