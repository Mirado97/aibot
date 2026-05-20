"""Flask dashboard — TradingView widget + backtest stats."""
import warnings
warnings.filterwarnings("ignore")

from flask import Flask, Response

from data import load_ohlcv
import macd_bt as mb

app = Flask(__name__)

SYMBOL        = "ETH/USDT:USDT"
SL_PCT        = 0.010
TP_PCT        = 0.020
TRAIL_TRIGGER = 0.010
TRAIL_DIST    = 0.010
TRAIL_TP      = 0.050

print("Загрузка данных…", flush=True)
_df_raw = load_ohlcv(SYMBOL)
_df     = mb.add_indicators(_df_raw)

_trades, _equity = mb.run_backtest(_df, sl_pct=SL_PCT, tp_pct=TP_PCT)
_stats  = mb.calc_stats(_trades, _equity)

_trades_tr, _equity_tr = mb.run_backtest(
    _df, sl_pct=SL_PCT, tp_pct=TRAIL_TP,
    trail_trigger_pct=TRAIL_TRIGGER, trail_dist_pct=TRAIL_DIST,
)
_stats_tr = mb.calc_stats(_trades_tr, _equity_tr)

print(f"Фикс: {_stats['n_trades']} сделок  PF={_stats['profit_factor']:.2f}", flush=True)
print(f"Трейл: {_stats_tr['n_trades']} сделок  PF={_stats_tr['profit_factor']:.2f}", flush=True)


def _make_page() -> str:
    rows = ""
    for t in list(t for t in _trades if t.exit_reason == "end_of_data") + \
             list(reversed([t for t in _trades if t.exit_reason != "end_of_data"])):
        sc  = "#2196F3" if t.side == "long" else "#FF9800"
        pc  = "#4CAF50" if t.is_win else "#ef5350"
        xts = _df.index[t.exit_bar].strftime("%m-%d %H:%M") if t.exit_bar else "—"
        xpx = f"{t.exit_price:.2f}" if t.exit_price else "—"
        rows += (
            f"<tr>"
            f"<td>{_df.index[t.entry_bar].strftime('%m-%d %H:%M')}</td>"
            f"<td>{xts}</td>"
            f"<td style='color:{sc}'>{t.side.upper()}</td>"
            f"<td>{t.entry_price:.2f}</td>"
            f"<td>{xpx}</td>"
            f"<td style='color:{pc}'>{t.pnl_pct*100:+.2f}%</td>"
            f"<td>{t.exit_reason or 'open'}</td>"
            f"</tr>"
        )

    s     = _stats
    pf_c  = "#4CAF50" if s.get("profit_factor", 0) >= 1 else "#ef5350"
    rt_c  = "#4CAF50" if s.get("total_return",  0) >= 0 else "#ef5350"

    st    = _stats_tr
    pf_ct = "#4CAF50" if st.get("profit_factor", 0) >= 1 else "#ef5350"
    rt_ct = "#4CAF50" if st.get("total_return",  0) >= 0 else "#ef5350"

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIBot</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0e1117;color:#e0e0e0;font-family:sans-serif;font-size:13px}}
  h1{{padding:8px 12px;font-size:16px;color:#00bcd4}}
  .lbl{{padding:4px 12px 0;font-size:11px;color:#555}}
  .m{{display:flex;gap:20px;padding:6px 12px 8px;background:#111827;flex-wrap:wrap}}
  .mi .l{{font-size:11px;color:#888}}
  .mi .v{{font-size:15px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{background:#1f2937;padding:5px 8px;text-align:left}}
  td{{padding:4px 8px;border-bottom:1px solid #1a2030}}
  tr:hover td{{background:#1a2030}}
  .wrap{{padding:8px 12px 20px}}
</style>
</head>
<body>

<h1>AIBot MACD | {SYMBOL} | SL {SL_PCT*100:.1f}%</h1>

<div class="lbl">Фикс TP {TP_PCT*100:.1f}%</div>
<div class="m">
  <div class="mi"><div class="l">Сделок</div><div class="v">{s.get('n_trades',0)}</div></div>
  <div class="mi"><div class="l">Win Rate</div><div class="v">{s.get('win_rate',0):.1f}%</div></div>
  <div class="mi"><div class="l">Profit Factor</div><div class="v" style="color:{pf_c}">{s.get('profit_factor',0):.2f}</div></div>
  <div class="mi"><div class="l">Доходность</div><div class="v" style="color:{rt_c}">{s.get('total_return',0):+.1f}%</div></div>
  <div class="mi"><div class="l">Max DD</div><div class="v" style="color:#ef5350">{s.get('max_drawdown',0):.1f}%</div></div>
  <div class="mi"><div class="l">Sharpe</div><div class="v">{s.get('sharpe',0):.2f}</div></div>
</div>

<div class="lbl">Трейлинг (trigger +{TRAIL_TRIGGER*100:.0f}% → безубыток, dist {TRAIL_DIST*100:.0f}%, потолок {TRAIL_TP*100:.0f}%)</div>
<div class="m">
  <div class="mi"><div class="l">Сделок</div><div class="v">{st.get('n_trades',0)}</div></div>
  <div class="mi"><div class="l">Win Rate</div><div class="v">{st.get('win_rate',0):.1f}%</div></div>
  <div class="mi"><div class="l">Profit Factor</div><div class="v" style="color:{pf_ct}">{st.get('profit_factor',0):.2f}</div></div>
  <div class="mi"><div class="l">Доходность</div><div class="v" style="color:{rt_ct}">{st.get('total_return',0):+.1f}%</div></div>
  <div class="mi"><div class="l">Max DD</div><div class="v" style="color:#ef5350">{st.get('max_drawdown',0):.1f}%</div></div>
  <div class="mi"><div class="l">Sharpe</div><div class="v">{st.get('sharpe',0):.2f}</div></div>
</div>

<!-- TradingView Widget -->
<div class="tradingview-widget-container" style="height:520px">
  <div id="tv_chart" style="height:100%"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
    new TradingView.widget({{
      "container_id": "tv_chart",
      "width": "100%",
      "height": 520,
      "symbol": "OKEX:ETHUSDT.P",
      "interval": "240",
      "timezone": "Europe/Kiev",
      "theme": "dark",
      "style": "1",
      "locale": "ru",
      "toolbar_bg": "#1f2937",
      "enable_publishing": false,
      "hide_side_toolbar": false,
      "studies": ["MACD@tv-basicstudies"]
    }});
  </script>
</div>

<div class="wrap">
  <p style="padding:8px 0 4px;font-size:13px">Ордера ({len(_trades)})</p>
  <table>
    <tr><th>Вход</th><th>Выход</th><th>Сторона</th><th>Вход $</th><th>Выход $</th><th>PnL %</th><th>Причина</th></tr>
    {rows}
  </table>
</div>

</body>
</html>"""


print("Генерация страницы…", flush=True)
_PAGE = _make_page()
print(f"Готово, размер страницы: {len(_PAGE)//1024}KB", flush=True)


@app.route("/")
def index():
    return Response(_PAGE, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
