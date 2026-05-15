export type EventSignalName =
  | "construction"
  | "nightlife"
  | "housing"
  | "restaurants"
  | "quality_of_life";

export type SignalName = EventSignalName | "density_change";

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

export type SignalTrends = Partial<Record<EventSignalName, SignalTrendPoint[]>>;

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

type GeoJSONPosition = [number, number] | [number, number, number];
type DemographicsProperties = {
  geoid: string;
  tract_name: string | null;
  borough: string | null;
  year: number | null;
  median_household_income: number | null;
  renter_occupied_pct: number | null;
  bachelors_or_higher_pct: number | null;
  under_5_pct: number | null;
  over_65_pct: number | null;
  density_change: number | null;
};

export type DemographicsFeature =
  | {
      type: "Feature";
      geometry: {
        type: "Polygon";
        coordinates: GeoJSONPosition[][];
      };
      properties: DemographicsProperties;
    }
  | {
      type: "Feature";
      geometry: {
        type: "MultiPolygon";
        coordinates: GeoJSONPosition[][][];
      };
      properties: DemographicsProperties;
    };

export type DemographicsGeoJSON = {
  type: "FeatureCollection";
  features: DemographicsFeature[];
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
