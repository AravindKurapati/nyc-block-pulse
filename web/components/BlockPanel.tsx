"use client";

import { useEffect, useRef, useState } from "react";

import type { BlockReport, SignalName } from "@/lib/types";

type FlyToSpot = {
  name: string;
  subtitle: string;
  lat: number;
  lon: number;
};

type SavedBlock = {
  label: string;
  lat: number;
  lon: number;
};

const ARU_PICKS: FlyToSpot[] = [
  { name: "Washington Square Park", subtitle: "Greenwich Village", lat: 40.73082, lon: -73.99763 },
  { name: "Apollo Bagels", subtitle: "West Village", lat: 40.72941, lon: -74.00277 },
  { name: "NYU Langone Health", subtitle: "Murray Hill", lat: 40.74220, lon: -73.97440 },
  { name: "DUMBO", subtitle: "Brooklyn", lat: 40.70338, lon: -73.98930 },
  { name: "NYU 404", subtitle: "NoHo", lat: 40.72952, lon: -73.99585 },
  { name: "Bensonhurst Park", subtitle: "Brooklyn", lat: 40.60526, lon: -74.00910 },
  { name: "Domino Park", subtitle: "Williamsburg", lat: 40.71503, lon: -73.96590 },
  { name: "Hunters Point", subtitle: "LIC, Queens", lat: 40.74480, lon: -73.94860 },
  { name: "The High Line", subtitle: "Chelsea", lat: 40.74800, lon: -74.00480 },
  { name: "Katz's Delicatessen", subtitle: "Lower East Side", lat: 40.72228, lon: -73.98737 },
  { name: "Astoria Park", subtitle: "Queens", lat: 40.77800, lon: -73.93040 },
];

const NYU_BUILDINGS: FlyToSpot[] = [
  { name: "Bobst Library", subtitle: "Washington Sq S", lat: 40.72950, lon: -73.99800 },
  { name: "Stern School of Business", subtitle: "44 W 4th St", lat: 40.72939, lon: -73.99695 },
  { name: "Kimmel Center", subtitle: "60 Washington Sq S", lat: 40.72972, lon: -73.99842 },
  { name: "Silver Center", subtitle: "100 Washington Sq E", lat: 40.72997, lon: -73.99682 },
  { name: "Courant Institute", subtitle: "251 Mercer St", lat: 40.72874, lon: -73.99560 },
  { name: "Tandon (Brooklyn)", subtitle: "6 MetroTech Center", lat: 40.69440, lon: -73.98650 },
  { name: "NYU Langone Health", subtitle: "550 1st Ave", lat: 40.74220, lon: -73.97440 },
  { name: "Casa Italiana", subtitle: "24 W 12th St", lat: 40.73560, lon: -73.99650 },
];

const SAVES_KEY = "nbp_saves";

function loadSaves(): SavedBlock[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(SAVES_KEY) ?? "[]") as SavedBlock[];
  } catch {
    return [];
  }
}

function persistSaves(saves: SavedBlock[]): void {
  localStorage.setItem(SAVES_KEY, JSON.stringify(saves));
}

const SIGNAL_LABELS: Record<SignalName, string> = {
  construction: "Construction",
  nightlife: "Nightlife",
  housing: "Housing",
  restaurants: "Restaurants",
  quality_of_life: "Quality of life",
};

const SIGNAL_ORDER: SignalName[] = [
  "construction",
  "nightlife",
  "housing",
  "restaurants",
  "quality_of_life",
];

type BlockPanelProps = {
  report: BlockReport | null;
  isLoading?: boolean;
  error?: string | null;
  selectedSignal?: SignalName;
  onFlyTo: (lat: number, lon: number) => void;
};

function formatDate(value: string | null) {
  if (!value) return "unknown date";
  return value.slice(0, 10);
}

function scoreColorClass(score: number) {
  if (score >= 30) return "text-red-500";
  if (score >= 10) return "text-amber-500";
  return "text-emerald-500";
}

