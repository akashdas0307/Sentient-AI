# Phase 11 — Frontend Redesign Migration Plan (D0)

**Branch:** `auto/phase-11-frontend-redesign`
**Date:** 2026-04-20
**Status:** READY

---

## 1. Design Bundle Inventory

### Source: `/frontend/Sentient-design-files-by/`

| File | Purpose | Size |
|------|---------|------|
| `Sentient.html` | Entry point: React 18 + Babel standalone app shell | Main |
| `tokens.css` | OKLCH design tokens, typography, animations | ~3KB |
| `components/shared.jsx` | NavContext, CmdContext, Icons (18 SVG), Sparkline, Pill, Card, StatCard, Btn, GaugeBar, Skeleton, ToastProvider, CommandPalette, Sidebar, Header | ~23KB |
| `components/chat.jsx` | Chat + Monologue panels, resizable split, scroll management, type-colored thoughts | ~20KB |
| `components/modules.jsx` | Module stat cards, pulse rate bar chart, module grid with sparklines | ~7KB |
| `components/memory.jsx` | Memory search, type pills, importance filter, detail rail | ~12KB |
| `components/graph.jsx` | Canvas-based force graph, edge types (entity/topic/temporal), filters, detail rail | ~30KB |
| `components/sleep.jsx` | Stage timeline (hypnogram SVG), consolidation bar chart, history feed | ~19KB |
| `components/events.jsx` | Live events stream, filters (time/type/module/severity), pause/resume | ~12KB |
| `components/gateway.jsx` | Model health gauges, recent calls stream, outcome pills | ~9KB |
| `components/identity.jsx` | Maturity stage arc, constitutional core, traits + drift, dynamic gauges | ~9KB |

### Component System
- **No external UI library** — pure React with inline `style={{}}` props
- **No Tailwind** — all styling via CSS custom properties + inline styles
- **No shadcn/ui** — all primitives defined in `shared.jsx`
- **No framer-motion** — CSS transitions and keyframe animations only
- **No recharts** — custom Sparkline SVG, canvas rendering for graph
- **No lucide-react** — 18 hand-drawn SVG icons in `shared.jsx`
- **Font:** IBM Plex Mono (Google Fonts import or `@fontsource/ibm-plex-mono`)

### Design Tokens (`tokens.css`)
```
--background: oklch(0.10 0 0)
--surface: oklch(0.14 0.005 40)
--surface-secondary: oklch(0.17 0.008 40)
--surface-tertiary: oklch(0.20 0.010 40)
--border: oklch(0.25 0.010 40)
--border-strong: oklch(0.35 0.015 40)
--foreground: oklch(0.92 0.010 40)
--muted-foreground: oklch(0.60 0.020 40)
--subtle-foreground: oklch(0.45 0.015 40)
--primary: oklch(0.6678 0.2232 36.66)        /* Amber */
--primary-foreground: oklch(0.12 0 0)
--primary-subtle: oklch(0.6678 0.2232 36.66 / 0.10)
--success: oklch(0.73 0.19 150)               /* Green */
--warning: oklch(0.78 0.16 72)                 /* Yellow */
--destructive: oklch(0.65 0.23 26)             /* Red */
--accent: oklch(0.70 0.18 280)                 /* Purple */
--overlay: oklch(0 0 0 / 0.6)
--radius-sm/1rem/radius-lg/radius-xl
Typography: .t-display/.t-h1/.t-h2/.t-body/.t-small/.t-label/.t-code
Animations: pulse-amber, spin-stepped, shimmer, bounce-dots
```

---

## 2. Route Mapping (8 routes — all preserved)

| Route | Current Page | Design Page | Migration |
|-------|--------------|-------------|-----------|
| `/` | `ChatPage.tsx` | `chat.jsx` | D2 — full rewrite |
| `/modules` | `ModulesPage.tsx` | `modules.jsx` | D3 — full rewrite |
| `/memory` | `MemoryPage.tsx` | `memory.jsx` | D4a — full rewrite |
| `/graph` | `MemoryGraphPage.tsx` | `graph.jsx` | D4b — full rewrite |
| `/sleep` | `SleepPage.tsx` | `sleep.jsx` | D5a — full rewrite + §4.4 button |
| `/events` | `EventsPage.tsx` | `events.jsx` | D5b — full rewrite |
| `/gateway` | `GatewayPage.tsx` | `gateway.jsx` | D6a — full rewrite |
| `/identity` | `IdentityPage.tsx` | `identity.jsx` | D6b — full rewrite |

