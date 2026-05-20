"""Flask dashboard — MACD backtest viewer."""
import warnings, time
warnings.filterwarnings("ignore")

from flask import Flask, request, Response
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import pandas as pd

from data import load_ohlcv
import macd_bt as mb

app = Flask(__name__)

SYMBOL   = "ETH/USDT:USDT"
SL_PCT   = 0.010
TP_PCT   = 0.020
DAYS_VIEW = 90   # свечей меньше → страница меньше

# ── Предвычисление при старте ──────────────────────────────────────────────────
print("Загрузка данных и бэктест…", flush=True)
_t0 = time.time()
_df_raw = load_ohlcv(SYMBOL)
_df     = mb.add_indicators(_df_raw)
_trades, _equity = mb.run_backtest(_df, sl_pct=SL_PCT, tp_pct=TP_PCT)
_stats  = mb.calc_stats(_trades, _equity)
print(f"Готово за {time.time()-_t0:.1f}с, сделок: {_stats['n_trades']}", flush=True)


def build_page() -> str:
    cutoff   = _df.index[-1] - pd.Timedelta(days=DAYS_VIEW)
    df_view  = _df[_df.index >= cutoff]

    # MACD 4h для нижней панели
    df4h = _df_raw.resample("4h").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    ).dropna()
    c4h   = df4h["close"]
    macd_ = c4h.ewm(span=12,adjust=False).mean() - c4h.ewm(span=26,adjust=False).mean()
    sig_  = macd_.ewm(span=9,adjust=False).mean()
    hist_ = macd_ - sig_
    dv4h  = df4h[df4h.index >= cutoff]
    hv    = hist_[dv4h.index]
    mv    = macd_[dv4h.index]
    sv    = sig_[dv4h.index]

    def ts(bar): return _df.index[bar]

    tin  = [t for t in _trades if ts(t.entry_bar) >= cutoff]
    lx   = [ts(t.entry_bar) for t in tin if t.side=="long"]
    ly   = [t.entry_price   for t in tin if t.side=="long"]
    sx   = [ts(t.entry_bar) for t in tin if t.side=="short"]
    sy   = [t.entry_price   for t in tin if t.side=="short"]
    wx   = [ts(t.exit_bar)  for t in tin if t.exit_bar and t.is_win]
    wy   = [t.exit_price    for t in tin if t.exit_bar and t.is_win]
    lox  = [ts(t.exit_bar)  for t in tin if t.exit_bar and not t.is_win]
    loy  = [t.exit_price    for t in tin if t.exit_bar and not t.is_win]

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.55,0.25,0.20], vertical_spacing=0.02,
                        subplot_titles=("Цена 15m","MACD 4h","Equity"))

    fig.add_trace(go.Candlestick(
        x=df_view.index, open=df_view["open"], high=df_view["high"],
        low=df_view["low"], close=df_view["close"],
        name="Цена", showlegend=False,
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        increasing_fillcolor="#26a69a",  decreasing_fillcolor="#ef5350",
    ), row=1, col=1)

    for x,y,color,sym,name in [
        (lx,ly,"#2196F3","triangle-up","Long"),
        (sx,sy,"#FF9800","triangle-down","Short"),
        (wx,wy,"#4CAF50","x","WIN"),
        (lox,loy,"#ef5350","x","LOSS"),
    ]:
        if x:
            fig.add_trace(go.Scatter(x=x,y=y,mode="markers",name=name,
                marker=dict(symbol=sym,size=12,color=color,
                            line=dict(color="#fff",width=1))), row=1,col=1)

    hcolors = ["#26a69a" if v>=0 else "#ef5350" for v in hv.values]
    fig.add_trace(go.Bar(x=dv4h.index,y=hv.values,marker_color=hcolors,
                         name="Hist",showlegend=False), row=2,col=1)
    fig.add_trace(go.Scatter(x=dv4h.index,y=mv.values,
                             line=dict(color="#2196F3",width=1.5),name="MACD"), row=2,col=1)
    fig.add_trace(go.Scatter(x=dv4h.index,y=sv.values,
                             line=dict(color="#FF9800",width=1.5),name="Signal"), row=2,col=1)
    fig.add_hline(y=0, line_color="#555", line_width=1, row=2, col=1)

    eq = pd.Series(_equity, index=_df.index)
    eqv = eq[eq.index >= cutoff]
    fig.add_trace(go.Scatter(x=eqv.index,y=eqv.values,fill="tozeroy",
        line=dict(color="#7E57C2",width=2),
        fillcolor="rgba(126,87,194,0.15)",name="Equity",showlegend=False), row=3,col=1)

    fig.update_layout(
        height=820, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#e0e0e0",size=12), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h",y=1.02,x=0),
        margin=dict(l=10,r=10,t=50,b=10),
    )
    for i in range(1,4):
        fig.update_xaxes(gridcolor="#1f2937",zeroline=False,row=i,col=1)
        fig.update_yaxes(gridcolor="#1f2937",zeroline=False,row=i,col=1)

    chart_html = pio.to_html(fig, full_html=False, include_plotlyjs=True)

    s = _stats
    pf_c = "color:#4CAF50" if s.get("profit_factor",0)>=1 else "color:#ef5350"
    rt_c = "color:#4CAF50" if s.get("total_return",0)>=0  else "color:#ef5350"

    closed = [t for t in reversed(_trades) if t.exit_reason != "end_of_data"]
    open_t = [t for t in _trades if t.exit_reason == "end_of_data"]

    rows = ""
    for t in list(open_t) + closed:
        sc = "#2196F3" if t.side=="long" else "#FF9800"
        side_s = f'<span style="color:{sc}">{t.side.upper()}</span>'
        pc = "#4CAF50" if t.is_win else "#ef5350"
        xts = _df.index[t.exit_bar].strftime("%Y-%m-%d %H:%M") if t.exit_bar else "—"
        xpx = f"{t.exit_price:.4f}" if t.exit_price else "—"
        rows += (f"<tr><td>{_df.index[t.entry_bar].strftime('%Y-%m-%d %H:%M')}</td>"
                 f"<td>{xts}</td><td>{side_s}</td>"
                 f"<td>{t.entry_price:.4f}</td><td>{xpx}</td>"
                 f"<td style='color:{pc}'>{t.pnl_pct*100:+.2f}%</td>"
                 f"<td>{t.exit_reason or 'open'}</td></tr>\n")

    page = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIBot Dashboard</title>
