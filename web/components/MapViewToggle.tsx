"use client";

export type MapViewMode = "events" | "demographics";

const MODES: Array<{ value: MapViewMode; label: string; tooltip: string }> = [
  {
    value: "events",
    label: "Activity",
    tooltip: "Recent events near each block — permits, complaints, crime, fires.",
  },
  {
    value: "demographics",
    label: "Population",
    tooltip: "Census demographics — density and 5-year change by tract.",
  },
];

type MapViewToggleProps = {
  mode: MapViewMode;
  onChange: (mode: MapViewMode) => void;
};

export default function MapViewToggle({ mode, onChange }: MapViewToggleProps) {
  return (
    <div className="w-[min(360px,calc(100vw-2rem))] rounded border border-neutral-200 bg-white/95 p-3 shadow-sm backdrop-blur">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Map
      </div>
      <div className="grid grid-cols-2 gap-2">
        {MODES.map((item) => {
          const active = item.value === mode;
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => onChange(item.value)}
              title={item.tooltip}
              className={[
                "min-h-9 rounded border px-3 text-sm font-medium transition",
                active
                  ? "border-neutral-950 bg-neutral-950 text-white"
                  : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-400",
              ].join(" ")}
              aria-pressed={active}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
