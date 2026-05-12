# Idle Panel Enrichment — Design Spec
_Date: 2026-05-12_

## Problem

The BlockPanel right sidebar is mostly empty when no block has been selected. It wastes ~60% of the panel height and gives new visitors no starting point.

## Goal

Fill the idle state with three useful sections that double as navigation shortcuts: Aru's curated picks, NYU building locations, and the user's own saved blocks. Once a block is selected the panel switches to the normal report view — no change to that experience.

## Out of scope

- Reverse geocoding saved block labels (use coords for now, improve later)
- NYU purple marker pins on the map (separate PR)
- Any backend / auth changes

---

## Data

Two hardcoded arrays at the top of `BlockPanel.tsx`:

```ts
ARU_PICKS: { name: string; neighborhood: string; lat: number; lon: number }[]
NYU_BUILDINGS: { name: string; lat: number; lon: number }[]
```

**Aru's Picks** (11 entries):
| Name | Neighborhood | Lat | Lon |
|------|-------------|-----|-----|
| Washington Square Park | Greenwich Village | 40.73082 | -73.99763 |
| Apollo Bagels | West Village | 40.72941 | -74.00277 |
| NYU Langone Health | Murray Hill | 40.74220 | -73.97440 |
| DUMBO | Brooklyn | 40.70338 | -73.98930 |
| NYU 404 | NoHo | 40.72952 | -73.99585 |
| Bensonhurst Park | Brooklyn | 40.60526 | -74.00910 |
| Domino Park | Williamsburg | 40.71503 | -73.96590 |
| Hunters Point | LIC, Queens | 40.74480 | -73.94860 |
| The High Line | Chelsea | 40.74800 | -74.00480 |
| Katz's Delicatessen | Lower East Side | 40.72228 | -73.98737 |
| Astoria Park | Queens | 40.77800 | -73.93040 |

**NYU Buildings** (8 entries):
| Name | Lat | Lon |
|------|-----|-----|
| Bobst Library | 40.72950 | -73.99800 |
| Stern School of Business | 40.72939 | -73.99695 |
| Kimmel Center | 40.72972 | -73.99842 |
| Silver Center | 40.72997 | -73.99682 |
| Courant Institute | 40.72874 | -73.99560 |
| Tandon (Brooklyn) | 40.69440 | -73.98650 |
| NYU Langone Health | 40.74220 | -73.97440 |
| Casa Italiana | 40.73560 | -73.99650 |

---

## Component changes

### `BlockPanel.tsx`

**New prop:**
```ts
onFlyTo: (lat: number, lon: number) => void;
```

**Idle state layout** (rendered when `report === null`):

```
┌─────────────────────────────┐
│ Block Report                 │  ← existing header
├─────────────────────────────┤
│ Click the map or search…     │  ← existing intro text
├─────────────────────────────┤
│  ★  Aru's Picks              │  ← section header
│  Washington Square Park      │
│  Greenwich Village      [→]  │  ← button calls onFlyTo(lat, lon)
│  Apollo Bagels               │
│  West Village           [→]  │
│  …                           │
├─────────────────────────────┤
│  ◆  NYU Buildings            │  ← section header (purple accent)
│  Bobst Library          [→]  │
│  Stern School           [→]  │
│  …                           │
├─────────────────────────────┤
│  ♥  Your Saves               │  ← only renders if saves.length > 0
│  40.73082, -73.99763    [×]  │  ← × removes from saves
│  …                           │
└─────────────────────────────┘
```

**Report state** (rendered when `report !== null`):

A bookmark icon button (outline = unsaved, filled = saved) is added to the sticky header row alongside the existing coordinate/borough info. Clicking it toggles save state.

**localStorage mechanics:**
- Key: `"nbp_saves"`
- Value: `JSON.stringify(SavedBlock[])` where `SavedBlock = { label: string; lat: number; lon: number }`
- Label format: `"${lat.toFixed(5)}, ${lon.toFixed(5)}"` (good enough until reverse geocoding lands)
- State initialized from localStorage on mount via `useState(() => loadSaves())`
- Writes to localStorage on every toggle (small payload, fine to write synchronously)

### `page.tsx`

Pass `loadBlock` as `onFlyTo` to `BlockPanel`:
```tsx
<BlockPanel
  report={report}
  isLoading={isBlockLoading}
  error={panelError}
  selectedSignal={signal}
  onFlyTo={loadBlock}   // ← new
/>
```

`loadBlock` already handles fly-to + report fetch, so no new logic needed.

---

## Visual design

- Section headers: `text-xs font-semibold uppercase tracking-wide text-neutral-500` (matches existing Evidence header style)
- Row item: two-line — name in `text-sm font-medium text-neutral-900`, subtitle in `text-xs text-neutral-500`
- Arrow button: small `text-neutral-400 hover:text-neutral-900` chevron-right or →
- NYU section accent: `text-purple-600` diamond (◆) in header
- Saves remove button: `text-neutral-400 hover:text-red-500` ×
- Dividers between sections: `border-t border-neutral-100`

---

## Testing

Manual:
1. Load app with no localStorage — idle panel shows Aru's Picks + NYU Buildings, no Saves section
2. Click any pick → map flies to location, block report loads in panel
3. Click bookmark on loaded report → icon fills, appears in Your Saves on next idle view
4. Remove a save → disappears from list, localStorage updated
5. Refresh page → saves persist

---

## Files changed

| File | Change |
|------|--------|
| `web/components/BlockPanel.tsx` | Idle state sections, save/unsave logic, `onFlyTo` prop |
| `web/app/page.tsx` | Pass `loadBlock` as `onFlyTo` |
