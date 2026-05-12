"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import BlockPanel from "@/components/BlockPanel";
import SearchBar from "@/components/SearchBar";
import SignalToggle from "@/components/SignalToggle";
import { fetchBlock, fetchEvents } from "@/lib/api";
import type {
  BBox,
  BlockReport,
  EventsGeoJSON,
  SearchResult,
  SignalName,
} from "@/lib/types";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

const DEFAULT_SIGNAL: SignalName = "quality_of_life";
const DEFAULT_DAYS = 90;
const DEFAULT_RADIUS_FT = 500;

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export default function Home() {
  const [signal, setSignal] = useState<SignalName>(DEFAULT_SIGNAL);
  const [heatmapGeoJSON, setHeatmapGeoJSON] = useState<EventsGeoJSON | null>(
    null,
  );
  const [report, setReport] = useState<BlockReport | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number;
    lon: number;
  } | null>(null);
  const [isBlockLoading, setIsBlockLoading] = useState(false);
  const [blockError, setBlockError] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const panelError = blockError ?? eventError;

  const signalRef = useRef(signal);
  const bboxRef = useRef<BBox | null>(null);
  const eventAbortRef = useRef<AbortController | null>(null);
  const blockAbortRef = useRef<AbortController | null>(null);
  const boundsDebounceRef = useRef<number | null>(null);

  useEffect(() => {
    signalRef.current = signal;
  }, [signal]);

  const requestEvents = useCallback((nextSignal: SignalName, bbox: BBox) => {
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

  const handleBoundsChange = useCallback(
    (bbox: BBox) => {
      bboxRef.current = bbox;
      if (boundsDebounceRef.current) {
        window.clearTimeout(boundsDebounceRef.current);
      }
      boundsDebounceRef.current = window.setTimeout(() => {
        requestEvents(signalRef.current, bbox);
      }, 300);
    },
    [requestEvents],
  );

  useEffect(() => {
    const bbox = bboxRef.current;
    if (bbox) {
      requestEvents(signal, bbox);
    }
    document
      .getElementById(`signal-${signal}`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [requestEvents, signal]);

  const loadBlock = useCallback((lat: number, lon: number) => {
    blockAbortRef.current?.abort();
    const controller = new AbortController();
    blockAbortRef.current = controller;
    setSelectedLocation({ lat, lon });
    setBlockError(null);
    setIsBlockLoading(true);

    fetchBlock(
      { lat, lon, days: DEFAULT_DAYS, radius_ft: DEFAULT_RADIUS_FT },
      controller.signal,
    )
      .then((data) => setReport(data))
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
  }, []);

  const handleSearchSelect = useCallback(
    (result: SearchResult) => {
      loadBlock(result.lat, result.lon);
    },
    [loadBlock],
  );

  useEffect(() => {
    return () => {
      eventAbortRef.current?.abort();
      blockAbortRef.current?.abort();
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
            selectedLocation={selectedLocation}
            onMapClick={loadBlock}
            onBoundsChange={handleBoundsChange}
          />
          <div className="pointer-events-none absolute bottom-4 left-4 z-10">
            <div className="pointer-events-auto">
              <SignalToggle signal={signal} onChange={setSignal} />
            </div>
          </div>
        </section>

        <div className="min-h-[520px] lg:h-[calc(100vh-4rem)]">
          <BlockPanel
            report={report}
            isLoading={isBlockLoading}
            error={panelError}
            selectedSignal={signal}
          />
        </div>
      </div>
    </main>
  );
}
