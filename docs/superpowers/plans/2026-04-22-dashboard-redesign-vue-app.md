# Dashboard Redesign — Vue App Implementation Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vue 3 single-page dashboard that reads a versioned JSON snapshot of the portfolio (produced by Plan A) and renders a modern, light, card-based view of positions, trades, today's plan, Claude's briefing, and performance statistics. The application is a pure static site, ready to be deployed to Cloudflare Pages in a later phase without code changes.

**Architecture:** One Vue 3 + Vite + TypeScript project. Tailwind CSS for styling with a small set of semantic color tokens. Chart.js for the donut and equity line charts, loaded as a module (not via CDN). A single `useData` composable owns loading, error, and schema-mismatch state; every visible section is a component that takes its slice of the data as props and renders statelessly. Vitest plus Vue Test Utils for tests. The sibling Python repository writes `public/data.json` into this project's public folder; during development the developer uses a committed fixture file.

**Tech Stack:** Node 18+, npm, Vite, Vue 3, TypeScript, Tailwind CSS, Chart.js, Vitest, Vue Test Utils, jsdom.

**Companion Plan:** Plan A produces the `data.json` this application consumes. This plan only depends on the schema locked in the Design Spec; it can be executed in parallel with Plan A once the contract is understood.

---

## Prerequisites

Before starting, confirm the following are true. If any are not, address them first.

- Node 18 or newer is available: running `node --version` returns a version at or above v18
- npm is available: `npm --version` returns a version at or above v9
- git is configured with the name and email you want to author these commits under
- A GitHub account exists under which a new repository called `investmentAgentDashboard` can be created
- The Design Spec at `docs/superpowers/specs/2026-04-22-dashboard-redesign-design.md` in the main repo has been read and the JSON contract it defines is understood
- The parent directory where the new repo will live (`~/Desktop/local/Learn/Local_Dev/`) is writable

---

## File Structure

All paths below are relative to the new `investmentAgentDashboard` repository root, which will live at `~/Desktop/local/Learn/Local_Dev/investmentAgentDashboard`.

**Top-level configuration files created by scaffolding and manual setup:**
- `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts`, `vitest.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `index.html`, `.gitignore`, `.nvmrc`, `README.md`, `LICENSE` (MIT)

**Source tree under `src/`:**
- `src/main.ts` — mounts the root component into `#app`
- `src/App.vue` — root layout, wires the data composable, handles loading and error states, composes every visible section
- `src/composables/useData.ts` — fetches `/data.json`, exposes reactive `data`, `loading`, `error`, `schemaMismatch`, and a manual `reload` function
- `src/types/data.ts` — TypeScript interface describing the JSON contract top-to-bottom, matching the Design Spec
- `src/utils/format.ts` — `formatCurrency`, `formatPercent`, `formatSignedPercent`, `formatDate`
- `src/utils/csv.ts` — `tradesToCSV(trades)` returns a CSV string, plus `downloadCSV(filename, content)` triggers a browser download
- `src/components/DashboardHeader.vue`
- `src/components/HeroCard.vue`
- `src/components/EquityChart.vue`
- `src/components/AllocationPanel.vue`
- `src/components/TodayPlan.vue`
- `src/components/BriefingCard.vue`
- `src/components/TradeHistory.vue`
- `src/components/FilterTabs.vue`
- `src/components/TradeRow.vue`
- `src/components/PerTickerGroup.vue`
- `src/components/StatsGrid.vue`
- `src/components/DashboardFooter.vue`
- `src/style.css` — one Tailwind entrypoint plus a handful of base rules (system font stack, tabular-nums for numeric spans)

**Tests under `tests/`:**
- `tests/utils/format.spec.ts`
- `tests/utils/csv.spec.ts`
- `tests/composables/useData.spec.ts`
- `tests/components/HeroCard.spec.ts`
- `tests/components/AllocationPanel.spec.ts`
- `tests/components/TradeHistory.spec.ts`
- `tests/components/StatsGrid.spec.ts`
- `tests/fixtures/data.valid.ts` — a typed fixture matching the contract, used across component tests
- `tests/fixtures/data.empty.ts` — minimal fixture representing a brand-new portfolio (no trades, no snapshots)