### Shell Components (D1)
| Component | Current | Design | Action |
|-----------|---------|--------|--------|
| Sidebar | `DashboardLayout.tsx` (Tailwind + shadcn Button) | `shared.jsx` Sidebar (inline styles, custom icons) | Replace |
| Header | `DashboardLayout.tsx` inline header | `shared.jsx` Header (page title + ⌘K + version + health + connected pills) | Replace |
| CommandPalette | Does not exist | `shared.jsx` CommandPalette (⌘K fuzzy search) | New |
| Toast | Does not exist | `shared.jsx` ToastProvider (auto-dismiss 4s) | New |

---

## 3. Files to Replace vs Keep

### REPLACE (full rewrite to match design)
- `src/App.tsx` — remove Tailwind wrapper, add NavContext/CmdContext/ToastProvider
- `src/App.css` — replace with `tokens.css` content
- `src/layouts/DashboardLayout.tsx` — replaced by inline shell in App.tsx
- `src/pages/ChatPage.tsx` — full rewrite
- `src/pages/ModulesPage.tsx` — full rewrite
- `src/pages/MemoryPage.tsx` — full rewrite
- `src/pages/MemoryGraphPage.tsx` — full rewrite (canvas + force sim)
- `src/pages/SleepPage.tsx` — full rewrite
- `src/pages/EventsPage.tsx` — full rewrite
- `src/pages/GatewayPage.tsx` — full rewrite
- `src/pages/IdentityPage.tsx` — full rewrite
- `src/components/` — all current components replaced by design primitives

### KEEP (preservation contract §2)
- `src/store/useSentientStore.ts` — Zustand store shape unchanged
- `src/types/index.ts` — all type interfaces unchanged
- `src/types/gateway.ts` — gateway types unchanged
- `src/hooks/useWebSocket.ts` — WebSocket hook unchanged
- `src/main.tsx` — entry point (minor: add tokens.css import)
- `src/lib/utils.ts` — `cn()` utility (remove if no longer needed, or keep for conditional classes)

### DELETE (no longer needed after migration)
- `src/components/ui/` — all 9 shadcn components (badge, button, card, input, scroll-area, select, separator, sheet, tooltip)
- `src/design/` — any design token files that overlap with `tokens.css`
- `tailwind.config.*` — if exists
- `postcss.config.*` — if exists (Vite 6 handles CSS natively)

---

## 4. Package Changes

### REMOVE from `package.json`
```
@base-ui/react          # Replaced by inline style primitives
@fontsource-variable/geist  # Replaced by IBM Plex Mono
class-variance-authority    # No more cva-based variants
clsx                        # No more className merging
tailwind-merge              # No more Tailwind
tw-animate-css              # No more Tailwind animations
shadcn                      # No more shadcn components
framer-motion               # Replaced by CSS transitions
lucide-react                # Replaced by inline SVG icons
recharts                    # Replaced by custom SVG charts
@xyflow/react               # Replaced by canvas-based graph
```

### ADD to `package.json`
```
@fontsource/ibm-plex-mono   # IBM Plex Mono font (self-hosted, no Google CDN)
```

### REMOVE from `devDependencies`
```
@tailwindcss/vite           # No more Tailwind
tailwindcss                 # No more Tailwind
autoprefixer                # No more PostCSS autoprefixer
postcss                     # No more PostCSS
```

### KEEP
```
react, react-dom, react-router, zustand, vite, typescript, @vitejs/plugin-react
```

---

## 5. CSS Token Merge Strategy

### Strategy: **Full replacement** — not merge

The current frontend uses Tailwind's dark theme utility classes. The design bundle uses OKLCH CSS custom properties with inline styles. These are incompatible systems — a merge would create a confusing hybrid.

