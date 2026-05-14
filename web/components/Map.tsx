"use client";

import { useEffect, useRef } from "react";
import maplibregl, {
  type GeoJSONSource,
  type LngLatBounds,
  type Map as MapLibreMap,
  type Marker,
} from "maplibre-gl";

import { NYU_BUILDINGS } from "@/lib/nyu";
import type { BBox, EventsGeoJSON } from "@/lib/types";

const HEATMAP_SOURCE_ID = "signal-events";
const HEATMAP_LAYER_ID = "signal-heatmap";
const NYU_SOURCE_ID = "nyu-buildings";
const NYU_CIRCLE_LAYER_ID = "nyu-building-circles";
const NYU_LABEL_LAYER_ID = "nyu-building-labels";

type SelectedLocation = {
  lat: number;
  lon: number;
} | null;

type PulseMapProps = {
  heatmapGeoJSON: EventsGeoJSON | null;
  selectedLocation: SelectedLocation;
  onMapClick: (lat: number, lon: number) => void;
  onBoundsChange: (bbox: BBox) => void;
};

function boundsToBBox(bounds: LngLatBounds): BBox {
  return {
    minLon: bounds.getWest(),
    minLat: bounds.getSouth(),
    maxLon: bounds.getEast(),
    maxLat: bounds.getNorth(),
  };
}

function emptyFeatureCollection(): EventsGeoJSON {
  return {
    type: "FeatureCollection",
    features: [],
    sampled: false,
    total_match: 0,
  };
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
  selectedLocation,
  onMapClick,
  onBoundsChange,
}: PulseMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const clickHandlerRef = useRef(onMapClick);
  const boundsHandlerRef = useRef(onBoundsChange);
  const heatmapDataRef = useRef<EventsGeoJSON | null>(heatmapGeoJSON);

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

    map.on("load", () => {
      map.addSource(HEATMAP_SOURCE_ID, {
        type: "geojson",
        data: heatmapDataRef.current ?? emptyFeatureCollection(),
      });
      map.addLayer({
        id: HEATMAP_LAYER_ID,
        type: "heatmap",
        source: HEATMAP_SOURCE_ID,
        maxzoom: 16,
        paint: {
          "heatmap-weight": [
            "interpolate",
            ["linear"],
            ["zoom"],
            10,
            0.6,
            16,
            1,
          ],
          "heatmap-intensity": [
            "interpolate",
            ["linear"],
            ["zoom"],
            9,
            0.9,
            15,
            1.8,
          ],
          "heatmap-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            9,
            12,
            15,
            28,
          ],
          "heatmap-opacity": 0.72,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(255,255,255,0)",
            0.2,
            "#4cc9f0",
            0.45,
            "#4895ef",
            0.7,
            "#f9c74f",
            1,
            "#d00000",
          ],
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
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const applyHeatmap = () => {
      const source = map.getSource(HEATMAP_SOURCE_ID) as
        | GeoJSONSource
        | undefined;
      source?.setData(heatmapDataRef.current ?? emptyFeatureCollection());
    };

    if (map.isStyleLoaded() && map.getSource(HEATMAP_SOURCE_ID)) {
      applyHeatmap();
      return;
    }

    map.once("load", applyHeatmap);
    return () => {
      map.off("load", applyHeatmap);
    };
  }, [heatmapGeoJSON]);

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