**Public assets:**
- `public/data.json` — the committed fixture / snapshot. This file is the contract between the two repos. In development and production, the application fetches it from the same origin.
- `public/favicon.svg` — a simple placeholder favicon (a dollar sign glyph)

---

## Task 1: Scaffold the Vite + Vue 3 + TypeScript project

**Files:**
- Create: the entire repository at `~/Desktop/local/Learn/Local_Dev/investmentAgentDashboard`

- [ ] **Step 1: Run the Vite scaffolder**

From the parent directory `~/Desktop/local/Learn/Local_Dev/`, run `npm create vite@latest investmentAgentDashboard -- --template vue-ts`. Accept the defaults. When the scaffolder finishes, change into the new directory and run `npm install`.

- [ ] **Step 2: Verify the starter app builds and runs**

Run `npm run dev`. Expected: Vite serves on a local port (typically 5173); opening it in a browser shows the starter Vue template. Stop the dev server with Ctrl+C. Run `npm run build`. Expected: a `dist/` folder is produced without errors. Run `npm run preview` briefly to confirm the production build serves correctly, then stop it.

- [ ] **Step 3: Replace the starter README with a project-specific one**

Overwrite `README.md` with content covering: project purpose (the dashboard companion to the investment agent), how to run `npm run dev`, how the `public/data.json` file is the input contract, a pointer to the Design Spec in the sibling main repository, and the commands `npm run dev`, `npm run build`, `npm run preview`, and `npm test`.

- [ ] **Step 4: Add a Node version pin**

Create `.nvmrc` containing just the major Node version in use (for example `18`). This helps collaborators match your environment.

- [ ] **Step 5: Remove starter artifacts**

Delete `src/components/HelloWorld.vue`, `src/assets/vue.svg`, and `public/vite.svg`. Empty `src/App.vue` to a minimal root containing just `<template><div id="app">Dashboard</div></template><script setup lang="ts"></script>`. Keep `src/main.ts` as scaffolded.

- [ ] **Step 6: Initialize git and make the first commit**

Run `git init`. Stage everything, commit with message `chore: scaffold Vue 3 + Vite + TypeScript project`.

- [ ] **Step 7: Create the GitHub repository and push**

Create a new private repository on GitHub named `investmentAgentDashboard` under your account. Add it as the remote origin: `git remote add origin https://github.com/<user>/investmentAgentDashboard.git`. Push: `git push -u origin master` (or `main`, whichever the scaffolder produced).

---

## Task 2: Install and configure Tailwind CSS

**Files:**
- Create: `tailwind.config.ts`, `postcss.config.js`
- Modify: `src/style.css`, `src/main.ts`

- [ ] **Step 1: Install dependencies**

Run `npm install -D tailwindcss postcss autoprefixer @types/node`. Initialize Tailwind by running `npx tailwindcss init -p` which produces `tailwind.config.js` and `postcss.config.js`. Rename the config to `tailwind.config.ts` (TypeScript) and convert the export to a typed default export using the `Config` type from `tailwindcss`.

- [ ] **Step 2: Configure Tailwind's content paths and theme tokens**

In `tailwind.config.ts`, set the content globs to include `./index.html` and `./src/**/*.{vue,ts,js}`. Extend the theme with a semantic color palette: `positive` mapped to an emerald shade (for example 500 and 600), `negative` mapped to a vivid red, `neutral` mapped to a warm amber, `accent` mapped to a deep slate, and keep Tailwind's default slate and gray scales for surfaces and borders. Add `fontFamily.sans` starting with `'Inter'` and falling back through the standard system stack.

- [ ] **Step 3: Wire Tailwind into the stylesheet**

Replace the contents of `src/style.css` with the three Tailwind directives (`@tailwind base`, `@tailwind components`, `@tailwind utilities`) plus a base layer that sets the `html` element to the system font stack, the body background to a soft gray, and any numeric span with the class `tabular` to use `font-variant-numeric: tabular-nums`.

- [ ] **Step 4: Import the stylesheet in main.ts**

Ensure `src/main.ts` imports `./style.css` at the top.

- [ ] **Step 5: Prove Tailwind is active**

