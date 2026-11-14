# Product Requirements Document
# Prediction Tracking, Scoring, and Alert-Only Notifications

**Version:** 0.1 (draft for review)
**Date:** 2026-11-14
**Owner:** Gary
**Status:** Draft. Open questions in section 11 need answers before build starts.
**Related:** 20260414-PRD-investment-agent.md, superpowers/specs/2026-06-25-trading-knowledge-loop-design.md, and the dashboard plan in the investmentAgentDashboard repo (docs/20261114-PLAN-supabase-dashboard-on-vercel.md)

---

## 1. Problem Statement

The agent makes calls every trading day, but nothing measures whether those calls are any good.

Today the agent saves its plan to a single plan file that is overwritten every run, writes one journal file per day, and keeps trades and snapshots in a local SQLite database that never leaves the agent PC. The trading review skill reads the journals and writes lessons into strategy memory, but that review is a judgment call made from daily snapshots. There is no record of each individual call together with the price at that moment, so there is no honest way to answer three basic questions:

1. When the agent liked a stock, did it actually go up?
2. How accurate is it overall, and is it better than just holding VOO?
3. In which situations is it most often wrong?

The second problem is noise. Every run sends a long Telegram message with the briefing, a bilingual market summary, a bilingual daily lesson, and the trade list. Most days nothing important happened, so the messages get skimmed or ignored. That means the day something does matter, it is easy to miss.

---

## 2. Product Goal

Turn the agent from something that talks every day into something that keeps score and only speaks up when it matters.

1. Record every call the agent makes, at the moment it makes it, in a form that can be checked later.
2. Score those calls automatically against what the market actually did.
3. Make the three questions above answerable with SQL and on the dashboard.
4. Cut Telegram down to 3 to 5 short points about holdings and the watchlist, sent only when something unusual happens.
5. Move the data to Supabase so the dashboard on Vercel can read it, while the agent keeps running on its own PC.

### Success Metrics

| ID | Metric | Target |
|---|---|---|
| G1 | Call coverage | Every holding and every screened candidate gets a recorded call on every run1 |
| G2 | Calls are tamper proof | A recorded call is never edited after it is written |
| G3 | Automatic scoring | Every call gets an outcome at each horizon within one trading day of that horizon ending |
| G4 | Questions answerable | Hit rate by conviction, by market direction, by signal, and picked versus not picked can each be pulled from a saved query |
| G5 | Quiet by default | On a normal day with nothing unusual, zero routine Telegram messages are sent |
| G6 | Short when it speaks | A routine alert message never has more than 5 points |
| G7 | Still alive | Gary hears from the agent at least once every 3 trading days, even if it is just a one line heartbeat |
| G8 | Trading never blocked | If Supabase is down, run1, run2, and the intraday monitor still complete normally |

---

## 3. Users

**Primary user:** Gary, solo, personal use. Reads Telegram on the phone and the dashboard on the web.

**Secondary user:** the trading review skill in the vault, which will read the scorecard instead of guessing from snapshots.

---

## 4. Scope

### In scope

- A new Supabase project that holds runs, calls, outcomes, alerts, and a copy of trades and daily snapshots for the dashboard.
- Changes to run1 so Claude gives a call for every holding and candidate, not only the stocks it trades.
- A new scoring step that fills in outcomes after the market closes.
- A rewrite of the routine Telegram messages into alert-only digests.
- A heartbeat message and failure alerts.
- Saved SQL views that answer the three questions.

### Out of scope

- Any change to the trading strategy, position sizing, or the four risk rules.
- Real money or a real brokerage connection.
- Moving the agent off its PC. The agent depends on the Claude CLI, which cannot run on Vercel.
- Replacing SQLite for the portfolio engine. SQLite stays the source of truth for cash, positions, and trade execution. Supabase gets a copy.
- The dashboard build itself. That has its own plan in the dashboard repo.

---

## 5. What Counts as a Call

A call is the agent's view on one stock on one day. It must be checkable at the moment it is made, which means it has to capture enough detail that nobody can argue later about what was meant.

### 5.1 Who gets a call

On every run1, Claude returns a call for every stock currently held in the paper portfolio and every candidate the screener passed in, whether or not it trades it. This is the key change. If only traded stocks are recorded, there is nothing to compare against, and "did it pick well" cannot be separated from "did the whole market go up".

### 5.2 What each call records

| Field | Meaning |
|---|---|
| Run date and run ID | Which run1 produced it |
| Ticker | The stock |
| Stance | Bullish, neutral, or bearish |
| Conviction | High, medium, or low, using the same scale the agent already uses for buys |
| Acted on | Whether this call turned into a buy, a sell, a hold of an existing position, or nothing |
| Reason | The one sentence Claude gave |
| Price at the time | The last price the agent saw when the call was made |
| VOO price at the time | So the call can be judged against the benchmark over the same window |
| Market direction | The market index reading the agent used that morning |
| Screener score and RSI | The numbers the screener produced |
| Signals | The list of signal names the screener produced |
| Strategy version | A short label for the prompt and strategy memory in force, so changes to the agent can be compared before and after |