**Steps:**
1. Delete `src/App.css` (Tailwind directives + any custom styles)
2. Create `src/styles/tokens.css` with the full contents of `tokens.css`
3. Import `tokens.css` in `src/main.tsx` before App
4. Remove `@tailwindcss/vite` plugin from `vite.config.ts`
5. Remove `tailwind.config.*` and `postcss.config.*` if they exist
6. All component styling uses `style={{}}` with `var(--token)` references

### Global styles to preserve from current code:
- `html, body, #root { height: 100%; overflow: hidden; }` — already in `tokens.css`
- Scrollbar styling — already in `tokens.css`
- Focus rings — already in `tokens.css`

---

## 6. Behavioral Fixes Mapping (§4.1–§4.6)

| Fix | Status in Design | Implementation Notes |
|-----|-------------------|---------------------|
| §4.1 Scroll hijack | **Already in design** | `chat.jsx` has `isNearBottom`, `handleMsgScroll`, `newMsgCount` pills. Convert to TS with Zustand data. |
| §4.2 Memory graph edges | **Already in design** | `graph.jsx` has 3 edge types (entity/topic/temporal) with distinct dash patterns. Convert canvas code to TS. |
| §4.3 Events filter+scroll | **Already in design** | `events.jsx` has time range, type/module/severity filters, pause/resume with buffered count. Convert to TS. |
| §4.4 Sleep dev-mode button | **NOT in design** | Must add "Force Sleep Cycle" button to `SleepPage.tsx`. Wire to POST `/api/sleep/cycle`. |
| §4.5 Timestamp normalization | **Applies across all pages** | All timestamps must use consistent `toLocaleTimeString` with tabular-nums. Design uses this pattern already. Enforce in shared util. |
| §4.6 Daydream vs reasoning | **Design uses `type` field** | Design `chat.jsx` MonologuePanel uses `type` (perception/reasoning/memory-fetch/daydream/decision) with distinct colors. Current store uses `is_daydream: boolean`. Need adapter: `is_daydream ? 'daydream' : 'reasoning'`. |

---

## 7. MonologueEntry Type Adaptation (§4.6)

**Current type:**
```typescript
interface MonologueEntry {
  id: string;
  monologue: string;
  is_daydream: boolean;   // ← boolean
  decision_count: number;
  duration_ms: number | null;
  timestamp: number;
}
```

**Design expects `type` field:** `perception | reasoning | memory-fetch | daydream | decision`

**Adapter strategy (no store change — preservation contract §2):**
```typescript
// In MonologuePanel component, map boolean to type string:
const entryType = entry.is_daydream ? 'daydream' : 'reasoning';
```

The store's `is_daydream: boolean` is PRESERVED. The UI component maps it to the design's type system locally. No store schema change needed.

---

## 8. Per-Page Migration Order

Matching the D2–D9 deliverable sequence:

### D1 — Global Shell (Day 1)
1. Create `src/styles/tokens.css`
2. Rewrite `src/App.tsx` — NavContext, CmdContext, ToastProvider, Sidebar, Header, CommandPalette, Routes
3. Delete `src/layouts/DashboardLayout.tsx`
4. Delete `src/components/ui/` (all shadcn)
5. Delete `src/components/` legacy (ChatPanel, EventsPanel, etc.)
6. Update `src/main.tsx` — import tokens.css
7. Update `vite.config.ts` — remove Tailwind plugin
8. Update `package.json` — remove/add deps, run `npm install`

### D2 — Chat + Monologue (Day 2)
1. Rewrite `src/pages/ChatPage.tsx` from `chat.jsx`
2. Implement §4.1 scroll behavior
3. Implement §4.6 type mapping adapter
4. Wire to `useSentientStore` (messages, monologueEntries, sendChat)

### D3 — Modules (Day 2)
1. Rewrite `src/pages/ModulesPage.tsx` from `modules.jsx`
2. Wire to `useSentientStore` (healthSnapshot)

### D4 — Memory + Graph (Day 3)
1. Rewrite `src/pages/MemoryPage.tsx` from `memory.jsx`
2. Rewrite `src/pages/MemoryGraphPage.tsx` from `graph.jsx`
3. Implement §4.2 edge types (entity/topic/temporal)