In `src/App.vue`, temporarily apply a Tailwind utility class (for example `bg-emerald-500 p-8 text-white text-2xl`) to the root div. Run `npm run dev` and open the browser. Expected: the dashboard greeting is shown with a green background. Revert the class.

- [ ] **Step 6: Commit**

Stage the config files and stylesheet changes. Commit with message `chore: configure Tailwind with semantic tokens`.

---

## Task 3: Install Chart.js, Vitest, and testing libraries

**Files:**
- Create: `vitest.config.ts`
- Modify: `package.json` scripts section

- [ ] **Step 1: Install runtime and dev dependencies**

Run `npm install chart.js`. Then run `npm install -D vitest @vue/test-utils jsdom @vitejs/plugin-vue happy-dom`. (Choose either `jsdom` or `happy-dom` — prefer `happy-dom` for speed.)

- [ ] **Step 2: Create the Vitest config**

Create `vitest.config.ts` that extends the Vite config, sets the `test.environment` to `happy-dom`, sets `test.globals` true for cleaner imports in tests, and points `test.include` at `tests/**/*.spec.ts`.

- [ ] **Step 3: Add test scripts**

In `package.json`, add scripts: `"test": "vitest run"` and `"test:watch": "vitest"`.

- [ ] **Step 4: Create a trivial placeholder test**

Create `tests/smoke.spec.ts` containing one test that asserts `1 + 1 === 2`. Run `npm test`. Expected: one passing test.

- [ ] **Step 5: Commit**

Stage config, scripts, and the smoke test. Commit with message `chore: add Chart.js and Vitest test runner`.

---

## Task 4: Define the TypeScript contract for data.json

**Files:**
- Create: `src/types/data.ts`

- [ ] **Step 1: Write the full interface**

Create `src/types/data.ts` exporting one top-level interface (call it `DashboardData`) whose fields match the eleven sections plus metadata from the Design Spec. Make every field strictly typed with no `any`. Numeric amounts are `number`; timestamps are `string`; optional or nullable fields use `T | null` (not optional marker) so the dashboard always sees the key, matching the exporter's behavior. Include sub-interfaces for `Metadata`, `AccountSummary`, `Position`, `AllocationSlice`, `Snapshot`, `Benchmark`, `BenchmarkSnapshot`, `Trade`, `TodayPlan`, `PlanDecision`, `Education`, `MarketEducation`, `DailyLesson`, `Sources`, `Stats`, `RealizedTrade`, and `DividendEvent`. The `Trade` interface includes a `realized_profit: number | null` field (non-null for sell rows that completed a round trip; null otherwise). Export them all.

- [ ] **Step 2: Compile-check the types**

Run `npx tsc --noEmit`. Expected: no errors. This guarantees the types are internally consistent before any code consumes them.

- [ ] **Step 3: Commit**

Stage the new file. Commit with message `feat(types): define data.json contract interface`.

---

## Task 5: Create the dev fixture data.json

**Files:**
- Create: `public/data.json`
- Create: `tests/fixtures/data.valid.ts`
- Create: `tests/fixtures/data.empty.ts`

- [ ] **Step 1: Write a realistic valid fixture**

Create `public/data.json` containing a complete, schema-valid snapshot that looks like the 2026-04-22 state from the main repo: portfolio at $10,409.92, VOO at $10,140.19, positions META/COIN/TSLA, seven trades including one winning MSTR round trip and one losing TSLA round trip, five daily snapshots, a populated today-plan with two decisions and a briefing, a populated education block with bilingual content, and a populated stats block with hand-consistent values. Use `schema_version: 1`.

- [ ] **Step 2: Create a typed TypeScript fixture for component tests**

Create `tests/fixtures/data.valid.ts` that imports the `DashboardData` type and exports a `const` of that type containing the same values as `public/data.json`. This lets component tests have type safety and avoid JSON parsing.

- [ ] **Step 3: Create an empty-portfolio fixture**

Create `tests/fixtures/data.empty.ts` exporting a `DashboardData` constant representing a brand new portfolio: starting cash $10,000, zero positions, empty trades, empty snapshots, no today-plan, no education, zero-value stats, empty dividends. This is for testing empty-state rendering.

