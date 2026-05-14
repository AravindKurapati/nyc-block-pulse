"use client";

import { useEffect, useRef } from "react";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { latLngToCell } from "h3-js";
import { circle } from "@turf/turf";
import type { FeatureCollection, Polygon } from "geojson";
import maplibregl, {
  type GeoJSONSource,
  type IControl,
  type LngLatBounds,
  type Map as MapLibreMap,
  type Marker,
} from "maplibre-gl";

import { NYU_BUILDINGS } from "@/lib/nyu";
import type { BBox, DemographicsGeoJSON, EventsGeoJSON } from "@/lib/types";
import type { MapViewMode } from "./MapViewToggle";

const DECK_HEATMAP_LAYER_ID = "deck-signal-heatmap";
const DECK_H3_LAYER_ID = "deck-signal-h3";
const H3_RESOLUTION = 9;
const DEMOGRAPHICS_SOURCE_ID = "tract-demographics";
const DEMOGRAPHICS_FILL_LAYER_ID = "tract-demographics-fill";
const DEMOGRAPHICS_LINE_LAYER_ID = "tract-demographics-line";
const RADIUS_RING_SOURCE_ID = "selected-radius-ring";
const RADIUS_RING_FILL_LAYER_ID = "selected-radius-ring-fill";
const RADIUS_RING_LINE_LAYER_ID = "selected-radius-ring-line";
const NYU_SOURCE_ID = "nyu-buildings";
const NYU_CIRCLE_LAYER_ID = "nyu-building-circles";
const NYU_LABEL_LAYER_ID = "nyu-building-labels";

type SelectedLocation = {
  lat: number;
  lon: number;
} | null;

type PulseMapProps = {
  heatmapGeoJSON: EventsGeoJSON | null;
  demographicsGeoJSON: DemographicsGeoJSON | null;
  viewMode: MapViewMode;
  selectedLocation: SelectedLocation;
  selectedRadiusFt: number;
  onMapClick: (lat: number, lon: number) => void;
  onBoundsChange: (bbox: BBox) => void;
};

type EventPoint = {
  position: [number, number];
  weight: number;
};

type EventHex = {
  hex: string;
  count: number;
};

type RadiusRingGeoJSON = FeatureCollection<Polygon, { radius_ft?: number }>;

function boundsToBBox(bounds: LngLatBounds): BBox {
  return {
    minLon: bounds.getWest(),
    minLat: bounds.getSouth(),
    maxLon: bounds.getEast(),
    maxLat: bounds.getNorth(),
  };
}

function emptyDemographicsFeatureCollection(): DemographicsGeoJSON {
  return {
    type: "FeatureCollection",
    features: [],
  };
}

function radiusRingGeoJSON(
  location: SelectedLocation,
  radiusFt: number,
): RadiusRingGeoJSON {
  if (!location) {
    return {
      type: "FeatureCollection",
      features: [],
    };
  }

  return {
    type: "FeatureCollection",
    features: [
      circle([location.lon, location.lat], radiusFt / 5280, {
        steps: 96,
        units: "miles",
        properties: { radius_ft: radiusFt },
      }) as RadiusRingGeoJSON["features"][number],
    ],
  };
}

function eventPoints(data: EventsGeoJSON | null): EventPoint[] {
  return (
    data?.features.map((feature) => ({
      position: feature.geometry.coordinates,
      weight: 1,
    })) ?? []
  );
}

function eventHexagons(data: EventsGeoJSON | null): EventHex[] {
  const counts = new Map<string, number>();
  for (const feature of data?.features ?? []) {
    const [lon, lat] = feature.geometry.coordinates;
    const hex = latLngToCell(lat, lon, H3_RESOLUTION);
    counts.set(hex, (counts.get(hex) ?? 0) + 1);
  }
  return Array.from(counts, ([hex, count]) => ({ hex, count }));
}

function hexFillColor(count: number): [number, number, number, number] {
  if (count >= 25) return [220, 38, 38, 170];
  if (count >= 10) return [249, 115, 22, 155];
  if (count >= 4) return [250, 204, 21, 140];
  return [20, 184, 166, 125];
}

