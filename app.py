"""Flask dashboard — MACD backtest viewer."""
import warnings
warnings.filterwarnings("ignore")

from flask import Flask, request, Response
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import pandas as pd

from data import load_ohlcv
import macd_bt as mb

app = Flask(__name__)

SYMBOLS = ["ETH/USDT:USDT", "SOL/USDT:USDT", "BTC/USDT:USDT",
           "DOGE/USDT:USDT", "XRP/USDT:USDT"]


def build_html(symbol, sl_pct, tp_pct, days_view):
    df_raw = load_ohlcv(symbol)
    df     = mb.add_indicators(df_raw)
    trades, equity = mb.run_backtest(df, sl_pct=sl_pct, tp_pct=tp_pct)
    stats  = mb.calc_stats(trades, equity)

    cutoff   = df.index[-1] - pd.Timedelta(days=days_view)
    df_view  = df[df.index >= cutoff]

    # MACD 4h
    df4h = df_raw.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    c4h      = df4h["close"]
    ema_fast = c4h.ewm(span=12, adjust=False).mean()
    ema_slow = c4h.ewm(span=26, adjust=False).mean()
    macd_l   = ema_fast - ema_slow
    sig_l    = macd_l.ewm(span=9, adjust=False).mean()
    hist_4h  = macd_l - sig_l
    df4h_view = df4h[df4h.index >= cutoff]
    hist_view = hist_4h[df4h_view.index]
    macd_view = macd_l[df4h_view.index]
    sig_view  = sig_l[df4h_view.index]

    def ts(bar): return df.index[bar]

    trades_in = [t for t in trades if ts(t.entry_bar) >= cutoff]
    long_ts  = [ts(t.entry_bar) for t in trades_in if t.side == "long"]
    long_px  = [t.entry_price   for t in trades_in if t.side == "long"]
    short_ts = [ts(t.entry_bar) for t in trades_in if t.side == "short"]
    short_px = [t.entry_price   for t in trades_in if t.side == "short"]
    win_ts   = [ts(t.exit_bar)  for t in trades_in if t.exit_bar and t.is_win]
    win_px   = [t.exit_price    for t in trades_in if t.exit_bar and t.is_win]
    loss_ts  = [ts(t.exit_bar)  for t in trades_in if t.exit_bar and not t.is_win]
    loss_px  = [t.exit_price    for t in trades_in if t.exit_bar and not t.is_win]

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.25, 0.20],
        vertical_spacing=0.02,
        subplot_titles=("Цена (15m)", "MACD 4h", "Equity"),
    )

    fig.add_trace(go.Candlestick(
        x=df_view.index,
        open=df_view["open"], high=df_view["high"],
        low=df_view["low"],   close=df_view["close"],
        name="Цена", showlegend=False,
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        increasing_fillcolor="#26a69a",  decreasing_fillcolor="#ef5350",
    ), row=1, col=1)

    if long_ts:
        fig.add_trace(go.Scatter(x=long_ts, y=long_px, mode="markers",
            marker=dict(symbol="triangle-up", size=13, color="#2196F3",
                        line=dict(color="#fff", width=1)),
            name="Long вход"), row=1, col=1)
    if short_ts:
        fig.add_trace(go.Scatter(x=short_ts, y=short_px, mode="markers",
            marker=dict(symbol="triangle-down", size=13, color="#FF9800",
                        line=dict(color="#fff", width=1)),
            name="Short вход"), row=1, col=1)
    if win_ts:
        fig.add_trace(go.Scatter(x=win_ts, y=win_px, mode="markers",
            marker=dict(symbol="x", size=11, color="#4CAF50", line=dict(width=2)),
            name="WIN"), row=1, col=1)
    if loss_ts:
        fig.add_trace(go.Scatter(x=loss_ts, y=loss_px, mode="markers",
            marker=dict(symbol="x", size=11, color="#ef5350", line=dict(width=2)),
            name="LOSS"), row=1, col=1)

    hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in hist_view.values]
    fig.add_trace(go.Bar(x=df4h_view.index, y=hist_view.values,
        marker_color=hist_colors, name="Histogram", showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df4h_view.index, y=macd_view.values,
        line=dict(color="#2196F3", width=1.5), name="MACD"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df4h_view.index, y=sig_view.values,
        line=dict(color="#FF9800", width=1.5), name="Signal"), row=2, col=1)
    fig.add_hline(y=0, line_color="#555", line_width=1, row=2, col=1)

    eq_series = pd.Series(equity, index=df.index)
    eq_view   = eq_series[eq_series.index >= cutoff]
    fig.add_trace(go.Scatter(x=eq_view.index, y=eq_view.values,
        fill="tozeroy", line=dict(color="#7E57C2", width=2),
        fillcolor="rgba(126,87,194,0.15)", name="Equity", showlegend=False), row=3, col=1)

    fig.update_layout(
        height=820, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#e0e0e0", size=12),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1f2937", zeroline=False, row=i, col=1)
        fig.update_yaxes(gridcolor="#1f2937", zeroline=False, row=i, col=1)

    chart_html = pio.to_html(fig, full_html=False, include_plotlyjs=True)

    s = stats or {}
    pf_color = "color:#4CAF50" if s.get("profit_factor", 0) >= 1 else "color:#ef5350"
    rt_color = "color:#4CAF50" if s.get("total_return", 0) >= 0 else "color:#ef5350"

    # Таблица ордеров
    closed = [t for t in reversed(trades) if t.exit_reason != "end_of_data"]
    open_t = [t for t in trades if t.exit_reason == "end_of_data"]

    def trade_rows(trade_list, badge):
        rows = ""
        for t in trade_list:
            side_s = f'<span style="color:#2196F3">LONG</span>' if t.side == "long" \
                     else f'<span style="color:#FF9800">SHORT</span>'
            pnl_c  = "#4CAF50" if t.is_win else "#ef5350"
            xts    = df.index[t.exit_bar].strftime("%Y-%m-%d %H:%M") if t.exit_bar else "—"
            xpx    = f"{t.exit_price:.4f}" if t.exit_price else "—"
            reason = t.exit_reason or "open"
            rows += (
                f"<tr>"
                f"<td>{df.index[t.entry_bar].strftime('%Y-%m-%d %H:%M')}</td>"
                f"<td>{xts}</td><td>{side_s}</td>"
                f"<td>{t.entry_price:.4f}</td><td>{xpx}</td>"
                f"<td style='color:{pnl_c}'>{t.pnl_pct*100:+.2f}%</td>"
                f"<td>{reason}</td><td>{badge}</td>"
                f"</tr>\n"
            )
        return rows

    table_rows = ""
    for t in open_t:
        table_rows += trade_rows([t], "🟡")
    table_rows += trade_rows(closed, "")

    sym_options = "".join(
        f'<option value="{s}" {"selected" if s == symbol else ""}>{s}</option>'
        for s in SYMBOLS
    )

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIBot Dashboard</title>
<style>
  body{{margin:0;background:#0e1117;color:#e0e0e0;font-family:sans-serif;font-size:13px}}
  h1{{margin:12px 16px 4px;font-size:18px;color:#00bcd4}}
  .metrics{{display:flex;gap:16px;padding:8px 16px;background:#1a1f2e;flex-wrap:wrap}}
  .metric{{text-align:center}}
  .metric .label{{font-size:11px;color:#888}}
  .metric .value{{font-size:16px;font-weight:bold}}
  form{{display:flex;gap:12px;align-items:center;padding:8px 16px;background:#111827;flex-wrap:wrap}}
  select,input{{background:#1f2937;color:#e0e0e0;border:1px solid #374151;padding:4px 8px;border-radius:4px}}
  button{{background:#2196F3;color:#fff;border:none;padding:6px 14px;border-radius:4px;cursor:pointer}}
  table{{width:100%;border-collapse:collapse;margin:8px 0}}
  th{{background:#1f2937;padding:6px 8px;text-align:left}}
  td{{padding:5px 8px;border-bottom:1px solid #1f2937}}
  tr:hover td{{background:#1a2030}}
  .section{{padding:0 16px 16px}}
</style>
</head>
<body>
<h1>📈 AIBot — MACD Crossover</h1>
<form method="get">
  <label>Символ: <select name="symbol">{sym_options}</select></label>
  <label>SL %: <input name="sl" type="number" step="0.5" min="0.5" max="5" value="{sl_pct*100:.1f}" style="width:60px"></label>
  <label>TP %: <input name="tp" type="number" step="0.5" min="1" max="10" value="{tp_pct*100:.1f}" style="width:60px"></label>
  <label>Дней: <input name="days" type="number" step="30" min="30" max="730" value="{days_view}" style="width:70px"></label>
  <button type="submit">Обновить</button>
</form>
<div class="metrics">
  <div class="metric"><div class="label">Сделок</div><div class="value">{s.get('n_trades',0)}</div></div>
  <div class="metric"><div class="label">Win Rate</div><div class="value">{s.get('win_rate',0):.1f}%</div></div>
  <div class="metric"><div class="label">Profit Factor</div><div class="value" style="{pf_color}">{s.get('profit_factor',0):.2f}</div></div>
  <div class="metric"><div class="label">Доходность</div><div class="value" style="{rt_color}">{s.get('total_return',0):+.1f}%</div></div>
  <div class="metric"><div class="label">Max Drawdown</div><div class="value" style="color:#ef5350">{s.get('max_drawdown',0):.1f}%</div></div>
  <div class="metric"><div class="label">Sharpe</div><div class="value">{s.get('sharpe',0):.2f}</div></div>
  <div class="metric"><div class="label">SL / TP</div><div class="value">{sl_pct*100:.1f}% / {tp_pct*100:.1f}%</div></div>
</div>
<div class="section">CHART_PLACEHOLDER</div>
<div class="section">
  <h2 style="font-size:15px">Ордера ({len(trades)} всего)</h2>
  <table>
    <tr><th>Вход</th><th>Выход</th><th>Сторона</th><th>Вход $</th><th>Выход $</th><th>PnL %</th><th>Причина</th><th></th></tr>
    {table_rows}
  </table>
</div>
</body>
</html>"""
    return page.replace("CHART_PLACEHOLDER", chart_html)


@app.route("/")
def index():
    symbol   = request.args.get("symbol", "ETH/USDT:USDT")
    sl_pct   = float(request.args.get("sl", 1.0)) / 100
    tp_pct   = float(request.args.get("tp", 2.0)) / 100
    days_view = int(request.args.get("days", 365))
    if symbol not in SYMBOLS:
        symbol = "ETH/USDT:USDT"
    html = build_html(symbol, sl_pct, tp_pct, days_view)
    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
