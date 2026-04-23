# Dashboard Redesign — Main Repo Implementation Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing HTML dashboard generator with a JSON exporter that produces a versioned data contract consumed by a separate Vue 3 dashboard repository. Auto-commit the resulting JSON into the sibling dashboard repo on each Run 2.

**Architecture:** A new Python module `agent/tools/dashboard_export.py` reads from the existing SQLite tables and the Run 1 plan file, computes derived statistics, and writes a single JSON file atomically. Run 2 calls it at the very end, after trade execution, and then runs a small git helper to commit and push the file inside the sibling dashboard repository. The old HTML dashboard module, its generated output, and its tests are removed. Trade execution remains sacred; no failure in export or git can affect trading.

**Tech Stack:** Python standard library, existing `sqlite3` and `yfinance` paths already in the repo, `pytest` for tests. No new dependencies.

**Companion Plan:** Plan B (dashboard Vue app) consumes the `data.json` produced by this plan.

---

## Prerequisites

Before starting, confirm the following are true. If any are not, address them first.

- The current working directory is the root of the `investmentAgentSim` repository
- The git status is clean, or only contains changes you are willing to carry through
- Python 3.9+ is available and the existing test suite passes: running `pytest` from the repo root reports zero failures
- The sibling directory for the dashboard repository (default path: `../investmentAgentDashboard`) may or may not exist yet; the exporter must handle both cases gracefully

---

## File Structure

**Files to create:**
- `agent/tools/dashboard_export.py` — the exporter module, the only new file
- `agent/tools/git_sync.py` — tiny helper wrapping the stage / commit / push subprocess calls
- `tests/test_dashboard_export.py` — tests for the exporter
- `tests/test_git_sync.py` — tests for the git helper
- `tests/fixtures/dashboard_export_seed.py` — a reusable helper that seeds a known test database and plan file for the happy-path and stats-math tests

**Files to modify:**
- `agent/main.py` — add the export + git sync call to the end of the Run 2 command
- `tests/test_main.py` — update Run 2 tests to assert the exporter runs and that its failure does not break trade execution

**Files to delete:**
- `agent/tools/dashboard.py` — the old HTML generator
- `tests/test_dashboard.py` (if it exists) — tests of the old HTML generator
- `output/dashboard.html` (if it exists locally) — stale generated file; also remove the `output/` entry from the repo if nothing else uses it

---

## Task 1: Deprecate the old dashboard module

**Files:**
- Delete: `agent/tools/dashboard.py`
- Delete: `tests/test_dashboard.py` (if present)
- Delete: `output/dashboard.html` (if present)
- Modify: `agent/main.py` — remove any import of or call to the old dashboard module

- [ ] **Step 1: Locate all references**

Search the repo for the symbols `dashboard.py`, `generate_dashboard`, and any other public names exported by the old module. Confirm exactly which files import or call them.

- [ ] **Step 2: Remove the references**

In `agent/main.py` remove the import of the old dashboard module and remove any call to it (typically inside `cmd_run2` or the dashboard CLI subcommand). Remove the old `dashboard` subcommand from the CLI entirely — it will no longer exist.

- [ ] **Step 3: Delete the module and its tests**

Delete `agent/tools/dashboard.py`. Delete `tests/test_dashboard.py` if present. Delete `output/dashboard.html` if present.

- [ ] **Step 4: Run the test suite**

Run `pytest` from the repo root. Expected: still zero failures, because the only thing that referenced the old module is now gone. Any failure indicates a missed reference — find and remove it before proceeding.

- [ ] **Step 5: Commit**

Stage all deletions and the `main.py` changes. Commit with message `chore: remove old HTML dashboard generator`.

---

## Task 2: Create the skeleton exporter module

**Files:**
- Create: `agent/tools/dashboard_export.py`
- Create: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write a failing test for the module's public surface**

In `tests/test_dashboard_export.py`, write a test that imports `export_dashboard_data` from `agent.tools.dashboard_export` and asserts it is callable. Also import a constant `SCHEMA_VERSION` from the same module and assert it equals the integer 1.

- [ ] **Step 2: Run the test to verify it fails**

Run `pytest tests/test_dashboard_export.py -v`. Expected failure: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Create the skeleton module**