function deckEventLayers(data: EventsGeoJSON | null, viewMode: MapViewMode) {
  if (viewMode !== "events") {
    return [];
  }

  const points = eventPoints(data);
  const hexagons = eventHexagons(data);

  return [
    new HeatmapLayer<EventPoint>({
      id: DECK_HEATMAP_LAYER_ID,
      data: points,
      getPosition: (item) => item.position,
      getWeight: (item) => item.weight,
      radiusPixels: 48,
      intensity: 1.1,
      threshold: 0.04,
      opacity: 0.5,
    }),
    new H3HexagonLayer<EventHex>({
      id: DECK_H3_LAYER_ID,
      data: hexagons,
      getHexagon: (item) => item.hex,
      getFillColor: (item) => hexFillColor(item.count),
      getLineColor: [38, 38, 38, 90],
      getLineWidth: 1,
      lineWidthMinPixels: 0.75,
      stroked: true,
      filled: true,
      extruded: false,
      pickable: false,
    }),
  ];
}

function nyuBuildingsGeoJSON() {
  return {
    type: "FeatureCollection" as const,
    features: NYU_BUILDINGS.map((building) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: [building.lon, building.lat],
      },
      properties: {
        name: building.name,
        address: building.address,
      },
    })),
  };
}

export default function PulseMap({
  heatmapGeoJSON,
  demographicsGeoJSON,
  viewMode,
  selectedLocation,
  selectedRadiusFt,
  onMapClick,
  onBoundsChange,
}: PulseMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const deckOverlayRef = useRef<MapboxOverlay | null>(null);
  const clickHandlerRef = useRef(onMapClick);
  const boundsHandlerRef = useRef(onBoundsChange);
  const heatmapDataRef = useRef<EventsGeoJSON | null>(heatmapGeoJSON);
  const demographicsDataRef = useRef<DemographicsGeoJSON | null>(
    demographicsGeoJSON,
  );
  const radiusRingDataRef = useRef<RadiusRingGeoJSON>(
    radiusRingGeoJSON(selectedLocation, selectedRadiusFt),
  );

  useEffect(() => {
    clickHandlerRef.current = onMapClick;
  }, [onMapClick]);

  useEffect(() => {
    boundsHandlerRef.current = onBoundsChange;
  }, [onBoundsChange]);

  useEffect(() => {
    heatmapDataRef.current = heatmapGeoJSON;
  }, [heatmapGeoJSON]);

  useEffect(() => {
    demographicsDataRef.current = demographicsGeoJSON;
  }, [demographicsGeoJSON]);

  useEffect(() => {
    radiusRingDataRef.current = radiusRingGeoJSON(
      selectedLocation,
      selectedRadiusFt,
    );
  }, [selectedLocation, selectedRadiusFt]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/bright",
      center: [-73.97, 40.74],
      zoom: 11,
      attributionControl: false,
    });
    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true }),
      "top-left",
    );
    map.addControl(new maplibregl.AttributionControl({ compact: true }));
    const deckOverlay = new MapboxOverlay({
      interleaved: false,
      layers: deckEventLayers(heatmapDataRef.current, viewMode),
    });
    deckOverlayRef.current = deckOverlay;
    map.addControl(deckOverlay as unknown as IControl);

    map.on("load", () => {
      map.addSource(DEMOGRAPHICS_SOURCE_ID, {
        type: "geojson",
        data:
          demographicsDataRef.current ?? emptyDemographicsFeatureCollection(),
      });
      map.addLayer({
        id: DEMOGRAPHICS_FILL_LAYER_ID,
        type: "fill",
        source: DEMOGRAPHICS_SOURCE_ID,
        layout: {
          visibility: viewMode === "demographics" ? "visible" : "none",
        },
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "density_change"], 0],
            0,
            "#d1fae5",
            10,
            "#fef08a",
            25,
            "#fb923c",
            50,
            "#dc2626",
          ],
          "fill-opacity": 0.58,
        },
      });
      map.addLayer({
        id: DEMOGRAPHICS_LINE_LAYER_ID,
        type: "line",
        source: DEMOGRAPHICS_SOURCE_ID,
        layout: {
          visibility: viewMode === "demographics" ? "visible" : "none",
        },
        paint: {
          "line-color": "#525252",
          "line-opacity": 0.5,
          "line-width": 0.8,
        },
      });
      map.addSource(RADIUS_RING_SOURCE_ID, {
        type: "geojson",
        data: radiusRingDataRef.current,
      });
      map.addLayer({
        id: RADIUS_RING_FILL_LAYER_ID,
        type: "fill",
        source: RADIUS_RING_SOURCE_ID,
        paint: {
          "fill-color": "#111827",
          "fill-opacity": 0.08,
        },
      });
      map.addLayer({
        id: RADIUS_RING_LINE_LAYER_ID,
        type: "line",
        source: RADIUS_RING_SOURCE_ID,
        paint: {
          "line-color": "#111827",
          "line-opacity": 0.75,
          "line-width": 2,
          "line-dasharray": [2, 1.5],
        },
      });
      map.addSource(NYU_SOURCE_ID, {
        type: "geojson",
        data: nyuBuildingsGeoJSON(),
      });
      map.addLayer({
        id: NYU_CIRCLE_LAYER_ID,
        type: "circle",
        source: NYU_SOURCE_ID,
        paint: {
          "circle-color": "#7c3aed",
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            10,
            5,
            15,
            9,
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
          "circle-opacity": 0.95,
        },
      });
      map.addLayer({
        id: NYU_LABEL_LAYER_ID,
        type: "symbol",
        source: NYU_SOURCE_ID,
        minzoom: 13,
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Open Sans Semibold", "Arial Unicode MS Bold"],
          "text-size": 12,
          "text-offset": [0, 1.2],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#581c87",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1.5,
        },
      });
      map.on("mouseenter", NYU_CIRCLE_LAYER_ID, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", NYU_CIRCLE_LAYER_ID, () => {
        map.getCanvas().style.cursor = "";
      });
      boundsHandlerRef.current(boundsToBBox(map.getBounds()));
    });

    map.on("click", (event) => {
      const layers = [NYU_CIRCLE_LAYER_ID, NYU_LABEL_LAYER_ID].filter((layer) =>
        map.getLayer(layer),
      );
      const nyuFeature = layers.length
        ? map.queryRenderedFeatures(event.point, { layers })[0]
        : undefined;
      if (nyuFeature?.geometry.type === "Point") {
        const [lon, lat] = nyuFeature.geometry.coordinates as [number, number];
        clickHandlerRef.current(lat, lon);
        return;
      }
      clickHandlerRef.current(event.lngLat.lat, event.lngLat.lng);
    });

    map.on("moveend", () => {
      boundsHandlerRef.current(boundsToBBox(map.getBounds()));
    });

    return () => {
      markerRef.current?.remove();
      deckOverlayRef.current?.finalize();
      deckOverlayRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    deckOverlayRef.current?.setProps({
      layers: deckEventLayers(heatmapDataRef.current, viewMode),
    });
  }, [heatmapGeoJSON, viewMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const applyDemographics = () => {
      const source = map.getSource(DEMOGRAPHICS_SOURCE_ID) as
        | GeoJSONSource
        | undefined;
      source?.setData(
        demographicsDataRef.current ?? emptyDemographicsFeatureCollection(),
      );
    };

    if (map.isStyleLoaded() && map.getSource(DEMOGRAPHICS_SOURCE_ID)) {
      applyDemographics();
      return;
    }

    map.once("load", applyDemographics);
    return () => {
      map.off("load", applyDemographics);
    };
  }, [demographicsGeoJSON]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const applyRadiusRing = () => {
      const source = map.getSource(RADIUS_RING_SOURCE_ID) as
        | GeoJSONSource
        | undefined;
      source?.setData(radiusRingDataRef.current);
    };

    if (map.isStyleLoaded() && map.getSource(RADIUS_RING_SOURCE_ID)) {
      applyRadiusRing();
      return;
    }

    map.once("load", applyRadiusRing);
    return () => {
      map.off("load", applyRadiusRing);
    };
  }, [selectedLocation, selectedRadiusFt]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const applyVisibility = () => {
      for (const layer of [
        DEMOGRAPHICS_FILL_LAYER_ID,
        DEMOGRAPHICS_LINE_LAYER_ID,
      ]) {
        if (map.getLayer(layer)) {
          map.setLayoutProperty(
            layer,
            "visibility",
            viewMode === "demographics" ? "visible" : "none",
          );
        }
      }
    };

    if (map.isStyleLoaded()) {
      applyVisibility();
      return;
    }

    map.once("load", applyVisibility);
    return () => {
      map.off("load", applyVisibility);
    };
  }, [viewMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedLocation) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }

    const lngLat: [number, number] = [selectedLocation.lon, selectedLocation.lat];
    if (!markerRef.current) {
      markerRef.current = new maplibregl.Marker({ color: "#111827" })
        .setLngLat(lngLat)
        .addTo(map);
    } else {
      markerRef.current.setLngLat(lngLat);
    }
    map.flyTo({ center: lngLat, zoom: Math.max(map.getZoom(), 14), essential: true });
  }, [selectedLocation]);

  return <div ref={containerRef} className="h-full min-h-[420px] w-full" />;
}