- [ ] **Step 4: Smoke-test the fixture by fetching it**

Run `npm run dev`. In the browser console, run `await (await fetch('/data.json')).json()` — confirm the structure looks right.

- [ ] **Step 5: Commit**

Stage all three fixture files. Commit with message `feat(fixtures): add valid and empty data.json fixtures`.

---

## Task 6: Write the format utility

**Files:**
- Create: `src/utils/format.ts`
- Create: `tests/utils/format.spec.ts`

- [ ] **Step 1: Write failing tests**

In `tests/utils/format.spec.ts`, write tests covering: `formatCurrency(10409.92)` returns `"$10,409.92"`; `formatCurrency(-234.56)` returns `"−$234.56"` (minus sign, not hyphen); `formatCurrency(null)` returns `"—"`; `formatPercent(4.1)` returns `"4.10%"`; `formatSignedPercent(4.1)` returns `"+4.10%"`; `formatSignedPercent(-0.18)` returns `"−0.18%"`; `formatSignedPercent(null)` returns `"—"`; `formatDate("2026-04-22")` returns `"Apr 22"`.

- [ ] **Step 2: Run to verify failures**

Run `npm test -- tests/utils/format.spec.ts`. Expected: import errors because the module does not exist yet.

- [ ] **Step 3: Implement the formatters**

Create `src/utils/format.ts` exporting four functions matching the test expectations. Use `Intl.NumberFormat` with `en-US` locale and `style: "currency"` for currency; use a custom string builder for signed percent to get the correct signs; use `Intl.DateTimeFormat` with month short and numeric day for dates. All functions accept `number | null` and return `"—"` for null input.

- [ ] **Step 4: Run to verify passes**

Run the test suite again. Expected: all format tests pass.

- [ ] **Step 5: Commit**

Commit with message `feat(utils): add currency, percent, and date formatters`.

---

## Task 7: Write the CSV utility

**Files:**
- Create: `src/utils/csv.ts`
- Create: `tests/utils/csv.spec.ts`

- [ ] **Step 1: Write failing tests**

Write tests: `tradesToCSV([])` returns just the header line (ending with a newline); `tradesToCSV([oneTrade])` returns header plus one data row with the expected field values and proper quoting of the reasoning field when it contains a comma or quotation marks; ordering of CSV columns is: id, timestamp, action, ticker, shares, price, total, reasoning.

- [ ] **Step 2: Run to verify failures**

Expected: module undefined.

- [ ] **Step 3: Implement `tradesToCSV`**

Create `src/utils/csv.ts`. Implement a small CSV writer: the header is a comma-separated list of the eight columns; each row stringifies the values, escapes double quotes by doubling them, and wraps any field containing a comma, newline, or double quote in double quotes. Join rows with `\n` and end with a trailing newline.

- [ ] **Step 4: Implement `downloadCSV`**

In the same file, export a `downloadCSV(filename, content)` function that creates a Blob with MIME type `text/csv`, creates an object URL, creates a temporary anchor element with the download attribute, clicks it, then revokes the URL. This is a browser-only function; the tests do not call it directly.

- [ ] **Step 5: Run to verify passes**

Expected: CSV tests pass.

- [ ] **Step 6: Commit**

Commit with message `feat(utils): add trade CSV export`.

---

## Task 8: Write the useData composable

**Files:**
- Create: `src/composables/useData.ts`
- Create: `tests/composables/useData.spec.ts`

- [ ] **Step 1: Write failing tests**

Write tests covering: calling `useData()` returns an object with reactive refs for `data`, `loading`, `error`, and `schemaMismatch`, plus a `reload` function; immediately after the call, `loading` is true and `data` is null; after the returned promise resolves with a valid fixture, `loading` becomes false, `data` equals the fetched object, and `error` is null; when `fetch` is mocked to return a malformed body, `loading` becomes false and `error` contains a helpful string; when the fetched JSON has `metadata.schema_version` greater than the expected constant, `schemaMismatch` is true but `data` is still populated. Use `vi.stubGlobal('fetch', …)` to mock fetch across the tests.

- [ ] **Step 2: Run to verify failures**

Expected: module undefined.

- [ ] **Step 3: Implement `useData`**