### 5.3 Rules

- Calls are written once and never edited. The database must enforce this, not just the code.
- Outcomes live in a separate table and point back to the call.
- If the agent fails to produce a call for a holding, that gap is itself recorded as a missing call, not silently skipped.

---

## 6. Scoring

### 6.1 Horizons

Every call is scored at three horizons: 1 trading day, 5 trading days, and 20 trading days. Recording all three means Gary does not have to pick one up front, and the data will show which horizon the agent is actually good at. Because the price at the time is recorded, more horizons can be added later from price history without losing anything.

### 6.2 What an outcome records

For each call and horizon: the closing price at the end of the horizon, the stock's percent change, VOO's percent change over the same window, the difference between the two (excess return), and whether the call was a hit.

### 6.3 What a hit means

- A bullish call is a hit if the stock beat VOO over the horizon.
- A bearish call is a hit if the stock did worse than VOO over the horizon.
- A neutral call is recorded but left out of the headline hit rate. See open question Q3.

Beating VOO is used instead of simply going up, because in a rising market almost everything goes up and a plain "did it go up" score would flatter the agent.

### 6.4 The scoring step

A new command runs on the agent PC once a day after the US market closes. It looks for every call whose horizon has ended and has no outcome yet, pulls closing prices using the same market data library the agent already uses, and writes the outcomes. It must be safe to run twice, and if the PC was off for a few days it must catch up on everything it missed. Market holidays and half days follow the trading calendar, not the calendar week.

Trades get their own scoring too: for every closed trade, the realized return versus what VOO did over the same holding period.

---

## 7. Answering the Three Questions

These are delivered as saved views in Supabase so they can be queried directly and read by the dashboard.

| Question | View answers it by |
|---|---|
| When it liked a stock, did it go up? | Hit rate and average excess return of bullish calls, at each horizon |
| How accurate is it overall? | Overall hit rate, picked versus not picked, and cumulative excess return of acted-on calls versus VOO |
| Where is it most wrong? | Hit rate broken down by conviction, by market direction, by each signal, by ticker, by RSI band, and by strategy version |

### Small sample warning

The watchlist is 18 stocks, so the agent produces roughly 18 to 25 calls a day. After a month that is only a few hundred calls spread across many groups. Every view must show the number of calls next to every rate, and any group with fewer than 30 calls must be flagged as too small to trust. The dashboard should grey these out.

---

## 8. Alert-Only Notifications

### 8.1 What changes

The long run1 and run2 Telegram messages stop being sent as routine messages. The briefing, market summary, bilingual daily lesson, and trade reasoning do not disappear. They move to the dashboard and keep going into the daily journal for the vault.

Telegram gets a short alert digest instead, sent only when at least one alert rule fires.

### 8.2 Alert rules

All thresholds are settings, not hard-coded, so they can be tuned after a few weeks.

| Rule | Starting threshold |
|---|---|
| A holding moved sharply since the prior close | 4 percent either way |
| A holding is close to its stop-loss or profit target | Within 2 percent of the trigger |
| A stop-loss or profit target actually fired | Always |
| The agent bought or sold anything | Always |
| A watchlist stock moved sharply | 6 percent either way |
| A high-conviction call on a stock not yet held | Always |
| Market direction flipped from the previous run | Always |
| Portfolio fell behind VOO over the past 5 trading days | 3 percentage points |

### 8.3 Message format

- At most 5 points. If more than 5 rules fire, show the 5 most important and end with a line saying how many more are on the dashboard.
- Each point is one line: ticker, what happened, and the number.
- Only holdings and watchlist stocks. No general market commentary.
- A link to the dashboard at the bottom.
- Priority order when trimming: executed trades and triggered stops first, then near-trigger warnings, then big moves on holdings, then everything else.

### 8.4 Not repeating itself

The same alert for the same ticker is sent at most once per trading day. The intraday monitor, which runs every 30 minutes, must check what was already sent before sending again.

### 8.5 Staying visibly alive

Going quiet is only safe if Gary can tell the difference between "nothing happened" and "the agent died".

- **Failure alerts** always send immediately, as they do today, for any failed run, failed scoring step, or Supabase writes that are still failing after retries.
- **Heartbeat:** if no message of any kind has gone out for 3 trading days, send a single line saying the agent is running, how many runs completed, and the portfolio versus VOO.
- **Weekly digest** on Sunday stays, and gains one new line: the hit rate for the week at the 5 day horizon, with the call count.

### 8.6 Every alert is logged

Every alert, sent or suppressed as a duplicate, is written to an alerts table. That makes it possible to check later whether the alert rules are catching the right things.

---

## 9. Supabase

### 9.1 Project

A new, dedicated Supabase project for the agent, separate from the plant app. The free plan allows two active projects and this would be the second, so a third future project would need a paid plan or a shared project.

