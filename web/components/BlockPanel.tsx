"use client";

import type { BlockReport, SignalName } from "@/lib/types";

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
};

function formatDate(value: string | null) {
  if (!value) {
    return "unknown date";
  }
  return value.slice(0, 10);
}

export default function BlockPanel({
  report,
  isLoading = false,
  error,
  selectedSignal,
}: BlockPanelProps) {
  if (!report) {
    return (
      <aside className="flex h-full flex-col overflow-y-auto border-l border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 p-5">
          <h2 className="text-lg font-semibold text-neutral-950">Block Report</h2>
        </div>
        <div className="flex flex-1 flex-col justify-center p-6 text-sm leading-6 text-neutral-600">
          <p className="text-base font-medium text-neutral-950">
            Click the map or search an address
          </p>
          <p className="mt-2">
            The five-signal report will appear here with nearby evidence from
            the selected 90-day window.
          </p>
          {isLoading ? (
            <p className="mt-4 text-neutral-500">Loading report...</p>
          ) : null}
          {error ? <p className="mt-4 text-red-700">{error}</p> : null}
        </div>
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
            {report.location.borough ?? "NYC"} · {report.window_days} days ·{" "}
            {report.radius_ft} ft
          </p>
          {report.location.bbl || report.location.bin ? (
            <p className="text-xs text-neutral-500">
              {report.location.bbl ? `BBL ${report.location.bbl}` : null}
              {report.location.bbl && report.location.bin ? " · " : null}
              {report.location.bin ? `BIN ${report.location.bin}` : null}
            </p>
          ) : null}
        </div>
        {isLoading ? <p className="mt-3 text-sm text-neutral-500">Updating...</p> : null}
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      </div>

      <div className="space-y-4 p-5">
        {SIGNAL_ORDER.map((key) => {
          const signal = report.signals[key];
          const active = key === selectedSignal;
          return (
            <section
              key={key}
              id={`signal-${key}`}
              className={[
                "rounded border p-4",
                active ? "border-neutral-950 bg-neutral-50" : "border-neutral-200 bg-white",
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
                  <div className="text-2xl font-semibold text-neutral-950">
                    {signal.score}
                  </div>
                  <div className="text-xs text-neutral-500">
                    {signal.count} events
                  </div>
                </div>
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
                          {formatDate(item.date)} · {item.source ?? "source"}
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
