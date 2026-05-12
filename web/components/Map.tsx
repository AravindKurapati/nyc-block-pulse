"use client";

import { useEffect, useRef } from "react";
import maplibregl, {
  type GeoJSONSource,
  type LngLatBounds,
  type Map as MapLibreMap,
  type Marker,
} from "maplibre-gl";

import type { BBox, EventsGeoJSON } from "@/lib/types";

const HEATMAP_SOURCE_ID = "signal-events";
const HEATMAP_LAYER_ID = "signal-heatmap";

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

  useEffect(() => {
    clickHandlerRef.current = onMapClick;
  }, [onMapClick]);

  useEffect(() => {
    boundsHandlerRef.current = onBoundsChange;
  }, [onBoundsChange]);

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
        data: emptyFeatureCollection(),
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
      boundsHandlerRef.current(boundsToBBox(map.getBounds()));
    });

    map.on("click", (event) => {
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
    if (!map || !map.isStyleLoaded()) {
      return;
    }
    const source = map.getSource(HEATMAP_SOURCE_ID) as GeoJSONSource | undefined;
    source?.setData(heatmapGeoJSON ?? emptyFeatureCollection());
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
