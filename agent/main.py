"""
main.py — CLI router for the AI Investment Agent.

Usage: python -m agent.main <command>

Commands:
  run1       Scan market, ask Claude for a trade plan (6:00 AM PT)
  run2       Execute the trade plan from run1 (6:30 AM PT)
  monitor    Check stop-loss/profit targets on open positions (every 30 min)
  history    Print trade history and portfolio summary
  dashboard  Regenerate the HTML dashboard
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

from agent.portfolio.database import DB_PATH, get_connection, init_db  # FEAT-002: added get_connection
from agent.portfolio.engine import (
    execute_buy,
    execute_sell,
    get_portfolio_status,
    get_trade_history,
    save_daily_snapshot,
)
from agent.tools.dashboard import generate_dashboard
from agent.tools.market_index import get_market_direction
from agent.tools.risk_rules import (
    check_profit_target,
    check_stop_loss,
    position_size_from_conviction,
    validate_buy,
    validate_sell,
)
from agent.tools.screener import screen_stocks
from agent.tools.stock_data import get_price
from agent.claude_agent import run_analysis
from agent.tools.notify import notify_error, notify_run1, notify_run2, notify_weekly
from agent.tools.weekly_report import build_weekly_report  # FEAT-004
from agent.tools.benchmark import update_benchmark  # FEAT-002

import os as _os

_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
PLAN_PATH = _os.path.join(_PROJECT_ROOT, "data", "run1_plan.json")
OUTPUT_PATH = _os.path.join(_PROJECT_ROOT, "output", "dashboard.html")

USAGE = """\
AI Investment Agent — Paper Trading
Usage: python -m agent.main <command>

Commands:
  run1       Scan market, ask Claude for a trade plan (6:00 AM PT)
  run2       Execute the trade plan from run1 (6:30 AM PT)
  monitor    Check stop-loss/profit targets on open positions (every 30 min)
  history    Print trade history and portfolio summary
  dashboard  Regenerate the HTML dashboard
  weekly     Build and send the weekly performance digest to Telegram (Sunday 1pm PT)

Cron setup (edit with `crontab -e`):
  0 14 * * 1-5  cd /path/to/investmentAgent && python -m agent.main run1 >> logs/agent.log 2>&1
  30 14 * * 1-5 cd /path/to/investmentAgent && python -m agent.main run2 >> logs/agent.log 2>&1
  */30 15-21 * * 1-5 cd /path/to/investmentAgent && python -m agent.main monitor >> logs/agent.log 2>&1
  0 20 * * 0  cd /path/to/investmentAgent && python -m agent.main weekly >> logs/agent.log 2>&1