function AnimatedScore({ target }: { target: number }) {
  const [display, setDisplay] = useState(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    setDisplay(0);
    const start = performance.now();
    const duration = 700;
    const animate = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = target * eased;
      setDisplay(Number.isInteger(target) ? Math.round(val) : Math.round(val * 10) / 10);
      if (t < 1) frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target]);

  return (
    <span className={`tabular-nums ${scoreColorClass(target)}`}>{display}</span>
  );
}

function SpotRow({
  spot,
  onFlyTo,
  accent,
}: {
  spot: FlyToSpot;
  onFlyTo: (lat: number, lon: number) => void;
  accent?: "purple";
}) {
  return (
    <li className="flex items-center justify-between gap-2">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-neutral-900">
          {spot.name}
        </div>
        <div
          className={`text-xs ${accent === "purple" ? "text-purple-500" : "text-neutral-500"}`}
        >
          {spot.subtitle}
        </div>
      </div>
      <button
        onClick={() => onFlyTo(spot.lat, spot.lon)}
        className="shrink-0 text-neutral-400 transition-colors hover:text-neutral-900"
        aria-label={`Fly to ${spot.name}`}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M9 18l6-6-6-6" />
        </svg>
      </button>
    </li>
  );
}

export default function BlockPanel({
  report,
  isLoading = false,
  error,
  selectedSignal,
  onFlyTo,
}: BlockPanelProps) {
  const [saves, setSaves] = useState<SavedBlock[]>(() => loadSaves());

  const isSaved = report
    ? saves.some((s) => s.lat === report.location.lat && s.lon === report.location.lon)
    : false;

  function toggleSave() {
    if (!report) return;
    const label = `${report.location.lat.toFixed(5)}, ${report.location.lon.toFixed(5)}`;
    const next = isSaved
      ? saves.filter(
          (s) => !(s.lat === report.location.lat && s.lon === report.location.lon),
        )
      : [...saves, { label, lat: report.location.lat, lon: report.location.lon }];
    setSaves(next);
    persistSaves(next);
  }

  if (!report) {
    return (
      <aside className="flex h-full flex-col overflow-y-auto border-l border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 p-5">
          <h2 className="text-lg font-semibold text-neutral-950">Block Report</h2>
        </div>

        <div className="p-5 text-sm leading-6 text-neutral-600">
          <p className="font-medium text-neutral-950">
            Click the map or search an address
          </p>
          <p className="mt-1 text-xs">
            The five-signal report will appear here with nearby evidence from
            the selected 90-day window.
          </p>
          {isLoading ? (
            <p className="mt-3 text-neutral-500">Loading report...</p>
          ) : null}
          {error ? <p className="mt-3 text-red-700">{error}</p> : null}
        </div>

        <div className="border-t border-neutral-100 px-5 py-4">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            ★ Aru&apos;s Picks
          </div>
          <ul className="space-y-3">
            {ARU_PICKS.map((spot) => (
              <SpotRow key={spot.name} spot={spot} onFlyTo={onFlyTo} />
            ))}
          </ul>
        </div>

        <div className="border-t border-neutral-100 px-5 py-4">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-purple-500">
            ◆ NYU Buildings
          </div>
          <ul className="space-y-3">
            {NYU_BUILDINGS.map((spot) => (
              <SpotRow key={spot.name} spot={spot} onFlyTo={onFlyTo} accent="purple" />
            ))}
          </ul>
        </div>

        {saves.length > 0 && (
          <div className="border-t border-neutral-100 px-5 py-4">
            <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
              ♥ Your Saves
            </div>
            <ul className="space-y-3">
              {saves.map((s) => (
                <li key={`${s.lat},${s.lon}`} className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-neutral-900">
                      {s.label}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      onClick={() => onFlyTo(s.lat, s.lon)}
                      className="text-neutral-400 transition-colors hover:text-neutral-900"
                      aria-label="Fly to saved block"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        className="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M9 18l6-6-6-6" />
                      </svg>
                    </button>
                    <button
                      onClick={() => {
                        const next = saves.filter(
                          (x) => !(x.lat === s.lat && x.lon === s.lon),
                        );
                        setSaves(next);
                        persistSaves(next);
                      }}
                      className="text-neutral-400 transition-colors hover:text-red-500"
                      aria-label="Remove save"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        className="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M18 6L6 18M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    );
  }

  return (
    <aside className="flex h-full flex-col overflow-y-auto border-l border-neutral-200 bg-white">
      <div className="sticky top-0 z-10 border-b border-neutral-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-neutral-950">Block Report</h2>
        <div className="mt-3 space-y-1 text-sm text-neutral-600">
          <p>
            {report.location.lat.toFixed(5)}, {report.location.lon.toFixed(5)}
          </p>
          <p>
            {report.location.borough ?? "NYC"} {report.window_days} days{" "}
            {report.radius_ft} ft radius
          </p>
          {report.location.bbl || report.location.bin ? (
            <p className="text-xs text-neutral-500">
              {report.location.bbl ? `BBL ${report.location.bbl}` : null}
              {report.location.bbl && report.location.bin ? "  " : null}
              {report.location.bin ? `BIN ${report.location.bin}` : null}
            </p>
          ) : null}
        </div>
        {isLoading ? (
          <p className="mt-3 text-sm text-neutral-500">Updating...</p>
        ) : null}
        {error ? (
          <p className="mt-3 text-sm text-red-700">{error}</p>
        ) : null}
        <button
          onClick={toggleSave}
          className="mt-3 flex items-center gap-1.5 text-xs text-neutral-500 transition-colors hover:text-neutral-900"
          aria-label={isSaved ? "Remove bookmark" : "Save this block"}
        >
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill={isSaved ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 3h14a1 1 0 0 1 1 1v17l-8-4-8 4V4a1 1 0 0 1 1-1z" />
          </svg>
          {isSaved ? "Saved" : "Save this block"}
        </button>
      </div>

      <div className="space-y-4 p-5">
        {SIGNAL_ORDER.map((key) => {
          const signal = report.signals[key];
          const active = key === selectedSignal;
          const barWidth = Math.min(100, (signal.score / 50) * 100);
          return (
            <section
              key={key}
              id={`signal-${key}`}
              className={[
                "rounded border p-4 transition-colors",
                active
                  ? "border-neutral-950 bg-neutral-50"
                  : "border-neutral-200 bg-white",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-neutral-950">
                    {SIGNAL_LABELS[key]}
                  </h3>
                  <p className="mt-1 text-xs text-neutral-500">
                    {signal.signal_type.replaceAll("_", " ")}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-semibold">
                    <AnimatedScore target={signal.score} />
                  </div>
                  <div className="text-xs text-neutral-500">
                    {signal.count} events
                  </div>
                </div>
              </div>

              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    signal.score >= 30
                      ? "bg-red-400"
                      : signal.score >= 10
                        ? "bg-amber-400"
                        : "bg-emerald-400"
                  }`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>

              <div className="mt-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Evidence
                </div>
                {signal.evidence.length === 0 ? (
                  <p className="mt-2 text-sm text-neutral-500">
                    No nearby evidence found in this window.
                  </p>
                ) : (
                  <ul className="mt-2 space-y-3">
                    {signal.evidence.slice(0, 5).map((item, index) => (
                      <li
                        key={item.id ?? `${key}-${index}`}
                        className="text-sm leading-5 text-neutral-700"
                      >
                        <div className="text-xs text-neutral-500">
                          {formatDate(item.date)} via {item.source ?? "source"}
                        </div>
                        <div>{item.summary ?? item.id ?? "event"}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </aside>
  );
}