Create `agent/tools/dashboard_export.py` with a module docstring describing its purpose, a `SCHEMA_VERSION` constant equal to 1, and a function `export_dashboard_data` that takes three parameters — `db_path`, `plan_path`, and `output_path` — and for now returns an empty dict. Do not write the file yet inside the function.

- [ ] **Step 4: Run the test to verify it passes**

Run `pytest tests/test_dashboard_export.py -v`. Expected: both assertions pass.

- [ ] **Step 5: Commit**

Stage both files. Commit with message `feat: scaffold dashboard_export module`.

---

## Task 3: Extract account summary

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`
- Create: `tests/fixtures/dashboard_export_seed.py`

- [ ] **Step 1: Create the seed fixture helper**

Create `tests/fixtures/dashboard_export_seed.py`. It exposes one function `seed_known_database(db_path)` that initializes a fresh SQLite database using the existing `init_db` from `agent.portfolio.database`, then inserts a known set of rows into `account`, `positions`, `trades`, `daily_snapshots`, `benchmark_account`, and `benchmark_snapshots`. The exact seed values should include: starting cash 10000, current cash 5238.89, three positions (META 3 shares at avg cost 674.16, COIN 12 at 195.90, TSLA 2 at 398.86), seven trades spanning three dates with at least two closed round trips on MSTR (buy 17 at 143.69 then sell 17 at 168.86 — a winner; and a TSLA sell 6 at 385.375 versus a TSLA buy 6 at 388.37 — a loser), five daily snapshots showing a small peak-to-trough dip, and a benchmark seed of 15.507 VOO shares deposited over 10000. This fixture is shared across happy-path and derived-stats tests.

- [ ] **Step 2: Write a failing test for account summary extraction**

In `tests/test_dashboard_export.py`, add a test that calls `seed_known_database` against a temp DB path, then calls a new internal function `_build_account_section(db_path)` from `dashboard_export`, and asserts the returned dict contains keys `total_value`, `cash`, `starting_cash`, `profit_dollars`, `profit_percent`, `vs_voo_dollars`, and `vs_voo_percent` with the expected numeric values derived from the seed.

- [ ] **Step 3: Run the test to verify it fails**

Run the test. Expected failure: `_build_account_section` is not defined.

- [ ] **Step 4: Implement `_build_account_section`**

Add the function to `dashboard_export`. It must open a read-only connection using the existing `get_connection` helper from `agent.portfolio.database`, read the cash balance from `account`, read the most recent total value from `daily_snapshots` (or compute from cash plus positions at avg cost when no snapshot exists), read the VOO benchmark total from `benchmark_account` joined against the latest `benchmark_snapshots` row, compute the profit dollars as total minus starting cash, compute the profit percent relative to starting cash, and compute the vs-VOO gap in dollars and percent. Use the existing `STARTING_CASH` constant from `agent.portfolio.engine`.

- [ ] **Step 5: Run the test to verify it passes**

Run the test. Expected: all seven asserted fields match.

- [ ] **Step 6: Commit**

Commit with message `feat(dashboard_export): extract account summary section`.

---

## Task 4: Extract positions with current prices

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write a failing test for positions extraction**

Add a test that uses the seed fixture, monkeypatches `get_price` from `agent.tools.stock_data` to return deterministic prices (META 681, COIN 193, TSLA 402), then calls `_build_positions_section(db_path)` and asserts: the returned list has three entries, each contains ticker, shares, avg_cost, current_price, market_value, profit_dollars, profit_percent, portfolio_pct; the numeric values match hand-calculations; and the portfolio_pct fields for positions plus the implied cash share sum to exactly 100.0.

- [ ] **Step 2: Write a failing test for price fetch failure**

Add a second test where `get_price` raises for one ticker (TSLA) and returns valid prices for the others. Assert that the TSLA entry is present but its `current_price`, `market_value`, `profit_dollars`, `profit_percent`, and `portfolio_pct` are all `None` (or `null` semantics), while the other two positions are populated normally. Assert the function does not raise.

- [ ] **Step 3: Run both tests to verify they fail**

Expected failures: `_build_positions_section` undefined.

- [ ] **Step 4: Implement `_build_positions_section`**

Read all rows from the `positions` table. For each, call the existing `get_price(ticker)` wrapped in a try/except that catches any exception and leaves the current price as None. Compute market value as shares times current price when price is available, profit dollars as market value minus shares times avg cost, profit percent as profit dollars divided by (shares times avg cost) times 100, portfolio percent as market value divided by (total market value plus cash) times 100. Use banker's rounding or half-up rounding to produce percentages that sum cleanly to 100 with cash. When a price is missing, all derived fields must be None.

- [ ] **Step 5: Run both tests to verify they pass**

Expected: both tests pass.

- [ ] **Step 6: Commit**

Commit with message `feat(dashboard_export): extract positions with current prices`.

---

## Task 5: Compute allocation breakdown

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write a failing test**

Add a test that uses the seed fixture with the same monkeypatched prices, calls `_build_allocation_section(positions_list, cash)`, and asserts the returned list contains four entries (three tickers plus cash), each with a `label` and a `pct` field, and that the sum of all `pct` values is exactly 100.0 (accounting for rounding). Order is: positions in descending pct, then cash last.

- [ ] **Step 2: Run to verify failure**

Expected: `_build_allocation_section` undefined.

- [ ] **Step 3: Implement the allocation function**

Take the positions list and cash balance as inputs. For each position where market value is not None, compute its percentage of total. Compute cash's percentage. Build a list of dicts sorted by descending percent, with cash always appended last. Adjust the final entry's percent so the total equals exactly 100.0 after rounding each value to one decimal place. Positions with missing prices are excluded from the donut but still present in the positions list.

- [ ] **Step 4: Run to verify pass**

Expected: test passes.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): compute allocation breakdown`.

