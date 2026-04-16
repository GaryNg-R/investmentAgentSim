"""HTML dashboard generator for the investment agent portfolio."""

import html as _html
import json
import os
from datetime import datetime, timezone

from agent.portfolio.database import DB_PATH, get_connection, init_db
from agent.portfolio.engine import STARTING_CASH

TARGET_VALUE = 11_500.0


def generate_dashboard(db_path: str = DB_PATH, output_path: str = "output/dashboard.html") -> str:
    """
    Reads portfolio data from SQLite, generates self-contained HTML, writes to output_path.
    Returns the output_path string.
    Creates output/ directory if it doesn't exist.
    Never raises — on error, writes a minimal error HTML and returns output_path.
    """
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    except Exception:
        pass

    try:
        html = _build_html(db_path)
    except Exception as exc:
        html = _error_html(str(exc))

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as exc:
        # Last-resort: try writing error HTML
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(_error_html(str(exc)))
        except Exception:
            pass

    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Dashboard Error</title></head>
<body><h1>Dashboard Error</h1><pre>{message}</pre></body></html>"""


def _build_html(db_path: str) -> str:
    # Ensure DB is initialised (idempotent)
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        # --- account ---
        cash_row = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()
        cash = cash_row["cash"] if cash_row else 0.0

        # --- positions ---
        pos_rows = conn.execute(
            "SELECT ticker, shares, avg_cost FROM positions ORDER BY ticker"
        ).fetchall()
        positions = [
            {"ticker": r["ticker"], "shares": r["shares"], "avg_cost": r["avg_cost"]}
            for r in pos_rows
        ]

        # --- trades (all, newest first) ---
        trade_rows = conn.execute(
            "SELECT id, timestamp, action, ticker, shares, price, total, reasoning "
            "FROM trades ORDER BY timestamp DESC, id DESC"
        ).fetchall()
        trades = [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "action": r["action"],
                "ticker": r["ticker"],
                "shares": r["shares"],
                "price": r["price"],
                "total": r["total"],
                "reasoning": r["reasoning"] or "",
            }
            for r in trade_rows
        ]

        # --- daily snapshots (last 30, oldest first for chart) ---
        snap_rows = conn.execute(
            "SELECT date, total_value, cash, pnl_pct FROM daily_snapshots "
            "ORDER BY date DESC LIMIT 30"
        ).fetchall()
        snapshots = list(reversed([
            {"date": r["date"], "total_value": r["total_value"],
             "cash": r["cash"], "pnl_pct": r["pnl_pct"]}
            for r in snap_rows
        ]))
    finally:
        conn.close()

    # --- computed values ---
    total_invested = sum(p["shares"] * p["avg_cost"] for p in positions)
    total_value = cash + total_invested
    pnl_dollar = total_value - STARTING_CASH
    pnl_pct = (pnl_dollar / STARTING_CASH) * 100.0
    progress_pct = min(100.0, max(0.0, (total_value - STARTING_CASH) / (TARGET_VALUE - STARTING_CASH) * 100.0))

    # Format helpers
    def fmt_dollar(v):
        return f"${v:,.2f}"

    def fmt_pnl(dollar, pct):
        sign = "+" if dollar >= 0 else ""
        return f"{sign}{fmt_dollar(dollar)} ({sign}{pct:.1f}%)"

    pnl_color = "#2ecc71" if pnl_dollar >= 0 else "#e74c3c"
    pnl_str = fmt_pnl(pnl_dollar, pnl_pct)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # --- positions table rows ---
    if positions:
        pos_rows_html = ""
        for p in positions:
            pos_val = p["shares"] * p["avg_cost"]
            pct_of_port = (pos_val / total_value * 100.0) if total_value > 0 else 0.0
            pos_rows_html += f"""
            <tr>
                <td><strong>{_html.escape(p['ticker'])}</strong></td>
                <td>{p['shares']:.4f}</td>
                <td>{fmt_dollar(p['avg_cost'])}</td>
                <td>{fmt_dollar(pos_val)}</td>
                <td>{pct_of_port:.1f}%</td>
            </tr>"""
        positions_body = pos_rows_html
    else:
        positions_body = '<tr><td colspan="5" class="empty-msg">No open positions</td></tr>'

    # --- trades table rows ---
    if trades:
        trade_rows_html = ""
        for t in trades:
            action_class = "buy" if t["action"] == "BUY" else "sell"
            date_str = t["timestamp"][:10] if t["timestamp"] else ""
            reasoning_short = (t["reasoning"][:80] + "…") if len(t["reasoning"]) > 80 else t["reasoning"]
            trade_rows_html += f"""
            <tr>
                <td>{date_str}</td>
                <td><span class="action-badge {action_class}">{_html.escape(t['action'])}</span></td>
                <td><strong>{_html.escape(t['ticker'])}</strong></td>
                <td>{t['shares']:.4f}</td>
                <td>{fmt_dollar(t['price'])}</td>
                <td>{fmt_dollar(t['total'])}</td>
                <td class="reasoning">{_html.escape(reasoning_short)}</td>
            </tr>"""
        trades_body = trade_rows_html
    else:
        trades_body = '<tr><td colspan="7" class="empty-msg">No trades yet</td></tr>'

    # --- chart data ---
    if snapshots:
        chart_labels = json.dumps([s["date"] for s in snapshots])
        chart_values = json.dumps([s["total_value"] for s in snapshots])
        chart_html = f"""
        <div class="chart-container">
            <canvas id="portfolioChart"></canvas>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        (function() {{
            const ctx = document.getElementById('portfolioChart').getContext('2d');
            const labels = {chart_labels};
            const values = {chart_values};
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: 'Portfolio Value',
                            data: values,
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52,152,219,0.1)',
                            borderWidth: 2,
                            pointRadius: 3,
                            fill: true,
                            tension: 0.3,
                        }},
                        {{
                            label: 'Starting Capital ($10,000)',
                            data: new Array(labels.length).fill({STARTING_CASH}),
                            borderColor: '#95a5a6',
                            borderDash: [6, 4],
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false,
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: '30-Day Portfolio Value',
                            color: '#ecf0f1',
                            font: {{ size: 16 }}
                        }},
                        legend: {{ labels: {{ color: '#bdc3c7' }} }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ color: '#bdc3c7' }}, grid: {{ color: '#2c3e50' }} }},
                        y: {{ ticks: {{ color: '#bdc3c7', callback: v => '$' + v.toLocaleString() }}, grid: {{ color: '#2c3e50' }} }}
                    }}
                }}
            }});
        }})();
        </script>"""
    else:
        chart_html = '<p class="empty-msg">No performance data yet</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Investment Portfolio Dashboard</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #ecf0f1;
            line-height: 1.6;
            padding: 1.5rem;
        }}
        h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
        h2 {{ font-size: 1.15rem; margin-bottom: 0.75rem; color: #bdc3c7; letter-spacing: 0.05em; text-transform: uppercase; }}
        section {{ background: #16213e; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
        /* Summary bar */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 1.25rem;
        }}
        .stat-card {{
            background: #0f3460;
            border-radius: 8px;
            padding: 1rem 1.25rem;
        }}
        .stat-label {{ font-size: 0.75rem; color: #95a5a6; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-value {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.2rem; }}
        /* Progress bar */
        .progress-wrap {{ margin-top: 0.5rem; }}
        .progress-label {{ font-size: 0.85rem; color: #bdc3c7; margin-bottom: 0.4rem; }}
        .progress-bar-bg {{
            background: #0f3460;
            border-radius: 99px;
            height: 12px;
            overflow: hidden;
        }}
        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #3498db, #2ecc71);
            border-radius: 99px;
            transition: width 0.4s ease;
        }}
        /* Tables */
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
        th {{
            text-align: left;
            padding: 0.6rem 0.75rem;
            background: #0f3460;
            color: #95a5a6;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid #1e2d4a; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: rgba(255,255,255,0.03); }}
        .empty-msg {{ color: #7f8c8d; text-align: center; padding: 1.5rem; font-style: italic; }}
        /* Action badges */
        .action-badge {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.05em;
        }}
        .action-badge.buy {{ background: rgba(46,204,113,0.2); color: #2ecc71; }}
        .action-badge.sell {{ background: rgba(231,76,60,0.2); color: #e74c3c; }}
        /* Chart */
        .chart-container {{ position: relative; max-height: 350px; }}
        /* Footer */
        footer {{ text-align: center; color: #7f8c8d; font-size: 0.78rem; margin-top: 1rem; }}
        .reasoning {{ color: #95a5a6; font-size: 0.82rem; max-width: 260px; }}
    </style>
</head>
<body>

<section>
    <h1>Investment Portfolio Dashboard</h1>
    <div class="summary-grid" style="margin-top:1rem;">
        <div class="stat-card">
            <div class="stat-label">Total Portfolio Value</div>
            <div class="stat-value">{fmt_dollar(total_value)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Cash Available</div>
            <div class="stat-value">{fmt_dollar(cash)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">P&amp;L</div>
            <div class="stat-value" style="color:{pnl_color};">{pnl_str}</div>
        </div>
    </div>
    <div class="progress-wrap">
        <div class="progress-label">
            Portfolio: {fmt_dollar(total_value)} / {fmt_dollar(TARGET_VALUE)} goal &mdash; {progress_pct:.0f}% of the way there
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width:{progress_pct:.1f}%;"></div>
        </div>
    </div>
</section>

<section>
    <h2>Open Positions</h2>
    <table>
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Shares</th>
                <th>Avg Cost</th>
                <th>Position Value</th>
                <th>% of Portfolio</th>
            </tr>
        </thead>
        <tbody>
            {positions_body}
        </tbody>
    </table>
</section>

<section>
    <h2>Trade History</h2>
    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Action</th>
                <th>Ticker</th>
                <th>Shares</th>
                <th>Price</th>
                <th>Total</th>
                <th>Reasoning</th>
            </tr>
        </thead>
        <tbody>
            {trades_body}
        </tbody>
    </table>
</section>

<section>
    <h2>30-Day Portfolio Value</h2>
    {chart_html}
</section>

<footer>Last updated: {generated_at}</footer>

</body>
</html>"""

    return html