Create `src/composables/useData.ts`. Export a function that returns an object containing the five refs and a reload function. Internally define the constant `EXPECTED_SCHEMA_VERSION` equal to 1. On first call, kick off an async fetch of `/data.json` — on success set `data`, set `loading` false, compare the schema version and set `schemaMismatch` accordingly; on failure (network error or parse error) set `error` to a string and leave `data` null. The `reload` function re-runs the fetch and updates the same refs. On malformed JSON or missing required keys, set `error`. Treat the case where the server returned an object whose only meaningful content is an `error` field as also an error (the exporter may write this when it crashes).

- [ ] **Step 4: Run to verify passes**

Expected: all composable tests pass.

- [ ] **Step 5: Commit**

Commit with message `feat(composables): add useData with loading, error, and schema-mismatch state`.

---

## Task 9: Build the DashboardHeader component

**Files:**
- Create: `src/components/DashboardHeader.vue`

- [ ] **Step 1: Implement the component**

A `<script setup lang="ts">` block declaring props `dateEt: string` and `generatedAt: string`. A template showing the brand text "Investment Agent" on the left with `text-accent font-semibold tracking-tight` classes and on the right a muted span showing the formatted date and a muted span showing `Updated <time>` where `<time>` is the `generatedAt` timestamp rendered through the format utility as a short local time.

- [ ] **Step 2: Verify by using it in App.vue**

Temporarily import and render `DashboardHeader` in `App.vue` with fixture values. Run `npm run dev` and confirm the header renders with correct typography.

- [ ] **Step 3: Commit**

Commit with message `feat(components): add DashboardHeader`.

---

## Task 10: Build the HeroCard component with tests

**Files:**
- Create: `src/components/HeroCard.vue`
- Create: `tests/components/HeroCard.spec.ts`

- [ ] **Step 1: Write failing tests**