### D5 — Sleep + Events (Day 3)
1. Rewrite `src/pages/SleepPage.tsx` from `sleep.jsx`
2. Add §4.4 "Force Sleep Cycle" dev-mode button (POST `/api/sleep/cycle`)
3. Rewrite `src/pages/EventsPage.tsx` from `events.jsx`
4. Implement §4.3 filter expansion + scroll

### D6 — Gateway + Identity (Day 4)
1. Rewrite `src/pages/GatewayPage.tsx` from `gateway.jsx`
2. Wire to `useSentientStore` (gatewayStatus, gatewayCalls)
3. Rewrite `src/pages/IdentityPage.tsx` from `identity.jsx`

### D7 — Timestamp Normalization (Day 4)
1. Create `src/lib/format.ts` with shared `formatTimestamp()`, `formatRelative()`, `formatDuration()`
2. Audit all pages for inconsistent timestamp formatting
3. Replace inline formatting with shared util

### D8 — Polish (Day 4)
1. Responsive layout audit
2. Keyboard navigation (focus rings from tokens.css)
3. Loading states (Skeleton from shared.jsx)
4. Animation tuning (CSS transitions, keyframes)
5. Remove any leftover Tailwind class references

### D9 — Playwright E2E (Day 5)
1. 8 new e2e specs (one per route)
2. Smoke tests: page renders, WebSocket connects, data flows
3. Behavioral tests: §4.1 scroll, §4.3 filters, §4.4 force sleep
4. Cross-browser: Chromium only (not a multi-browser requirement)

---

## 9. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Removing Tailwind + shadcn breaks all existing styling | Expected — full UI replacement. D1 creates the new shell first. |
| Canvas graph (`graph.jsx`) performance | Design already uses requestAnimationFrame with cooling. Port as-is. |
| `@xyflow/react` removal loses React Flow graph | Design uses custom canvas force graph — different paradigm, intentional replacement. |
| `framer-motion` removal loses page transitions | Replace with CSS `transition: opacity 200ms` on route change. |
| Google Fonts CDN dependency | Use `@fontsource/ibm-plex-mono` npm package for self-hosting. |
| Large diff (>300 lines per deliverable) | Each D-deliverable is a full page rewrite. Expected. Keep commits atomic per deliverable. |
| Store shape must not change | All pages adapt to existing store. Only UI layer changes. |

---

## 10. Verification Checklist (per deliverable)

- [ ] Page renders without console errors
- [ ] WebSocket data populates from `useSentientStore`
- [ ] No Tailwind classes remain in the file
- [ ] All CSS uses `var(--token)` or inline styles
- [ ] TypeScript compiles (`tsc --noEmit`)
- [ ] Behavioral fix verified (if applicable)
- [ ] No new package dependencies beyond `@fontsource/ibm-plex-mono`

---

## 11. Commit Plan

| Commit | Scope | Message Pattern |
|--------|-------|----------------|
| D0 | This plan | `docs(phase-11-D0): migration plan` |
| D1 | Shell + tokens + deps | `feat(phase-11-D1): global shell redesign — tokens, sidebar, header, command palette` |
| D2 | Chat + Monologue | `feat(phase-11-D2): chat + monologue redesign with scroll fix (§4.1, §4.6)` |
| D3 | Modules | `feat(phase-11-D3): modules page redesign` |
| D4 | Memory + Graph | `feat(phase-11-D4): memory + graph redesign with edge types (§4.2)` |
| D5 | Sleep + Events | `feat(phase-11-D5): sleep + events redesign with force sleep (§4.4) and filters (§4.3)` |
| D6 | Gateway + Identity | `feat(phase-11-D6): gateway + identity redesign` |
| D7 | Timestamps | `fix(phase-11-D7): timestamp normalization across all pages (§4.5)` |
| D8 | Polish | `feat(phase-11-D8): responsive, keyboard, loading states, animation polish` |
| D9 | Playwright | `test(phase-11-D9): e2e specs for 8 routes + behavioral fixes` |