---

## Task 6: Extract snapshots and benchmark series

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write failing tests for snapshots and benchmark series**

Add two tests. The first calls `_build_snapshots_section(db_path)` and asserts the returned list is in ascending date order, has five entries matching the seeded rows, and each entry has `date`, `total_value`, `cash`, and `profit_percent`. The second calls `_build_benchmark_section(db_path)` and asserts the returned dict contains `voo_shares`, `voo_price`, `total_value`, `total_deposited`, and a `snapshots` list in ascending date order with `date`, `voo_shares`, `voo_price`, and `total_value` fields.

- [ ] **Step 2: Run to verify failures**

Expected: functions undefined.

- [ ] **Step 3: Implement the two functions**

`_build_snapshots_section` reads all rows from `daily_snapshots` ordered by date ascending and maps them to dicts. `_build_benchmark_section` reads the current `benchmark_account` row for shares and deposited, reads the most recent price from `benchmark_snapshots` for the top-level fields, and reads all `benchmark_snapshots` rows ordered by date ascending for the series.

- [ ] **Step 4: Run to verify passes**

Expected: both tests pass.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): extract snapshots and benchmark series`.

---

## Task 7: Extract trade history

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write a failing test**

Add a test that calls `_build_trades_section(db_path)` and asserts the returned list is in descending timestamp order (newest first), has exactly the seven seeded trades, each contains `id`, `timestamp`, `action`, `ticker`, `shares`, `price`, `total`, `reasoning`, and `realized_profit`. Assert `reasoning` is always a string (never None — missing DB values become empty strings). Assert `realized_profit` is null on BUY rows and on SELL rows that did not complete a round trip, and is a number equal to the hand-calculated realized dollar amount on SELL rows that did complete a round trip (the MSTR and TSLA closed trades from the seed).

- [ ] **Step 2: Run to verify failure**

Expected: function undefined.

- [ ] **Step 3: Implement `_build_trades_section`**

Read all rows from `trades` ordered by timestamp ascending to build FIFO queues of open buys per ticker. As each sell is encountered, pop buys from the head of that ticker's queue until the sold share count is satisfied, accumulating the realized profit as the sell's total minus the cost basis of the matched buys. Store that realized profit alongside the sell. Buys and partial sells carry a null realized_profit. Once all rows are processed, reverse the list to descending timestamp order (newest first) and map each to a dict; coerce a null `reasoning` to an empty string.

- [ ] **Step 4: Run to verify pass**

Expected: test passes.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): extract trade history with per-sell realized profit`.

---

## Task 8: Extract today's plan from Run 1 JSON

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write failing tests for three plan states**

