"""Flask dashboard — server-side PNG charts via matplotlib."""
import warnings, io, base64, os
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from flask import Flask, Response

from data import load_ohlcv
import macd_bt as mb

app = Flask(__name__)

SYMBOL    = "ETH/USDT:USDT"
SL_PCT    = 0.010
TP_PCT    = 0.020
DAYS_VIEW = 90

BG   = "#0e1117"
GRID = "#1f2937"

print("Загрузка данных…", flush=True)
_df_raw = load_ohlcv(SYMBOL)
_df     = mb.add_indicators(_df_raw)
_trades, _equity = mb.run_backtest(_df, sl_pct=SL_PCT, tp_pct=TP_PCT)
_stats  = mb.calc_stats(_trades, _equity)
print(f"Сделок: {_stats['n_trades']}", flush=True)


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _make_page() -> str:
    cutoff = _df.index[-1] - pd.Timedelta(days=DAYS_VIEW)

    df4h = _df_raw.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    dv4h = df4h[df4h.index >= cutoff]

    c4h   = df4h["close"]
    macd_ = c4h.ewm(span=12, adjust=False).mean() - c4h.ewm(span=26, adjust=False).mean()
    sig_  = macd_.ewm(span=9, adjust=False).mean()
    hist_ = macd_ - sig_
    macd_v = macd_[dv4h.index]
    sig_v  = sig_[dv4h.index]
    hist_v = hist_[dv4h.index]

    eq = pd.Series(_equity, index=_df.index).resample("4h").last().dropna()
    eq_v = eq[eq.index >= cutoff]

    # ── Цена + маркеры ─────────────────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(14, 4), facecolor=BG)
    ax1.set_facecolor(BG)
    ax1.plot(dv4h.index, dv4h["close"], color="#26a69a", linewidth=1)

    for t in _trades:
        entry_t = _df.index[t.entry_bar]
        if entry_t < cutoff:
            continue
        ep = t.entry_price
        color = "#2196F3" if t.side == "long" else "#FF9800"
        marker = "^" if t.side == "long" else "v"
        ax1.scatter(entry_t, ep, color=color, marker=marker, s=40, zorder=5)
        if t.exit_bar and t.exit_price:
            exit_t = _df.index[t.exit_bar]
            if exit_t >= cutoff:
                ec = "#4CAF50" if t.is_win else "#ef5350"
                ax1.scatter(exit_t, t.exit_price, color=ec, marker="o", s=25, zorder=5)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax1.tick_params(colors="#9ca3af", labelsize=8)
    ax1.grid(color=GRID, linewidth=0.5)
    for sp in ax1.spines.values():
        sp.set_color(GRID)
    ax1.set_title("ETH/USDT 4h", color="#9ca3af", fontsize=9, pad=4)
    img1 = _fig_to_b64(fig1)

    # ── MACD ───────────────────────────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(14, 2.2), facecolor=BG)
    ax2.set_facecolor(BG)
    colors = ["#26a69a" if v >= 0 else "#ef5350" for v in hist_v]
    ax2.bar(hist_v.index, hist_v.values, color=colors, width=pd.Timedelta(hours=3.5))
    ax2.plot(macd_v.index, macd_v.values, color="#2196F3", linewidth=0.8)
    ax2.plot(sig_v.index,  sig_v.values,  color="#FF9800", linewidth=0.8)
    ax2.axhline(0, color=GRID, linewidth=0.5)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax2.tick_params(colors="#9ca3af", labelsize=8)
    ax2.grid(color=GRID, linewidth=0.5)
    for sp in ax2.spines.values():
        sp.set_color(GRID)
    ax2.set_title("MACD(12,26,9)", color="#9ca3af", fontsize=9, pad=4)
    img2 = _fig_to_b64(fig2)

    # ── Equity ─────────────────────────────────────────────────────────────
    fig3, ax3 = plt.subplots(figsize=(14, 1.8), facecolor=BG)
    ax3.set_facecolor(BG)
    ax3.fill_between(eq_v.index, eq_v.values, alpha=0.3, color="#7E57C2")
    ax3.plot(eq_v.index, eq_v.values, color="#7E57C2", linewidth=1)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax3.tick_params(colors="#9ca3af", labelsize=8)
    ax3.grid(color=GRID, linewidth=0.5)
    for sp in ax3.spines.values():
        sp.set_color(GRID)
    ax3.set_title("Equity", color="#9ca3af", fontsize=9, pad=4)
    img3 = _fig_to_b64(fig3)

    # ── Таблица ────────────────────────────────────────────────────────────
    rows = ""
    for t in list(t for t in _trades if t.exit_reason == "end_of_data") + \
             list(reversed([t for t in _trades if t.exit_reason != "end_of_data"])):
        sc = "#2196F3" if t.side == "long" else "#FF9800"
        pc = "#4CAF50" if t.is_win else "#ef5350"
        xts = _df.index[t.exit_bar].strftime("%m-%d %H:%M") if t.exit_bar else "—"
        xpx = f"{t.exit_price:.2f}" if t.exit_price else "—"
        rows += (f"<tr><td>{_df.index[t.entry_bar].strftime('%m-%d %H:%M')}</td>"
                 f"<td>{xts}</td><td style='color:{sc}'>{t.side.upper()}</td>"
                 f"<td>{t.entry_price:.2f}</td><td>{xpx}</td>"
                 f"<td style='color:{pc}'>{t.pnl_pct*100:+.2f}%</td>"
                 f"<td>{t.exit_reason or 'open'}</td></tr>")

    s    = _stats
    pf_c = "#4CAF50" if s.get("profit_factor", 0) >= 1 else "#ef5350"
    rt_c = "#4CAF50" if s.get("total_return", 0) >= 0  else "#ef5350"

    return (
        "<!DOCTYPE html><html lang='ru'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>AIBot</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0}"
        f"body{{background:{BG};color:#e0e0e0;font-family:sans-serif;font-size:13px}}"
        "h1{padding:8px 12px;font-size:16px;color:#00bcd4}"
        ".m{display:flex;gap:20px;padding:6px 12px 8px;background:#111827;flex-wrap:wrap}"
        ".mi .l{font-size:11px;color:#888}.mi .v{font-size:15px;font-weight:bold}"
        "img{width:100%;display:block}"
        "table{width:100%;border-collapse:collapse;font-size:12px}"
        "th{background:#1f2937;padding:5px 8px;text-align:left}"
        "td{padding:4px 8px;border-bottom:1px solid #1a2030}"
        "tr:hover td{background:#1a2030}"
        ".wrap{padding:8px 12px 20px}"
        "</style></head><body>"
        f"<h1>AIBot MACD | {SYMBOL} | SL {SL_PCT*100:.1f}% TP {TP_PCT*100:.1f}%</h1>"
        "<div class='m'>"
        f"<div class='mi'><div class='l'>Сделок</div><div class='v'>{s.get('n_trades',0)}</div></div>"
        f"<div class='mi'><div class='l'>Win Rate</div><div class='v'>{s.get('win_rate',0):.1f}%</div></div>"
        f"<div class='mi'><div class='l'>Profit Factor</div><div class='v' style='color:{pf_c}'>{s.get('profit_factor',0):.2f}</div></div>"
        f"<div class='mi'><div class='l'>Доходность</div><div class='v' style='color:{rt_c}'>{s.get('total_return',0):+.1f}%</div></div>"
        f"<div class='mi'><div class='l'>Max DD</div><div class='v' style='color:#ef5350'>{s.get('max_drawdown',0):.1f}%</div></div>"
        f"<div class='mi'><div class='l'>Sharpe</div><div class='v'>{s.get('sharpe',0):.2f}</div></div>"
        "</div>"
        f"<img src='data:image/png;base64,{img1}'>"
        f"<img src='data:image/png;base64,{img2}'>"
        f"<img src='data:image/png;base64,{img3}'>"
        "<div class='wrap'>"
        f"<p style='padding:8px 0 4px;font-size:13px'>Ордера ({len(_trades)})</p>"
        "<table><tr><th>Вход</th><th>Выход</th><th>Сторона</th>"
        "<th>Вход $</th><th>Выход $</th><th>PnL %</th><th>Причина</th></tr>"
        + rows +
        "</table></div>"
        "</body></html>"
    )


print("Генерация страницы…", flush=True)
_PAGE = _make_page()
print(f"Готово, размер страницы: {len(_PAGE)//1024}KB", flush=True)


@app.route("/")
def index():
    return Response(_PAGE, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
