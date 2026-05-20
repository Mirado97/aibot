"""Flask dashboard."""
import warnings, time, json, os
warnings.filterwarnings("ignore")

from flask import Flask, Response
import pandas as pd

from data import load_ohlcv
import macd_bt as mb

app = Flask(__name__)

SYMBOL    = "ETH/USDT:USDT"
SL_PCT    = 0.010
TP_PCT    = 0.020
DAYS_VIEW = 90

# ── Старт: загрузка + бэктест + генерация страницы ────────────────────────────
print("Загрузка данных…", flush=True)
_df_raw = load_ohlcv(SYMBOL)
_df     = mb.add_indicators(_df_raw)
_trades, _equity = mb.run_backtest(_df, sl_pct=SL_PCT, tp_pct=TP_PCT)
_stats  = mb.calc_stats(_trades, _equity)
print(f"Сделок: {_stats['n_trades']}", flush=True)

# Читаем JS библиотеку
_lw_js_path = os.path.join(os.path.dirname(__file__), "static", "lw-charts.js")
with open(_lw_js_path, "r") as f:
    _LW_JS = f.read().replace("</script>", "<\\/script>")


def _make_page() -> str:
    cutoff = _df.index[-1] - pd.Timedelta(days=DAYS_VIEW)

    # 4h свечи для графика (540 баров вместо 8640)
    df4h = _df_raw.resample("4h").agg(
        {"open":"first","high":"max","low":"min","close":"last"}
    ).dropna()
    dv4h = df4h[df4h.index >= cutoff]

    candles = [{"time": int(ts.timestamp()),
                "open": round(float(r.open),2), "high": round(float(r.high),2),
                "low":  round(float(r.low),2),  "close": round(float(r.close),2)}
               for ts, r in dv4h.iterrows()]

    # MACD
    c4h   = df4h["close"]
    macd_ = c4h.ewm(span=12,adjust=False).mean() - c4h.ewm(span=26,adjust=False).mean()
    sig_  = macd_.ewm(span=9,adjust=False).mean()
    hist_ = macd_ - sig_
    macd_data = [{"time": int(ts.timestamp()), "value": round(float(v),4)}
                 for ts, v in macd_[dv4h.index].items()]
    sig_data  = [{"time": int(ts.timestamp()), "value": round(float(v),4)}
                 for ts, v in sig_[dv4h.index].items()]
    hist_data = [{"time": int(ts.timestamp()), "value": round(float(v),4),
                  "color": "#26a69a" if v>=0 else "#ef5350"}
                 for ts, v in hist_[dv4h.index].items()]

    # Equity (по 4h бару)
    eq = pd.Series(_equity, index=_df.index).resample("4h").last().dropna()
    eq_view = eq[eq.index >= cutoff]
    eq_data = [{"time": int(ts.timestamp()), "value": round(float(v),2)}
               for ts, v in eq_view.items()]

    # Маркеры → округляем до ближайшего 4h бара
    def to4h(bar_idx):
        t = _df.index[bar_idx]
        return int(t.floor("4h").timestamp())

    markers = []
    for t in _trades:
        if _df.index[t.entry_bar] < cutoff:
            continue
        markers.append({"time": to4h(t.entry_bar),
            "position": "belowBar" if t.side=="long" else "aboveBar",
            "color": "#2196F3" if t.side=="long" else "#FF9800",
            "shape": "arrowUp" if t.side=="long" else "arrowDown",
            "text": "L" if t.side=="long" else "S"})
        if t.exit_bar and _df.index[t.exit_bar] >= cutoff:
            markers.append({"time": to4h(t.exit_bar),
                "position": "aboveBar" if t.is_win else "belowBar",
                "color": "#4CAF50" if t.is_win else "#ef5350",
                "shape": "circle", "text": "W" if t.is_win else "X"})
    markers.sort(key=lambda x: x["time"])

    # Таблица
    rows = ""
    for t in list(t for t in _trades if t.exit_reason=="end_of_data") + \
             list(reversed([t for t in _trades if t.exit_reason!="end_of_data"])):
        sc = "#2196F3" if t.side=="long" else "#FF9800"
        pc = "#4CAF50" if t.is_win else "#ef5350"
        xts = _df.index[t.exit_bar].strftime("%m-%d %H:%M") if t.exit_bar else "—"
        xpx = f"{t.exit_price:.2f}" if t.exit_price else "—"
        rows += (f"<tr><td>{_df.index[t.entry_bar].strftime('%m-%d %H:%M')}</td>"
                 f"<td>{xts}</td><td style='color:{sc}'>{t.side.upper()}</td>"
                 f"<td>{t.entry_price:.2f}</td><td>{xpx}</td>"
                 f"<td style='color:{pc}'>{t.pnl_pct*100:+.2f}%</td>"
                 f"<td>{t.exit_reason or 'open'}</td></tr>")

    s    = _stats
    pf_c = "#4CAF50" if s.get("profit_factor",0)>=1 else "#ef5350"
    rt_c = "#4CAF50" if s.get("total_return",0)>=0  else "#ef5350"

    cj = json.dumps(candles)
    mj = json.dumps(markers)
    hj = json.dumps(hist_data)
    aj = json.dumps(macd_data)
    gj = json.dumps(sig_data)
    ej = json.dumps(eq_data)

    html = (
        "<!DOCTYPE html><html lang='ru'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>AIBot</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{background:#0e1117;color:#e0e0e0;font-family:sans-serif;font-size:13px}"
        "h1{padding:8px 12px;font-size:16px;color:#00bcd4}"
        ".m{display:flex;gap:20px;padding:6px 12px 8px;background:#111827;flex-wrap:wrap}"
        ".mi .l{font-size:11px;color:#888}.mi .v{font-size:15px;font-weight:bold}"
        ".lbl{padding:2px 12px;font-size:11px;color:#666}"
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
        "<div class='lbl'>Цена ETH 4h — 90 дней</div><div id='c1' style='width:100%;height:360px'></div>"
        "<div class='lbl'>MACD 4h</div><div id='c2' style='width:100%;height:140px'></div>"
        "<div class='lbl'>Equity</div><div id='c3' style='width:100%;height:120px'></div>"
        "<div class='wrap'>"
        f"<p style='padding:8px 0 4px;font-size:13px'>Ордера ({len(_trades)})</p>"
        "<table><tr><th>Вход</th><th>Выход</th><th>Сторона</th>"
        "<th>Вход $</th><th>Выход $</th><th>PnL %</th><th>Причина</th></tr>"
        + rows +
        "</table></div>"
        "<script>" + _LW_JS + "</script>"
        "<script>console.log('JS start',typeof LightweightCharts);"
        "const OPT={"
        "autoSize:true,"
        "layout:{background:{color:'#0e1117'},textColor:'#9ca3af'},"
        "grid:{vertLines:{color:'#1f2937'},horzLines:{color:'#1f2937'}},"
        "timeScale:{timeVisible:true,secondsVisible:false},crosshair:{mode:1}};"
        f"const ch1=LightweightCharts.createChart(document.getElementById('c1'),{{...OPT,height:360}});"
        "const cs=ch1.addCandlestickSeries({upColor:'#26a69a',downColor:'#ef5350',"
        "borderUpColor:'#26a69a',borderDownColor:'#ef5350',wickUpColor:'#26a69a',wickDownColor:'#ef5350'});"
        f"cs.setData({cj});cs.setMarkers({mj});"
        f"const ch2=LightweightCharts.createChart(document.getElementById('c2'),{{...OPT,height:140}});"
        f"const hb=ch2.addHistogramSeries({{priceLineVisible:false,lastValueVisible:false}});"
        f"const ml=ch2.addLineSeries({{color:'#2196F3',lineWidth:1,priceLineVisible:false,lastValueVisible:false}});"
        f"const sl=ch2.addLineSeries({{color:'#FF9800',lineWidth:1,priceLineVisible:false,lastValueVisible:false}});"
        f"hb.setData({hj});ml.setData({aj});sl.setData({gj});"
        f"const ch3=LightweightCharts.createChart(document.getElementById('c3'),{{...OPT,height:120}});"
        f"const es=ch3.addAreaSeries({{lineColor:'#7E57C2',topColor:'rgba(126,87,194,0.3)',bottomColor:'rgba(126,87,194,0)',lineWidth:2}});"
        f"es.setData({ej});"
        "[ch1,ch2,ch3].forEach((c,i)=>{c.timeScale().subscribeVisibleLogicalRangeChange(r=>"
        "{if(!r)return;[ch1,ch2,ch3].forEach((cc,j)=>{if(i!==j)cc.timeScale().setVisibleLogicalRange(r);});});});"
        "window.addEventListener('resize',()=>{[ch1,ch2,ch3].forEach(c=>c.applyOptions({}));});"
        "</script>"
        "</body></html>"
    )
    return html


print("Генерация страницы…", flush=True)
_PAGE = _make_page()
print(f"Готово, размер страницы: {len(_PAGE)//1024}KB", flush=True)


@app.route("/")
def index():
    return Response(_PAGE, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