"""


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_run1(db_path: str = DB_PATH, plan_path: str = PLAN_PATH) -> None:
    """Scan market, ask Claude for a trade plan, save to data/run1_plan.json."""
    try:
        init_db(db_path)
        market_direction = get_market_direction()
        screened_stocks = screen_stocks(market_direction["direction"])
        portfolio = get_portfolio_status(db_path)
        decisions = run_analysis(market_direction, portfolio, screened_stocks, plan_path)

        print(decisions["briefing"])
        if decisions["briefing"].startswith("Analysis failed:"):
            sys.exit(1)
        for trade in decisions.get("trades", []):
            action = trade.get("action", "")
            ticker = trade.get("ticker", "")
            shares = trade.get("shares", 0)
            reasoning = trade.get("reasoning", "")
            print(f"PLAN: {action} {shares} {ticker} — {reasoning}")

        print(f"Plan saved to {plan_path}")
        notify_run1(  # FEAT-001: pass bilingual education fields
            decisions["briefing"],
            decisions.get("trades", []),
            market_direction["direction"],
            market_education=decisions.get("market_education", {}),
            daily_lesson=decisions.get("daily_lesson", {}),
        )
    except Exception as exc:
        notify_error("run1", str(exc))
        print(f"Error: {exc}")
        sys.exit(1)


def cmd_run2(db_path: str = DB_PATH, plan_path: str = PLAN_PATH, output_path: str = OUTPUT_PATH) -> None:
    """Execute the trade plan from run1."""
    try:
        init_db(db_path)

        # FEAT-002: Monday $100 deposit into agent cash — idempotent via benchmark_snapshots
        if date.today().weekday() == 0:
            _today_str = date.today().isoformat()
            _dep_conn = get_connection(db_path)
            try:
                _already = _dep_conn.execute(
                    "SELECT 1 FROM benchmark_snapshots WHERE date=?", (_today_str,)
                ).fetchone()
                if not _already:
                    _dep_conn.execute("UPDATE account SET cash = cash + 100.0 WHERE id = 1")
                    _dep_conn.commit()
                    print("Monday deposit: +$100 added to agent cash")
            finally:
                _dep_conn.close()

        # Load the plan
        try:
            with open(plan_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            print("Error: run1 plan not found. Run `python -m agent.main run1` first.")
            sys.exit(1)

        decisions = payload.get("decisions", payload)

        # Guard: skip all trades outside NYSE market hours (9:30am–4:00pm ET, Mon–Fri)
        _et = ZoneInfo("America/New_York")
        _now_et = datetime.now(_et)
        _market_open = dtime(9, 30)
        _market_close = dtime(16, 0)
        _is_market_hours = (
            _now_et.weekday() < 5
            and _market_open <= _now_et.time() < _market_close
        )
        if not _is_market_hours:
            print(f"Market closed ({_now_et.strftime('%H:%M ET %a')}) — skipping all trades")
            decisions = {**decisions, "trades": []}

        if decisions.get("skip_new_buys", False):
            print("Skipping new buys (risk-off day)")

        portfolio = get_portfolio_status(db_path)
        executed: list[str] = []
        rejected: list[str] = []

        for trade in decisions.get("trades", []):
            action = trade.get("action", "")
            ticker = trade.get("ticker", "")
            shares = trade.get("shares", 0)
            reasoning = trade.get("reasoning", "")

            current_price = get_price(ticker)
            if current_price is None:
                print(f"Could not fetch price for {ticker}, skipping")
                continue

            if action == "BUY":
                if decisions.get("skip_new_buys", False):
                    print(f"Skipped BUY {ticker} (risk-off)")
                    continue
                # FEAT-003: derive shares from conviction + current price
                conviction = trade.get("conviction", "medium")
                dollar_amount = position_size_from_conviction(conviction, portfolio["cash"])
                shares = int(dollar_amount / current_price)
                valid, reason = validate_buy(ticker, shares, current_price, portfolio)
                if valid:
                    execute_buy(ticker, shares, current_price, reasoning, db_path)
                    msg = f"BUY {shares} {ticker} @ ${current_price:.2f}"
                    print(f"EXECUTED: {msg}")
                    executed.append(msg)
                else:
                    msg = f"BUY {ticker} — {reason}"
                    print(f"REJECTED: {msg}")
                    rejected.append(msg)

            elif action == "SELL":
                valid, reason = validate_sell(ticker, shares, portfolio)
                if valid:
                    execute_sell(ticker, shares, current_price, reasoning, db_path)
                    msg = f"SELL {shares} {ticker} @ ${current_price:.2f}"
                    print(f"EXECUTED: {msg}")
                    executed.append(msg)
                else:
                    msg = f"SELL {ticker} — {reason}"
                    print(f"REJECTED: {msg}")
                    rejected.append(msg)

            # Refresh portfolio after each trade
            portfolio = get_portfolio_status(db_path)

        # Save daily snapshot
        today = date.today().isoformat()
        portfolio = get_portfolio_status(db_path)
        save_daily_snapshot(today, portfolio["total_value"], portfolio["cash"], portfolio["pnl_pct"], db_path)

        benchmark = update_benchmark(db_path)  # FEAT-002: must run before dashboard

        # Regenerate dashboard
        generate_dashboard(db_path, output_path)

        # Print final portfolio status
        print(
            f"Cash: ${portfolio['cash']:,.2f} | "
            f"Total Value: ${portfolio['total_value']:,.2f} | "
            f"P&L: {portfolio['pnl_pct']:+.2f}%"
        )
        notify_run2(executed, rejected, portfolio, benchmark=benchmark)  # FEAT-002
    except SystemExit:
        raise
    except Exception as exc:
        notify_error("run2", str(exc))
        print(f"Error: {exc}")
        sys.exit(1)


def cmd_monitor(db_path: str = DB_PATH, output_path: str = OUTPUT_PATH) -> None:
    """Intraday stop-loss and profit-target checker."""
    try:
        init_db(db_path)
        portfolio = get_portfolio_status(db_path)

        if not portfolio["positions"]:
            print("No open positions to monitor")
            return

        any_sells = False

        for pos in portfolio["positions"]:
            try:
                ticker = pos["ticker"]
                shares = int(pos["shares"])
                avg_cost = pos["avg_cost"]
                current_price = get_price(ticker)
                if current_price is None:
                    print(f"  {ticker}: could not fetch price, skipping")
                    continue
                if check_stop_loss(ticker, current_price, avg_cost):
                    execute_sell(ticker, shares, current_price, "stop-loss triggered", db_path=db_path)
                    print(f"  STOP-LOSS: sold {shares} {ticker} @ ${current_price:.2f}")
                    any_sells = True
                elif check_profit_target(ticker, current_price, avg_cost):
                    execute_sell(ticker, shares, current_price, "profit target hit", db_path=db_path)
                    print(f"  PROFIT TARGET: sold {shares} {ticker} @ ${current_price:.2f}")
                    any_sells = True
                else:
                    pct = (current_price / avg_cost - 1) * 100
                    print(f"  {ticker}: ${current_price:.2f} (cost ${avg_cost:.2f}, {pct:+.1f}%)")
            except Exception as exc:
                print(f"  Warning: could not process {pos.get('ticker', '?')}: {exc}")

        if any_sells:
            portfolio = get_portfolio_status(db_path)
            today = date.today().isoformat()
            save_daily_snapshot(today, portfolio["total_value"], portfolio["cash"], portfolio["pnl_pct"], db_path)
            generate_dashboard(db_path, output_path)

        print("Monitor complete")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def cmd_history(db_path: str = DB_PATH) -> None:
    """Print trade history table and portfolio summary."""
    try:
        init_db(db_path)
        trades = get_trade_history(limit=100, db_path=db_path)
        if len(trades) == 100:
            print("(Showing most recent 100 trades)")
        portfolio = get_portfolio_status(db_path)

        try:
            from tabulate import tabulate
            headers = ["Date", "Action", "Ticker", "Shares", "Price", "Total", "Reasoning"]
            rows = []
            for t in trades:
                date_str = t["timestamp"][:10] if t.get("timestamp") else ""
                reasoning = t.get("reasoning") or ""
                if len(reasoning) > 60:
                    reasoning = reasoning[:57] + "..."
                rows.append([
                    date_str,
                    t.get("action", ""),
                    t.get("ticker", ""),
                    t.get("shares", 0),
                    f"${t.get('price', 0.0):.2f}",
                    f"${t.get('total', 0.0):.2f}",
                    reasoning,
                ])
            print(tabulate(rows, headers=headers, tablefmt="simple"))
        except ImportError:
            # Fallback if tabulate not installed
            print(f"{'Date':<12} {'Action':<6} {'Ticker':<8} {'Shares':<8} {'Price':<10} {'Total':<10} Reasoning")
            print("-" * 80)
            for t in trades:
                date_str = t["timestamp"][:10] if t.get("timestamp") else ""
                reasoning = t.get("reasoning") or ""
                if len(reasoning) > 60:
                    reasoning = reasoning[:57] + "..."
                print(
                    f"{date_str:<12} {t.get('action',''):<6} {t.get('ticker',''):<8} "
                    f"{t.get('shares',0):<8} ${t.get('price',0.0):<9.2f} ${t.get('total',0.0):<9.2f} {reasoning}"
                )

        total_trades = len(trades)
        total_value = portfolio["total_value"]
        pnl_pct = portfolio["pnl_pct"]
        print(f"Total trades: {total_trades} | Portfolio: ${total_value:,.2f} | P&L: {pnl_pct:+.1f}%")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def cmd_dashboard(db_path: str = DB_PATH, output_path: str = OUTPUT_PATH) -> None:
    """Regenerate the HTML dashboard."""
    try:
        init_db(db_path)
        path = generate_dashboard(db_path, output_path)
        print(f"Dashboard regenerated: {path}")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def cmd_weekly(db_path: str = DB_PATH) -> None:  # FEAT-004
    """Build and send the weekly performance digest to Telegram."""
    try:
        init_db(db_path)
        report = build_weekly_report(db_path)
        notify_weekly(report)
        print("Weekly digest sent")
    except Exception as exc:
        notify_error("weekly", str(exc))
        print(f"Error: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def main(args: list[str]) -> None:
    """Route CLI arguments to the correct command function."""
    if not args:
        print(USAGE)
        sys.exit(1)

    command = args[0]

    if command == "run1":
        cmd_run1()
    elif command == "run2":
        cmd_run2()
    elif command == "monitor":
        cmd_monitor()
    elif command == "history":
        cmd_history()
    elif command == "dashboard":
        cmd_dashboard()
    elif command == "weekly":
        cmd_weekly()
    else:
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
