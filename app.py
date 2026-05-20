"""Flask dashboard — MACD backtest viewer."""
import warnings, time, json
warnings.filterwarnings("ignore")

from flask import Flask, request, Response, send_from_directory
import pandas as pd
import os

from data import load_ohlcv
import macd_bt as mb

app = Flask(__name__)

@app.route("/static/<path:f>")
def static_files(f):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), f)

SYMBOL    = "ETH/USDT:USDT"
SL_PCT    = 0.010
TP_PCT    = 0.020
DAYS_VIEW = 90

print("Загрузка данных и бэктест…", flush=True)
_t0 = time.time()
_df_raw = load_ohlcv(SYMBOL)
_df     = mb.add_indicators(_df_raw)
_trades, _equity = mb.run_backtest(_df, sl_pct=SL_PCT, tp_pct=TP_PCT)
_stats  = mb.calc_stats(_trades, _equity)
print(f"Готово за {time.time()-_t0:.1f}с, сделок: {_stats['n_trades']}", flush=True)


def build_page() -> str:
    cutoff  = _df.index[-1] - pd.Timedelta(days=DAYS_VIEW)
    df_view = _df[_df.index >= cutoff]

    # Свечи для LightweightCharts: {time: unix_sec, open, high, low, close}
    candles = [
        {"time": int(ts.timestamp()), "open": r.open, "high": r.high,
         "low": r.low, "close": r.close}
        for ts, r in df_view.iterrows()
    ]

    # MACD 4h
    df4h = _df_raw.resample("4h").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    ).dropna()
    c4h   = df4h["close"]
    macd_ = c4h.ewm(span=12,adjust=False).mean() - c4h.ewm(span=26,adjust=False).mean()
    sig_  = macd_.ewm(span=9,adjust=False).mean()
    hist_ = macd_ - sig_
    dv4h  = df4h[df4h.index >= cutoff]

    macd_line = [{"time": int(ts.timestamp()), "value": round(float(v),4)}
                 for ts, v in macd_[dv4h.index].items()]
    sig_line  = [{"time": int(ts.timestamp()), "value": round(float(v),4)}
                 for ts, v in sig_[dv4h.index].items()]
    hist_bars = [{"time": int(ts.timestamp()), "value": round(float(v),4),
                  "color": "#26a69a" if v >= 0 else "#ef5350"}
                 for ts, v in hist_[dv4h.index].items()]

    # Equity
    eq_view = pd.Series(_equity, index=_df.index)[_df.index >= cutoff]
    equity_line = [{"time": int(ts.timestamp()), "value": round(float(v),2)}
                   for ts, v in eq_view.items()]

    # Маркеры сделок
    def ts(bar): return _df.index[bar]
    tin = [t for t in _trades if ts(t.entry_bar) >= cutoff]

    markers = []
    for t in tin:
        entry_ts = int(ts(t.entry_bar).timestamp())
        markers.append({
            "time": entry_ts,
            "position": "belowBar" if t.side == "long" else "aboveBar",
            "color": "#2196F3" if t.side == "long" else "#FF9800",
            "shape": "arrowUp" if t.side == "long" else "arrowDown",
            "text": "L" if t.side == "long" else "S",
        })
        if t.exit_bar:
            exit_ts = int(ts(t.exit_bar).timestamp())
            markers.append({
                "time": exit_ts,
                "position": "aboveBar" if t.is_win else "belowBar",
                "color": "#4CAF50" if t.is_win else "#ef5350",
                "shape": "circle",
                "text": "W" if t.is_win else "L",
            })
    markers.sort(key=lambda x: x["time"])

    # Таблица ордеров
    closed = [t for t in reversed(_trades) if t.exit_reason != "end_of_data"]
    open_t = [t for t in _trades if t.exit_reason == "end_of_data"]
    rows = ""
    for t in list(open_t) + closed:
        sc = "#2196F3" if t.side == "long" else "#FF9800"
        pc = "#4CAF50" if t.is_win else "#ef5350"
        xts = _df.index[t.exit_bar].strftime("%Y-%m-%d %H:%M") if t.exit_bar else "—"
        xpx = f"{t.exit_price:.4f}" if t.exit_price else "—"
        rows += (f"<tr><td>{_df.index[t.entry_bar].strftime('%Y-%m-%d %H:%M')}</td>"
                 f"<td>{xts}</td>"
                 f"<td style='color:{sc}'>{t.side.upper()}</td>"
                 f"<td>{t.entry_price:.4f}</td><td>{xpx}</td>"
                 f"<td style='color:{pc}'>{t.pnl_pct*100:+.2f}%</td>"
                 f"<td>{t.exit_reason or 'open'}</td></tr>\n")

    s = _stats
    pf_c = "#4CAF50" if s.get("profit_factor",0)>=1 else "#ef5350"
    rt_c = "#4CAF50" if s.get("total_return",0)>=0  else "#ef5350"

    candles_j = json.dumps(candles)
    markers_j = json.dumps(markers)
    macd_j    = json.dumps(macd_line)
    sig_j     = json.dumps(sig_line)
    hist_j    = json.dumps(hist_bars)
    equity_j  = json.dumps(equity_line)

    return f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIBot Dashboard</title>