Add three tests. First, "happy path": write a valid Run 1 plan JSON file to a temp path containing `decisions` (array of buy/sell/hold entries with reasoning), `skip_new_buys` (boolean), `market_direction`, and `briefing` (string). Call `_build_today_plan_section(plan_path)` and assert the returned dict mirrors those fields. Second, "missing file": pass a path that does not exist; assert the function returns None. Third, "malformed file": write a non-JSON string to a temp file; assert the function returns None (permissive — never raises).

- [ ] **Step 2: Run to verify failures**

Expected: function undefined.

- [ ] **Step 3: Implement `_build_today_plan_section`**

Try to open the file and parse JSON. If the file does not exist or JSON parsing fails or any required keys are missing, return None. Otherwise return a dict with `decisions`, `skip_new_buys`, `market_direction`, and `briefing`.

- [ ] **Step 4: Run to verify passes**

Expected: all three tests pass.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): extract today's plan section`.

---

## Task 9: Extract daily education from Run 1 JSON

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write failing tests**

Add two tests. First, "happy path": write a plan JSON with `market_education` (containing `summary_en`, `summary_zh`, `sources`) and `daily_lesson` (containing `term`, `explanation_en`, `explanation_zh`). Call `_build_education_section(plan_path)` and assert the returned dict has both blocks intact. Second, "absent education fields": write a plan JSON without those optional blocks. Assert the function returns a dict with both blocks set to None.

- [ ] **Step 2: Run to verify failures**

Expected: function undefined.

- [ ] **Step 3: Implement `_build_education_section`**

Load the plan JSON the same way as the today-plan loader. Extract `market_education` and `daily_lesson` if present; otherwise set each to None. Missing file or parse error returns a dict with both set to None. Never raises.

- [ ] **Step 4: Run to verify passes**

Expected: both tests pass.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): extract daily education section`.

---

## Task 10: Compute derived trade statistics

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write a failing test with hand-calculated expectations**

Add a test using the seed fixture. The seeded trades contain one MSTR winner (+$427.89 realized) and one TSLA round trip that's a loser (hand-compute the exact dollar loss based on seed numbers and document it in the test comments). Call `_build_stats_section(trades_list, snapshots_list)` and assert the returned dict contains: `win_rate` equals the correct percent given those closed round trips; `winners_count` and `losers_count` as integers; `avg_winner` and `avg_loser` as the arithmetic means; `best_trade` as a dict containing ticker and realized dollars; `worst_trade` as a dict; `max_drawdown_percent` as the peak-to-trough percent drop over the snapshots; `daily_volatility` as the standard deviation of day-over-day percent changes; `total_realized_profit` as the sum across all closed round trips; `per_ticker_realized` as a dict mapping ticker to realized profit.

- [ ] **Step 2: Run to verify failure**

Expected: function undefined.

- [ ] **Step 3: Implement `_build_stats_section`**

Reconstruct round trips using FIFO (first-in-first-out) matching of buys and sells per ticker in chronological order. For each fully-closed round trip, compute realized profit as sale total minus purchase cost allocated at FIFO. Classify round trips as winners or losers based on realized profit sign. Compute win rate, counts, averages, best, worst, total, and per-ticker totals. For drawdown, scan the snapshots' total values chronologically, tracking the running peak and the largest percent drop from any peak to a subsequent trough. For volatility, compute day-over-day percent changes of total value and return the population standard deviation. When there are no closed trades, the stats fields are zero or None; when there are fewer than two snapshots, drawdown and volatility are None.

- [ ] **Step 4: Run to verify pass**

Expected: test passes with hand-computed values.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): compute derived trade statistics`.

---

## Task 11: Extract dividend events

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write a failing test**

Add a test that seeds two dividend event rows (one META, one COIN), calls `_build_dividends_section(db_path)`, and asserts the returned list contains both entries in descending date order, each with `date`, `ticker`, `shares`, `amount_per_share`, and `total`.

- [ ] **Step 2: Run to verify failure**

Expected: function undefined.

- [ ] **Step 3: Implement `_build_dividends_section`**

Read all rows from `dividend_events` ordered by date descending and map each to a dict. If the table is empty, return an empty list.

- [ ] **Step 4: Run to verify pass**

Expected: test passes.

- [ ] **Step 5: Commit**

Commit with message `feat(dashboard_export): extract dividend events`.

---

## Task 12: Assemble the full export dict and write atomically

