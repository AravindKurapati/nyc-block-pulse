"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import BlockPanel from "@/components/BlockPanel";
import MapViewToggle, { type MapViewMode } from "@/components/MapViewToggle";
import SearchBar from "@/components/SearchBar";
import SignalToggle from "@/components/SignalToggle";
import {
  fetchBlock,
  fetchDemographics,
  fetchEvents,
  fetchSignalTrend,
} from "@/lib/api";
import type {
  BBox,
  BlockReport,
  DemographicsGeoJSON,
  EventSignalName,
  EventsGeoJSON,
  SearchResult,
  SignalTrends,
} from "@/lib/types";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

const DEFAULT_SIGNAL: EventSignalName = "quality_of_life";
const DEFAULT_DAYS = 90;
const DEFAULT_RADIUS_FT = 500;
const SIGNAL_ORDER: EventSignalName[] = [
  "construction",
  "nightlife",
  "housing",
  "restaurants",
  "quality_of_life",
];

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export default function Home() {
  const [signal, setSignal] = useState<EventSignalName>(DEFAULT_SIGNAL);
  const [mapViewMode, setMapViewMode] = useState<MapViewMode>("events");
  const [heatmapGeoJSON, setHeatmapGeoJSON] = useState<EventsGeoJSON | null>(
    null,
  );
  const [demographicsGeoJSON, setDemographicsGeoJSON] =
    useState<DemographicsGeoJSON | null>(null);
  const [report, setReport] = useState<BlockReport | null>(null);
  const [signalTrends, setSignalTrends] = useState<SignalTrends>({});
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number;
    lon: number;
  } | null>(null);
  const [isBlockLoading, setIsBlockLoading] = useState(false);
  const [isTrendLoading, setIsTrendLoading] = useState(false);
  const [blockError, setBlockError] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const panelError = blockError ?? eventError;

  const signalRef = useRef(signal);
  const mapViewModeRef = useRef(mapViewMode);
  const bboxRef = useRef<BBox | null>(null);
  const eventAbortRef = useRef<AbortController | null>(null);
  const demographicsAbortRef = useRef<AbortController | null>(null);
  const blockAbortRef = useRef<AbortController | null>(null);
  const trendAbortRef = useRef<AbortController | null>(null);
  const boundsDebounceRef = useRef<number | null>(null);
  const pendingSignalRef = useRef<EventSignalName | null>(null);

  useEffect(() => {
    signalRef.current = signal;
  }, [signal]);

  useEffect(() => {
    mapViewModeRef.current = mapViewMode;
  }, [mapViewMode]);

  const requestEvents = useCallback((nextSignal: EventSignalName, bbox: BBox) => {
    eventAbortRef.current?.abort();
    const controller = new AbortController();
    eventAbortRef.current = controller;
    setEventError(null);

    fetchEvents(
      { signal: nextSignal, bbox, days: DEFAULT_DAYS, limit: 5000 },
      controller.signal,
    )
      .then((data) => setHeatmapGeoJSON(data))
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        setEventError(
          error instanceof Error ? error.message : "Could not load map events.",
        );
      });
  }, []);

  const requestSignalTrends = useCallback((nextReport: BlockReport) => {
    trendAbortRef.current?.abort();
    const controller = new AbortController();
    trendAbortRef.current = controller;
    setSignalTrends({});
    setIsTrendLoading(true);

    Promise.all(
      SIGNAL_ORDER.map(async (signalName) => {
        const trend = await fetchSignalTrend(
          {
            signal: signalName,
            lat: nextReport.location.lat,
            lon: nextReport.location.lon,
            days: nextReport.window_days,
            radius_ft: nextReport.radius_ft,
          },
          controller.signal,
        );
        return [signalName, trend] as const;
      }),
    )
      .then((entries) => {
        setSignalTrends(Object.fromEntries(entries) as SignalTrends);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        setEventError(
          error instanceof Error
            ? error.message
            : "Could not load signal trends.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsTrendLoading(false);
        }
      });
  }, []);

  const requestDemographics = useCallback((bbox: BBox) => {
    demographicsAbortRef.current?.abort();
    const controller = new AbortController();
    demographicsAbortRef.current = controller;
    setEventError(null);

    fetchDemographics({ bbox, limit: 2000 }, controller.signal)
      .then((data) => setDemographicsGeoJSON(data))
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        setEventError(
          error instanceof Error
            ? error.message
            : "Could not load demographics.",
        );
      });
  }, []);

  const handleBoundsChange = useCallback(
    (bbox: BBox) => {
      bboxRef.current = bbox;
      if (boundsDebounceRef.current) {
        window.clearTimeout(boundsDebounceRef.current);
      }
      boundsDebounceRef.current = window.setTimeout(() => {
        if (mapViewModeRef.current === "demographics") {
          requestDemographics(bbox);
          return;
        }
        const pendingSignal = pendingSignalRef.current;
        pendingSignalRef.current = null;
        requestEvents(pendingSignal ?? signalRef.current, bbox);
      }, 300);
    },
    [requestDemographics, requestEvents],
  );

  useEffect(() => {
    if (mapViewMode !== "events") {
      pendingSignalRef.current = signal;
      return;
    }
    const bbox = bboxRef.current;
    if (bbox) {
      requestEvents(signal, bbox);
    } else {
      pendingSignalRef.current = signal;
    }
    document
      .getElementById(`signal-${signal}`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [mapViewMode, requestEvents, signal]);

  useEffect(() => {
    const bbox = bboxRef.current;
    if (!bbox) {
      return;
    }
    if (mapViewMode === "demographics") {
      requestDemographics(bbox);
      return;
    }
    requestEvents(signalRef.current, bbox);
  }, [mapViewMode, requestDemographics, requestEvents]);

  const loadBlock = useCallback((lat: number, lon: number) => {
    blockAbortRef.current?.abort();
    trendAbortRef.current?.abort();
    const controller = new AbortController();
    blockAbortRef.current = controller;
    setSelectedLocation({ lat, lon });
    setSignalTrends({});
    setBlockError(null);
    setIsBlockLoading(true);
    setIsTrendLoading(false);

    fetchBlock(
      { lat, lon, days: DEFAULT_DAYS, radius_ft: DEFAULT_RADIUS_FT },
      controller.signal,
    )
      .then((data) => {
        setReport(data);
        requestSignalTrends(data);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        setBlockError(
          error instanceof Error
            ? error.message
            : "Could not load block report.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsBlockLoading(false);
        }
      });
  }, [requestSignalTrends]);

  const handleSearchSelect = useCallback(
    (result: SearchResult) => {
      loadBlock(result.lat, result.lon);
    },
    [loadBlock],
  );

  useEffect(() => {
    return () => {
      eventAbortRef.current?.abort();
      demographicsAbortRef.current?.abort();
      blockAbortRef.current?.abort();
      trendAbortRef.current?.abort();
      if (boundsDebounceRef.current) {
        window.clearTimeout(boundsDebounceRef.current);
      }
    };
  }, []);

  return (
    <main className="flex min-h-screen flex-col bg-neutral-100 text-neutral-950">
      <header className="z-20 flex min-h-16 items-center gap-4 border-b border-neutral-200 bg-white px-4 py-3 shadow-sm md:px-6">
        <div className="shrink-0 text-lg font-semibold tracking-tight">
          NYC Block Pulse
        </div>
        <div className="min-w-0 flex-1">
          <SearchBar onSelect={handleSearchSelect} />
        </div>
      </header>

      <div className="grid flex-1 lg:grid-cols-[minmax(0,65fr)_minmax(360px,35fr)]">
        <section className="relative min-h-[calc(100vh-4rem)] bg-neutral-200">
          <Map
            heatmapGeoJSON={heatmapGeoJSON}
            demographicsGeoJSON={demographicsGeoJSON}
            viewMode={mapViewMode}
            selectedLocation={selectedLocation}
            selectedRadiusFt={report?.radius_ft ?? DEFAULT_RADIUS_FT}
            onMapClick={loadBlock}
            onBoundsChange={handleBoundsChange}
          />
          <div className="pointer-events-none absolute bottom-4 left-4 z-10 space-y-3">
            <div className="pointer-events-auto">
              <MapViewToggle mode={mapViewMode} onChange={setMapViewMode} />
            </div>
            {mapViewMode === "events" ? (
              <div className="pointer-events-auto">
                <SignalToggle signal={signal} onChange={setSignal} />
              </div>
            ) : null}
          </div>
        </section>

        <div className="min-h-[520px] lg:h-[calc(100vh-4rem)]">
          <BlockPanel
            report={report}
            isLoading={isBlockLoading}
            isTrendLoading={isTrendLoading}
            error={panelError}
            selectedSignal={signal}
            trends={signalTrends}
            onFlyTo={loadBlock}
          />
        </div>
      </div>
    </main>
  );
}