Write tests mounting `HeroCard` with a props object of type `AccountSummary`: assert the total value is rendered using the currency formatter; assert the profit pill shows the correctly-signed percent and dollar amount; assert the three mini-KPIs show cash balance, vs-VOO percent, and the positions count (which should be passed in as a separate prop since `AccountSummary` itself doesn't carry it — update the test to reflect this). Also assert that the pill has the `bg-positive-50 text-positive-700` class (or whatever the positive token resolves to) when profit is positive, and the negative equivalent when profit is negative.

- [ ] **Step 2: Implement the component**

Props: `account: AccountSummary`, `positionsCount: number`. Template: a white rounded card with padding and shadow; a small uppercase label "Total Portfolio"; the large currency value; a pill with an up or down arrow character and the signed percent plus dollar amount; a three-column grid of mini-KPI cards below (cash, vs VOO, positions count). Styling uses the Tailwind semantic tokens so positive is emerald, negative is red.

- [ ] **Step 3: Run tests to verify passes**

Expected: all HeroCard tests pass.

- [ ] **Step 4: Commit**

Commit with message `feat(components): add HeroCard`.

---

## Task 11: Build the EquityChart component

**Files:**
- Create: `src/components/EquityChart.vue`

- [ ] **Step 1: Implement the component**

Props: `snapshots: Snapshot[]` and `benchmarkSnapshots: BenchmarkSnapshot[]`. Use the Chart.js `Chart` constructor with type `line`. Two datasets: the agent's `total_value` series in the accent color as a solid line, and the benchmark's `total_value` series in a neutral gray as a dashed line. X-axis is dates; Y-axis scales automatically. Render into a canvas element. Destroy and recreate the chart when the props change (use a `watch` plus an `onBeforeUnmount` cleanup). Wrap in a rounded white card with padding and a small label plus a legend with two colored dots identifying each series.

- [ ] **Step 2: Visual verification**

Run `npm run dev`. Render `EquityChart` with the fixture snapshots. Confirm the chart renders correctly with both series visible. No test required for this component since it is primarily visual.

- [ ] **Step 3: Commit**

Commit with message `feat(components): add EquityChart with Chart.js line`.

---

## Task 12: Build the AllocationPanel component with tests

**Files:**
- Create: `src/components/AllocationPanel.vue`
- Create: `tests/components/AllocationPanel.spec.ts`

- [ ] **Step 1: Write failing tests**

Tests: given a props set of `positions`, `allocation`, and `cash`, the component renders a donut chart (assert the canvas element exists) and a list of rows; each row shows the ticker and share count on the left and the market value plus portfolio percentage on the right; the cash row appears last; any position whose `market_value` is null still appears in the list but with an "unavailable" placeholder for value and percent.

- [ ] **Step 2: Implement the component**

Use Chart.js with type `doughnut`. Props: `positions: Position[]`, `allocation: AllocationSlice[]`, `cash: number`, `totalValue: number`. The donut uses the allocation slices; colors are taken from a small array of deterministic colors keyed by ticker. The list on the right iterates the positions sorted by descending market value, with cash rendered last. Wrap in a card; on narrow viewports (use Tailwind's `lg:` breakpoint or similar), the donut stacks above the list. Destroy the chart instance in an unmount hook.

- [ ] **Step 3: Run tests to verify passes**

Expected: component tests pass.

- [ ] **Step 4: Commit**

Commit with message `feat(components): add AllocationPanel with donut and positions list`.

---

## Task 13: Build the TodayPlan component

**Files:**
- Create: `src/components/TodayPlan.vue`

- [ ] **Step 1: Implement the component**

Prop: `plan: TodayPlan | null`. When the prop is null, render a single muted card saying "No plan available for today." Otherwise iterate `plan.decisions`: for each decision, render a plan-card with a small action label (BUY, SELL, or HOLD) colored by type (emerald, red, gray), the ticker and share count, and the reasoning text below in muted type. If `skip_new_buys` is true, prepend a small warning banner that says "Risk-off today — no new buys."

- [ ] **Step 2: Visual verification**

Render in dev with the fixture today-plan and confirm it looks right. Temporarily swap to the empty fixture and confirm the fallback message appears.

- [ ] **Step 3: Commit**

Commit with message `feat(components): add TodayPlan`.

---

## Task 14: Build the BriefingCard component

**Files:**
- Create: `src/components/BriefingCard.vue`

- [ ] **Step 1: Implement the component**

Props: `briefing: string | null`, `education: Education | null`. Render a card with a subtle amber left border for visual separation. The top of the card shows the briefing text (falling back to "No briefing available today" if null). Below is the daily lesson block, if present: the term, the English explanation, and below that in a smaller, lighter style, the Chinese explanation. Below the lesson is a small, collapsible-by-default "Market context" block showing the bilingual market summary with source citations if present. Source citations render as subscripted links if a URL is provided, otherwise plain superscripted numbers.

- [ ] **Step 2: Visual verification**

Run in dev with the fixture education block. Confirm bilingual content renders correctly and that the amber accent reads well against the fintech palette.

- [ ] **Step 3: Commit**

Commit with message `feat(components): add BriefingCard with bilingual education`.

---

## Task 15: Build the FilterTabs sub-component

**Files:**
- Create: `src/components/FilterTabs.vue`

- [ ] **Step 1: Implement the component**

Props: `modelValue: string` (the currently-active filter key), `options: { key: string; label: string }[]` (the available filters). Emits: `update:modelValue`. Template: a flex row of pill buttons; the active pill has a dark background with white text, inactive pills have a light gray background with slate text. Clicking a pill emits the new value. This is a controlled component — it does not manage state itself.

- [ ] **Step 2: Commit**

Commit with message `feat(components): add FilterTabs`.

---

## Task 16: Build the TradeRow sub-component

**Files:**
- Create: `src/components/TradeRow.vue`

- [ ] **Step 1: Implement the component**

Prop: `trade: Trade`. Template: one row with the action label in bold with color (green for BUY, red for SELL), the ticker, the share count and price, and on the right the short date. When `trade.realized_profit` is non-null, show a small pill in green or red with the realized dollar amount formatted via the currency formatter with a leading sign. Rows have a hairline border underneath.

- [ ] **Step 2: Commit**

Commit with message `feat(components): add TradeRow`.

---

## Task 17: Build the PerTickerGroup sub-component

**Files:**
- Create: `src/components/PerTickerGroup.vue`

- [ ] **Step 1: Implement the component**

Prop: `group: { ticker: string; trades: Trade[]; realized_profit: number; trade_count: number }`. Template: a collapsible section with the ticker, a trade count badge, and the realized profit on the right, colored by sign. Clicking the header toggles expansion; when expanded, the contained `TradeRow` components are listed underneath.

- [ ] **Step 2: Commit**

Commit with message `feat(components): add PerTickerGroup`.

---

## Task 18: Build the TradeHistory component with tests

**Files:**
- Create: `src/components/TradeHistory.vue`
- Create: `tests/components/TradeHistory.spec.ts`

- [ ] **Step 1: Write failing tests**

Tests: given a props set with the seven-trade fixture, the default filter is "Month" and the rendered list contains only trades in the current month (use a fixed "today" date passed as a prop so the test is deterministic); switching the filter to "All" renders all seven trades; switching to "By ticker" renders grouped sections with correct realized profit per ticker; clicking the CSV export button calls the `downloadCSV` function with a CSV string (stub `downloadCSV` via a spy on the module).

- [ ] **Step 2: Implement the component**

Props: `trades: Trade[]`, `perTickerRealized: Record<string, number>` (from the Stats section — pass it through), `now: Date` (defaults to `new Date()` but injectable for testing). Internal state: the currently active filter key. A computed property returns the filtered trades according to the active filter (Week, Month, Quarter, Year, All, By ticker). When "By ticker" is active, a second computed groups the filtered list by ticker, counts trades per ticker, and uses `perTickerRealized[ticker]` for the realized-profit value — no FIFO math is needed in the Vue app because Plan A already produced it. The template renders: the header with a title showing the filtered count; the CSV export button; the `FilterTabs` instance bound to the filter key; either a flat list of `TradeRow` components or a list of `PerTickerGroup` components depending on the filter.

- [ ] **Step 3: Run tests to verify passes**

Expected: TradeHistory tests pass.

- [ ] **Step 4: Commit**

Commit with message `feat(components): add TradeHistory with filters and CSV export`.

---

## Task 19: Build the StatsGrid component with tests

**Files:**
- Create: `src/components/StatsGrid.vue`
- Create: `tests/components/StatsGrid.spec.ts`

- [ ] **Step 1: Write failing tests**

Tests: given a `stats: Stats` prop, the grid renders six tiles with the expected labels and correctly-formatted values; positive values render in the positive token, negative in the negative token; null values render as "—".

- [ ] **Step 2: Implement the component**

Prop: `stats: Stats`. Template: a responsive grid — three columns on desktop, two on mobile — containing six metric tiles: win rate (formatted as percent); average winner vs loser (formatted currency side-by-side with a separator); max drawdown (signed percent in negative color); daily volatility (percent); best trade (ticker plus dollar amount in positive color); total realized profit (signed currency).

- [ ] **Step 3: Run tests to verify passes**

Expected: StatsGrid tests pass.

- [ ] **Step 4: Commit**

Commit with message `feat(components): add StatsGrid`.

---

## Task 20: Build the DashboardFooter component

**Files:**
- Create: `src/components/DashboardFooter.vue`

- [ ] **Step 1: Implement the component**

Props: `generatedAt: string`, `schemaVersion: number`. A small centered muted paragraph reading `Generated <formatted time> · schema v<version>`.

- [ ] **Step 2: Commit**

Commit with message `feat(components): add DashboardFooter`.

---

## Task 21: Assemble everything in App.vue

**Files:**
- Modify: `src/App.vue`

- [ ] **Step 1: Wire the composable and handle states**

Replace the stub `App.vue` with a full implementation. In the `<script setup lang="ts">` block, call `useData()` and destructure all refs. In the template, handle three states explicitly: loading (show a centered muted skeleton saying "Loading portfolio data…"), error (show a centered error card showing the error message, the timestamp of the last error, and a "Retry" button bound to the `reload` function), and data-present (render the full dashboard).

- [ ] **Step 2: Compose the full dashboard when data is present**

When `data` is non-null, render the centered container (max-width constraint around 720 pixels on large screens, full width on mobile with padding) containing in order: `DashboardHeader`, `HeroCard`, `EquityChart`, `AllocationPanel`, `TodayPlan`, `BriefingCard`, `TradeHistory`, `StatsGrid`, `DashboardFooter`. Pass the appropriate slice of `data` to each component as props.

- [ ] **Step 3: Handle the schema-mismatch warning**

When `schemaMismatch` is true, render a yellow warning banner at the very top of the container saying "Dashboard may be out of date — rebuild required." Clicking it links to the README. The content below renders anyway on a best-effort basis.

- [ ] **Step 4: Verify end-to-end in dev**

Run `npm run dev`. Confirm every section renders with the fixture data, the page is readable on a phone viewport (use the browser's device emulation), and the loading skeleton flashes briefly on first load. Use the browser devtools to temporarily delete `public/data.json` and confirm the error state appears.

- [ ] **Step 5: Commit**

Commit with message `feat(app): compose full dashboard with loading, error, and schema-mismatch states`.

---

## Task 22: Responsive verification and production build

**Files:** none modified — verification only.

- [ ] **Step 1: Test on three viewport widths**

Use browser devtools to verify rendering at three widths: 375 pixels (iPhone SE), 414 pixels (iPhone Pro), and 1280 pixels (desktop). Confirm: on mobile, the single column fills the viewport with 16px side padding and nothing horizontally overflows; the donut sits above the positions list on narrow viewports; the stats grid becomes two columns on mobile.

- [ ] **Step 2: Run the full test suite**

Run `npm test`. Expected: every spec file passes.

- [ ] **Step 3: Produce a production build**

Run `npm run build`. Expected: `dist/` is produced without warnings (beyond informational ones about chunk size). Run `npm run preview` and open the preview URL. Navigate through the dashboard and confirm everything still works with the bundled JS.

- [ ] **Step 4: Commit anything incidental**

If this step surfaced small fixes (CSS adjustments, type narrowing), commit them with a clear message.

---

## Task 23: Write the README and ignore rules

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Expand the README**

Replace the README contents with sections: what the project is (the companion dashboard to `investmentAgentSim`, separated for presentation concerns); how data flows in (the sibling repo writes `public/data.json` on each Run 2, this project reads it client-side); quick start (prereqs, install, dev, build, test commands); project structure (short tree); the contract (pointer to the main repo's Design Spec); how to add a new data field (update the type, the fixture, any consuming component, bump the schema version if the change is breaking); and deployment (the current project is ready for static hosting; live deploy is deferred to a future phase).

- [ ] **Step 2: Confirm .gitignore**

Ensure `.gitignore` contains `node_modules/`, `dist/`, `.DS_Store`, and `*.log`. Keep `public/data.json` tracked (it is the contract artifact committed by the sibling repo).

- [ ] **Step 3: Commit and push**

Commit with message `docs: write README and finalize .gitignore`. Push to origin.

---

## Self-Review Checklist

After completing all tasks, verify the following. If any item fails, fix it before declaring this plan complete.

- The repository lives at `~/Desktop/local/Learn/Local_Dev/investmentAgentDashboard` and is pushed to a private GitHub repo
- `npm run dev` serves a working dashboard that renders every section of the Design Spec from the fixture `public/data.json`
- `npm run build` produces a `dist/` folder without errors
- `npm run preview` serves the built bundle correctly
- `npm test` passes every spec file with zero failures and zero skips
- The dashboard is visually readable at 375px, 414px, and 1280px viewport widths
- Manually deleting `public/data.json` triggers the error state with a working Retry button
- The TypeScript `DashboardData` interface exactly matches the Design Spec's eleven sections plus metadata
- No `any` types exist anywhere in `src/`
- Git history contains one commit per task, using conventional commit messages
- No unused imports or unused files remain

---

## Next Steps

Plan B completes the presentation layer. Combined with Plan A, the redesign is shippable as a local-only setup: run the agent, the data writes and commits, pull in the dashboard repo, run `npm run dev`, view on desktop or phone (via LAN access or port forwarding).

The future phase — deploying to Cloudflare Pages behind Cloudflare Access, and optionally moving the data artifact to R2 — is captured as a separate future spec. Nothing in this plan contradicts that direction: the dashboard is already a pure static site, and the data contract is already versioned and stable.