<script src="/static/lw-charts.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0e1117;color:#e0e0e0;font-family:sans-serif;font-size:13px}}
h1{{padding:10px 16px 4px;font-size:17px;color:#00bcd4}}
.m{{display:flex;gap:24px;padding:8px 16px 10px;background:#111827;flex-wrap:wrap}}
.mi .l{{font-size:11px;color:#888}}.mi .v{{font-size:15px;font-weight:bold}}
#c1,#c2,#c3{{width:100%;}}
.ct{{padding:0 8px;color:#888;font-size:11px;padding-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#1f2937;padding:5px 8px;text-align:left;position:sticky;top:0}}
td{{padding:4px 8px;border-bottom:1px solid #1a2030}}
tr:hover td{{background:#1a2030}}
.wrap{{padding:8px 0 0}}
</style>
</head><body>
<h1>📈 AIBot MACD | {SYMBOL} | SL {SL_PCT*100:.1f}% TP {TP_PCT*100:.1f}%</h1>
<div class="m">
  <div class="mi"><div class="l">Сделок</div><div class="v">{s.get('n_trades',0)}</div></div>
  <div class="mi"><div class="l">Win Rate</div><div class="v">{s.get('win_rate',0):.1f}%</div></div>
  <div class="mi"><div class="l">Profit Factor</div><div class="v" style="color:{pf_c}">{s.get('profit_factor',0):.2f}</div></div>
  <div class="mi"><div class="l">Доходность</div><div class="v" style="color:{rt_c}">{s.get('total_return',0):+.1f}%</div></div>
  <div class="mi"><div class="l">Max Drawdown</div><div class="v" style="color:#ef5350">{s.get('max_drawdown',0):.1f}%</div></div>
  <div class="mi"><div class="l">Sharpe</div><div class="v">{s.get('sharpe',0):.2f}</div></div>
</div>
<div class="ct">Цена 15m — последние {DAYS_VIEW} дней</div>
<div id="c1"></div>
<div class="ct">MACD 4h</div>
<div id="c2"></div>
<div class="ct">Equity</div>
<div id="c3"></div>
<div class="wrap" style="padding:0 16px 16px">
  <h2 style="font-size:14px;padding:10px 0 6px">Ордера ({len(_trades)})</h2>
  <table><tr><th>Вход</th><th>Выход</th><th>Сторона</th><th>Вход $</th><th>Выход $</th><th>PnL %</th><th>Причина</th></tr>
  {rows}</table>
</div>
<script>
const W = document.body.clientWidth - 16;
const OPT = {{
  layout:{{background:{{color:'#0e1117'}},textColor:'#9ca3af'}},
  grid:{{vertLines:{{color:'#1f2937'}},horzLines:{{color:'#1f2937'}}}},
  timeScale:{{timeVisible:true,secondsVisible:false}},
  crosshair:{{mode:1}},
  width: W,
}};

// Chart 1 — свечи
const ch1 = LightweightCharts.createChart(document.getElementById('c1'), {{...OPT, height:380}});
const cs  = ch1.addCandlestickSeries({{
  upColor:'#26a69a',downColor:'#ef5350',
  borderUpColor:'#26a69a',borderDownColor:'#ef5350',
  wickUpColor:'#26a69a',wickDownColor:'#ef5350',
}});
cs.setData({candles_j});
cs.setMarkers({markers_j});

// Chart 2 — MACD
const ch2   = LightweightCharts.createChart(document.getElementById('c2'), {{...OPT, height:160}});
const hist  = ch2.addHistogramSeries({{priceLineVisible:false,lastValueVisible:false}});
const macdL = ch2.addLineSeries({{color:'#2196F3',lineWidth:1,priceLineVisible:false,lastValueVisible:false}});
const sigL  = ch2.addLineSeries({{color:'#FF9800',lineWidth:1,priceLineVisible:false,lastValueVisible:false}});
hist.setData({hist_j});
macdL.setData({macd_j});
sigL.setData({sig_j});

// Chart 3 — equity
const ch3 = LightweightCharts.createChart(document.getElementById('c3'), {{...OPT, height:130}});
const eqS = ch3.addAreaSeries({{lineColor:'#7E57C2',topColor:'rgba(126,87,194,0.3)',bottomColor:'rgba(126,87,194,0)',lineWidth:2}});
eqS.setData({equity_j});

// Синхронизация временных шкал
[ch1,ch2,ch3].forEach((c,i)=>{{
  c.timeScale().subscribeVisibleLogicalRangeChange(r=>{{
    if(!r) return;
    [ch1,ch2,ch3].forEach((cc,j)=>{{ if(i!==j) cc.timeScale().setVisibleLogicalRange(r); }});
  }});
}});
window.addEventListener('resize',()=>{{
  const w = document.body.clientWidth-16;
  [ch1,ch2,ch3].forEach(c=>c.applyOptions({{width:w}}));
}});
</script>
</body></html>"""


@app.route("/")
def index():
    return Response(build_page(), mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