**Files:**
- Modify: `agent/tools/dashboard_export.py`
- Modify: `tests/test_dashboard_export.py`

- [ ] **Step 1: Write the happy-path integration test**

Add a test that seeds the database and writes a valid plan file, then calls `export_dashboard_data(db_path, plan_path, output_path)`. Assert the function returns a dict and that the file at `output_path` exists. Load the file as JSON and assert it contains exactly eleven top-level keys plus a `metadata` key: `metadata`, `account`, `positions`, `allocation`, `snapshots`, `benchmark`, `trades`, `today_plan`, `education`, `stats`, `dividends`. Assert `metadata` contains `schema_version` equal to 1, a `generated_at` ISO timestamp string, a `date_et` string, and a `run_id` string. Assert the returned dict equals the loaded JSON.

- [ ] **Step 2: Write an atomic-write test**

Add a test that writes a sentinel value to the output path first, then calls `export_dashboard_data` targeting that same path. Mid-way through the function, simulate a crash by monkeypatching one of the internal build functions to raise. Assert the sentinel file is still intact — the partial write did not clobber the previous good file.

- [ ] **Step 3: Write an error-path test**

Add a test that passes a deliberately broken database path. Assert the function does not raise, and that the output file exists and contains a top-level `error` field with a string explaining the failure.

- [ ] **Step 4: Run to verify failures**

Expected: the main assembly does not exist yet; tests fail.

- [ ] **Step 5: Implement `export_dashboard_data`**

Wrap the entire body in a try/except. Inside the try, call each `_build_*` function in order, assembling the full dict with a `metadata` block that includes `schema_version`, `generated_at` as an ISO 8601 timestamp with UTC offset, `date_et` as the current date formatted in America/New_York, and `run_id` as a combined timestamp+random short string. Write the dict to a temp file adjacent to the target path (same directory, `.tmp` suffix) using `json.dump` with sorted keys disabled and two-space indentation, then `os.replace` the temp file onto the final path (atomic on POSIX). On any exception, build a minimal dict with `metadata` (including schema_version) and an `error` field containing the string representation of the exception, write that minimally the same way, and return it. Never let an exception escape.

- [ ] **Step 6: Run to verify passes**

Expected: all three tests pass.

- [ ] **Step 7: Commit**

Commit with message `feat(dashboard_export): assemble full export with atomic write`.

---

## Task 13: Write the git sync helper

**Files:**
- Create: `agent/tools/git_sync.py`
- Create: `tests/test_git_sync.py`

- [ ] **Step 1: Write failing tests**

Add four tests in `tests/test_git_sync.py`. First, "repo not present": call `sync_dashboard_repo(nonexistent_path)` — assert it returns a dict with `ok` false and a `reason` string mentioning the missing directory; assert it does not raise. Second, "clean repo, nothing to commit": set up a tmp git repo with one committed file, call `sync_dashboard_repo(repo_path, files=["public/data.json"])` where that file was not modified — assert the function returns `ok` true with a reason indicating no changes. Third, "dirty repo, happy path": set up a tmp git repo, write the target file, configure a local upstream (bare repo cloned as origin), call `sync_dashboard_repo` — assert the commit was created and the push succeeded. Fourth, "push failure tolerated": same as happy path but point origin at an invalid URL — assert the function returns a dict with `ok` false and a `reason` describing the push failure, but does not raise.

- [ ] **Step 2: Run to verify failures**

Expected: `sync_dashboard_repo` undefined.

- [ ] **Step 3: Implement `sync_dashboard_repo`**

The function takes the repo root path and an optional list of file paths (relative to the repo) to stage. Check the directory exists and contains a `.git` folder; if not, return an `ok` false result. Run `git -C <path> add <files>` (or `git -C <path> add -A` if no files specified). Run `git -C <path> status --porcelain` to detect whether anything is staged; if empty, return an `ok` true result with a "no changes" reason. Otherwise run `git -C <path> commit -m "data: run2 snapshot <iso timestamp>"`. Run `git -C <path> push`. If any subprocess fails, return an `ok` false result containing the stderr. Never raise. All subprocess calls have a short timeout (e.g. 30 seconds for push).

- [ ] **Step 4: Run to verify passes**

Expected: all four tests pass.

- [ ] **Step 5: Commit**