<style>
body{{margin:0;background:#0e1117;color:#e0e0e0;font-family:sans-serif;font-size:13px}}
h1{{margin:10px 16px 4px;font-size:18px;color:#00bcd4}}
.m{{display:flex;gap:20px;padding:8px 16px;background:#1a1f2e;flex-wrap:wrap}}
.mi .l{{font-size:11px;color:#888}}.mi .v{{font-size:16px;font-weight:bold}}
.s{{padding:0 16px 16px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1f2937;padding:6px 8px;text-align:left}}
td{{padding:5px 8px;border-bottom:1px solid #1f2937}}
</style></head><body>
<h1>📈 AIBot — MACD | ETH/USDT:USDT | SL {SL_PCT*100:.1f}% TP {TP_PCT*100:.1f}%</h1>
<div class="m">
<div class="mi"><div class="l">Сделок</div><div class="v">{s.get('n_trades',0)}</div></div>
<div class="mi"><div class="l">Win Rate</div><div class="v">{s.get('win_rate',0):.1f}%</div></div>
<div class="mi"><div class="l">Profit Factor</div><div class="v" style="{pf_c}">{s.get('profit_factor',0):.2f}</div></div>
<div class="mi"><div class="l">Доходность</div><div class="v" style="{rt_c}">{s.get('total_return',0):+.1f}%</div></div>
<div class="mi"><div class="l">Max Drawdown</div><div class="v" style="color:#ef5350">{s.get('max_drawdown',0):.1f}%</div></div>
<div class="mi"><div class="l">Sharpe</div><div class="v">{s.get('sharpe',0):.2f}</div></div>
</div>
<div class="s">CHART_PLACEHOLDER</div>
<div class="s"><h2 style="font-size:15px">Ордера ({len(_trades)})</h2>
<table><tr><th>Вход</th><th>Выход</th><th>Сторона</th><th>Вход $</th><th>Выход $</th><th>PnL %</th><th>Причина</th></tr>
{rows}</table></div>
</body></html>"""
    return page.replace("CHART_PLACEHOLDER", chart_html)


@app.route("/")
def index():
    return Response(build_page(), mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