Free projects pause after a week with no activity. The agent writes every trading day, so this should never happen in practice, but a week of PC downtime would pause it. The heartbeat and failure alerts should mention if Supabase reports the project as paused.

### 9.2 What lives there

In plain terms, the project holds: one row per run with its status, market direction, briefing, and strategy version; the calls; the outcomes; the alerts; and a copy of trades, daily portfolio snapshots, and VOO benchmark snapshots for the dashboard.

### 9.3 Access and keys

- The agent writes using a server key kept in the agent PC's environment file. It is never committed to git and never pasted into chat.
- Row level security is turned on for every table.
- The dashboard reads through its own server-side functions on Vercel. The details are in the dashboard plan.
- The agent's write permissions on the calls table allow inserting new rows only, which is how the "never edited" rule is enforced.

### 9.4 When Supabase is unreachable

Trading must never wait on Supabase. If a write fails, the rows go into a local outbox file on the agent PC and are retried on the next run. Rows are identified so a retry never creates duplicates. If the outbox still has rows after 3 runs, a failure alert is sent.

---

## 10. Delivery Phases

Phase 1 should ship first and fast, because the data only starts piling up once it is switched on. Every day without it is a day of calls that can never be scored.

| Phase | What ships | Done when |
|---|---|---|
| 1. Start recording | Supabase project and tables, run1 asks Claude for a call on every holding and candidate, calls and runs are written with the outbox fallback | A full trading day of calls appears in Supabase, and pulling the network cable during a run still lets the run finish |
| 2. Score | The scoring command, trade scoring, and the saved views | Every call older than 1 trading day has a 1 day outcome, and each view returns results with counts |
| 3. Go quiet | Alert digest, dedupe, heartbeat, alerts table, weekly digest line | A normal day sends nothing, a test stop-loss sends one short message, and 3 silent days produce a heartbeat |
| 4. Dashboard | Covered by the plan in the dashboard repo | See that plan |
| 5. Retire the old path (optional) | Stop the hourly data.json commits to the dashboard repo once the Vercel dashboard has run cleanly for a week | Dashboard repo history stops growing with snapshot commits |
| 6. Backfill (optional) | Import trade decisions from the existing journal files as calls, marked as backfilled | Backfilled calls are clearly separated in every view, because they lack stances for untraded stocks and full signal data |

---

## 11. Open Questions

| ID | Question | Default if not answered |
|---|---|---|
| Q1 | Does "holdings" mean the paper portfolio only, or should Gary's real brokerage holdings be included too? | Paper portfolio only. Real holdings would need a manual list and would be a separate feature. |
| Q2 | Which horizon matters most for judging the agent: 1 day, 5 days, or 20 days? | Score all three. Use 5 days as the headline number on the dashboard and in the weekly digest. |
| Q3 | Should neutral calls be scored at all? | Record them, leave them out of the headline hit rate, and show them separately. |
| Q4 | Are the starting alert thresholds in 8.2 reasonable? | Use them for 2 weeks, then tune from the alerts table. |
| Q5 | Should the long-form daily lesson still come to Telegram on some cadence, since it is useful for learning? | No. It lives on the dashboard and in the vault journal. |
| Q6 | Is it acceptable to stop the hourly data.json commits to the dashboard repo after the move? | Yes, after one clean week on Vercel. |

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Asking Claude for a call on every stock makes the prompt longer and the output harder to parse | Keep each call to a stance, conviction, and one sentence. Treat a missing or malformed call as a recorded gap, never a crash. |
| Small sample size leads to false conclusions | Counts shown everywhere, small groups flagged, and lessons in strategy memory should cite the count they are based on. |
| The free market data source returns gaps or bad prices | Scoring skips and retries a missing price rather than writing a wrong outcome. A price that moved more than 50 percent in a day is held for a manual look. |
| Going quiet hides a dead agent | Heartbeat and failure alerts in 8.5. |
| A key leaks | Keys only in the environment file, never in git or chat, and can be rotated in Supabase without code changes. |
| Supabase free project pauses after downtime | Mentioned in alerts, and the outbox keeps data safe until it is restored. |

---

## 13. Acceptance Criteria

1. After a run1, every holding and every candidate has exactly one call for that run, or a recorded gap.
2. Attempting to change a stored call through the agent's key is rejected by the database.
3. After the scoring step, every call whose horizon has ended has an outcome, and running the step again changes nothing.
4. Each saved view returns a hit rate with a call count, and groups under 30 calls are flagged.
5. A day with no alert rules firing sends no routine Telegram message.
6. When rules fire, the message has at most 5 points, covers only holdings and the watchlist, and ends with the dashboard link.
7. The same alert for the same ticker is not sent twice in one trading day.
8. A heartbeat goes out after 3 trading days of silence.
9. With Supabase unreachable, run1, run2, and the monitor all finish, the rows land in the outbox, and they are written on the next successful run with no duplicates.
10. All existing tests still pass, and the new parts have tests in the same style.