Commit with message `feat(git_sync): add dashboard repo auto-commit helper`.

---

## Task 14: Hook exporter into Run 2

**Files:**
- Modify: `agent/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write a failing test for the successful export hook**

In `tests/test_main.py`, add or update a test for `cmd_run2` that patches `export_dashboard_data` and `sync_dashboard_repo` and asserts both are called exactly once with the expected arguments (db path, plan path, the resolved output path from the environment variable or default, and the resolved repo root for sync). The test also confirms the call order: export first, then sync.

- [ ] **Step 2: Write a failing test for export failure isolation**

Add a test that patches `export_dashboard_data` to raise an exception. Assert that `cmd_run2` still completes without raising and that the trade execution portion earlier in the command was still reached (assert a trade was persisted to the test DB as usual). The export failure is logged but absorbed.

- [ ] **Step 3: Run to verify failures**

Expected: imports or assertions fail because the hook does not exist yet.

- [ ] **Step 4: Implement the hook**

At the very end of `cmd_run2` (after the existing Telegram notify call), add a block that: reads the environment variable `DASHBOARD_REPO_PATH` (default: `../investmentAgentDashboard`), resolves it to an absolute path relative to the main repo root, builds the output path as `<repo>/public/data.json`, wraps a call to `export_dashboard_data(db_path, plan_path, output_path)` in a try/except that logs the exception and continues, and then wraps a call to `sync_dashboard_repo(repo_path, files=["public/data.json"])` in its own try/except. Import the two helpers at the top of the file.

- [ ] **Step 5: Run to verify passes**

Expected: both tests pass. Run the full test suite (`pytest`) to catch any regression.

- [ ] **Step 6: Commit**

Commit with message `feat(run2): export dashboard data and sync dashboard repo`.

---

## Task 15: Regression check the unchanged paths

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run `pytest` from the repo root. Expected: all tests pass. No test is skipped or unexpectedly excluded.

- [ ] **Step 2: Perform a dry-run of Run 2 against a sandbox directory**

Set `DASHBOARD_REPO_PATH=/tmp/fake-dashboard-repo` (a path that does not exist). Run `python -m agent.main run2` in a copy of the repo or against a test DB. Expected: Run 2 completes successfully, trade execution works, the exporter logs a warning about the missing repo and moves on, git sync logs a warning and moves on. No crash.

- [ ] **Step 3: Perform a dry-run against a real sibling directory**

Create `/tmp/fake-dashboard-repo` as an empty git repo with a remote pointing at a local bare repo. Rerun Run 2. Expected: a `public/data.json` file appears in the fake directory, the commit is created, and the push succeeds (or fails gracefully if the local bare repo is not writable).

- [ ] **Step 4: Inspect the produced JSON**

Open the produced `data.json` in a viewer. Confirm it has all eleven top-level sections plus metadata, all values look sensible, and none of the fields are missing or the wrong type.

- [ ] **Step 5: Commit a note documenting the dry-run verification**

Update `CONTEXT.md` with a short note under a new subheading (for example "Dashboard Export") describing the new `data.json` artifact, the environment variable name, and the fact that the old HTML dashboard is gone. Commit with message `docs: note dashboard export in CONTEXT.md`.

---

## Self-Review Checklist

After completing all tasks, verify the following. If any item fails, fix it before declaring this plan complete.

- The old `agent/tools/dashboard.py` no longer exists in the repo
- `agent/tools/dashboard_export.py` exists and exports `export_dashboard_data` and `SCHEMA_VERSION`
- `agent/tools/git_sync.py` exists and exports `sync_dashboard_repo`
- `agent/main.py` imports both helpers and calls them at the end of `cmd_run2`
- The full pytest suite passes
- A dry run of Run 2 against a fake sibling directory produces a `data.json` with eleven top-level sections plus metadata
- Git history contains a commit for each task, with clear conventional commit messages
- No new Python dependencies were added

---

## Next Steps

This plan lands the main-repo half of the redesign. The produced `data.json` is the input to **Plan B** (the Vue 3 dashboard application), which will be written next. Plan B is independent of this one in the sense that it can be worked on in parallel once the schema (which is locked by the Design Spec) is understood; however, any schema change introduced during Plan A's execution must be propagated to Plan B before merging Plan B.
