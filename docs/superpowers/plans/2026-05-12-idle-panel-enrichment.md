# Idle Panel Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the BlockPanel idle state with Aru's Picks, NYU Buildings, and a localStorage-backed Your Saves section, plus a bookmark toggle on loaded block reports.

**Architecture:** All changes are in two files — `BlockPanel.tsx` gets hardcoded data arrays, a new `onFlyTo` prop, localStorage save state, and the enriched idle layout; `page.tsx` passes `loadBlock` as `onFlyTo`. No backend changes.

**Tech Stack:** Next.js 14 App Router, React, TypeScript, Tailwind CSS, localStorage

---

## File Map

| File | Change |
|------|--------|
| `web/components/BlockPanel.tsx` | Add types, hardcoded data, `onFlyTo` prop, saves state, idle sections, bookmark button |
| `web/app/page.tsx` | Pass `loadBlock` as `onFlyTo` to BlockPanel |

---

### Task 1: Add data types, hardcoded arrays, and `onFlyTo` prop

**Files:**
- Modify: `web/components/BlockPanel.tsx`

- [ ] **Step 1: Add `FlyToSpot` type and `SavedBlock` type at the top of the file (after existing imports)**

Open `web/components/BlockPanel.tsx`. After the existing import block and before the `SIGNAL_LABELS` constant, add:

```ts
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
```

- [ ] **Step 2: Add `ARU_PICKS` array after the two new types**

```ts
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
```

- [ ] **Step 3: Add `NYU_BUILDINGS` array immediately after `ARU_PICKS`**

```ts
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
```

- [ ] **Step 4: Add localStorage helpers after the arrays**

```ts
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
```

- [ ] **Step 5: Add `onFlyTo` to `BlockPanelProps`**

Find the existing `BlockPanelProps` type:
```ts
type BlockPanelProps = {
  report: BlockReport | null;
  isLoading?: boolean;
  error?: string | null;
  selectedSignal?: SignalName;
};
```

Replace it with:
```ts
type BlockPanelProps = {
  report: BlockReport | null;
  isLoading?: boolean;
  error?: string | null;
  selectedSignal?: SignalName;
  onFlyTo: (lat: number, lon: number) => void;
};
```

- [ ] **Step 6: Add `saves` state to the component**

Find the `export default function BlockPanel({` line. Update the destructured props and add state:

```ts
export default function BlockPanel({
  report,
  isLoading = false,
  error,
  selectedSignal,
  onFlyTo,
}: BlockPanelProps) {
  const [saves, setSaves] = useState<SavedBlock[]>(() => loadSaves());
```

The existing `useEffect`, `useRef`, etc. from `AnimatedScore` are in a separate component — `BlockPanel` itself currently has no state. Add this `useState` as the first line inside the `BlockPanel` function body (after the opening brace).

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit
```

Expected: no errors (the prop is added but not yet used in JSX — that's fine at this stage).

- [ ] **Step 8: Commit**

```bash
git add web/components/BlockPanel.tsx
git commit -m "feat: add FlyToSpot/SavedBlock types, hardcoded data, onFlyTo prop"
```

---

### Task 2: Build the shared spot-row component and idle section layout

**Files:**
- Modify: `web/components/BlockPanel.tsx`

- [ ] **Step 1: Add `SpotRow` helper component**

Add this above `export default function BlockPanel` (and below `AnimatedScore`):

```tsx
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
```

- [ ] **Step 2: Replace the idle-state return in `BlockPanel`**

Find the `if (!report)` block which currently returns:
```tsx
if (!report) {
  return (
    <aside className="flex h-full flex-col overflow-y-auto border-l border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 p-5">
        <h2 className="text-lg font-semibold text-neutral-950">
          Block Report
        </h2>
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
```

Replace it entirely with:
```tsx
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
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/components/BlockPanel.tsx
git commit -m "feat: idle panel — Aru's Picks, NYU Buildings, Your Saves sections"
```

---

### Task 3: Add bookmark toggle to the report state header

**Files:**
- Modify: `web/components/BlockPanel.tsx`

- [ ] **Step 1: Add `isSaved` derived value and `toggleSave` function inside `BlockPanel`**

After the `const [saves, setSaves] = useState<SavedBlock[]>(() => loadSaves());` line, add:

```ts
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
```

- [ ] **Step 2: Add bookmark button to the report header**

Find the sticky header in the report return — the `<div className="sticky top-0 z-10 ...">` block. It currently ends with the error/loading paragraphs. Add the bookmark button as the last child inside the sticky div, after the `{error ? ... : null}` line:

```tsx
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
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/components/BlockPanel.tsx
git commit -m "feat: bookmark toggle on block report header"
```

---

### Task 4: Wire `onFlyTo` in page.tsx

**Files:**
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Pass `loadBlock` as `onFlyTo` to `BlockPanel`**

Find the `<BlockPanel` usage in `page.tsx`:
```tsx
<BlockPanel
  report={report}
  isLoading={isBlockLoading}
  error={panelError}
  selectedSignal={signal}
/>
```

Replace with:
```tsx
<BlockPanel
  report={report}
  isLoading={isBlockLoading}
  error={panelError}
  selectedSignal={signal}
  onFlyTo={loadBlock}
/>
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat: wire onFlyTo to loadBlock in page.tsx"
```

---

### Task 5: Manual verification

- [ ] **Step 1: Start the dev server**

```bash
cd web && npm run dev
```

Open `http://localhost:3000`.

- [ ] **Step 2: Idle state — Aru's Picks**

With no block selected, verify:
- "★ Aru's Picks" section is visible with all 11 entries
- Each row shows name + neighborhood
- Click "Washington Square Park" → map flies to Greenwich Village, block report loads
- Panel switches from idle to report view

- [ ] **Step 3: Idle state — NYU Buildings**

- "◆ NYU Buildings" section is visible with all 8 entries
- Subtitle text is purple
- Click "NYU Langone Health" → map flies to 550 1st Ave area, block report loads

- [ ] **Step 4: Save mechanic**

- Load any block by clicking map
- Bookmark button appears in sticky header with "Save this block" label
- Click it → icon fills, label changes to "Saved"
- Navigate away (click somewhere else) → panel shows report for new location
- Click back arrow in browser (no back arrow in app — just open idle state by... hmm, there's no "clear" button. Refresh page to get idle state)
- After refresh, "♥ Your Saves" section appears with the saved block's coords
- Click the → chevron → flies to and loads that block
- Click × → entry disappears, localStorage is updated

- [ ] **Step 5: Your Saves persistence**

- Save two blocks
- Refresh the page
- "♥ Your Saves" still shows both entries

- [ ] **Step 6: No saves — section hidden**

- Open DevTools → Application → Local Storage → delete `nbp_saves` key
- Refresh → "Your Saves" section is gone entirely

- [ ] **Step 7: Commit final state if any tweaks were made**

```bash
git add -p
git commit -m "fix: idle panel polish from manual testing"
```
