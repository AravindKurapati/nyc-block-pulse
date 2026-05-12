"use client";

import type { SignalName } from "@/lib/types";

const SIGNALS: Array<{ value: SignalName; label: string }> = [
  { value: "quality_of_life", label: "Quality of life" },
  { value: "nightlife", label: "Nightlife" },
  { value: "construction", label: "Construction" },
  { value: "housing", label: "Housing" },
  { value: "restaurants", label: "Restaurants" },
];

type SignalToggleProps = {
  signal: SignalName;
  onChange: (signal: SignalName) => void;
};

export default function SignalToggle({ signal, onChange }: SignalToggleProps) {
  return (
    <div className="w-[min(520px,calc(100vw-2rem))] rounded border border-neutral-200 bg-white/95 p-3 shadow-sm backdrop-blur">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Signal
      </div>
      <div className="flex flex-wrap gap-2">
        {SIGNALS.map((item) => {
          const active = item.value === signal;
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => onChange(item.value)}
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
