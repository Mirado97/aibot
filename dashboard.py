"""Интерактивный дашборд: MACD Crossover backtest."""
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from data import load_ohlcv
import macd_bt as mb

st.set_page_config(page_title="AIBot Dashboard", layout="wide", page_icon="📈")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Параметры")
    symbol = st.selectbox("Символ", [
        "ETH/USDT:USDT", "SOL/USDT:USDT", "DOGE/USDT:USDT",
        "BTC/USDT:USDT", "XRP/USDT:USDT",
    ])
    sl_pct  = st.slider("Stop Loss %",   0.5, 5.0, 1.0, 0.5) / 100
    tp_pct  = st.slider("Take Profit %", 1.0, 10.0, 2.0, 0.5) / 100
    days_view = st.slider("Показать дней на графике", 30, 730, 120)

# ── Load & run ────────────────────────────────────────────────────────────────
with st.spinner(f"Загрузка {symbol} …"):
    df_raw = load_ohlcv(symbol)
    df     = mb.add_indicators(df_raw)
    trades, equity = mb.run_backtest(df, sl_pct=sl_pct, tp_pct=tp_pct)
    stats  = mb.calc_stats(trades, equity)

st.title(f"📈 AIBot — MACD Crossover | {symbol}")

# ── Метрики ───────────────────────────────────────────────────────────────────
if stats:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Сделок",        stats["n_trades"])
    c2.metric("Win Rate",      f"{stats['win_rate']:.1f}%")
    c3.metric("Profit Factor", f"{stats['profit_factor']:.2f}")
    c4.metric("Доходность",    f"{stats['total_return']:+.1f}%")
    c5.metric("Max Drawdown",  f"{stats['max_drawdown']:.1f}%")
    c6.metric("Sharpe",        f"{stats['sharpe']:.2f}")
else:
    st.warning("Нет сделок за период.")

# ── Подготовка данных для графика ─────────────────────────────────────────────
cutoff   = df.index[-1] - pd.Timedelta(days=days_view)
df_view  = df[df.index >= cutoff]

# 4h MACD для нижней панели
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

# Маркеры: фильтруем по окну
def ts(bar):
    return df.index[bar]

trades_in_view = [t for t in trades if ts(t.entry_bar) >= cutoff]

long_entry_ts  = [ts(t.entry_bar) for t in trades_in_view if t.side == "long"]
long_entry_px  = [t.entry_price   for t in trades_in_view if t.side == "long"]
short_entry_ts = [ts(t.entry_bar) for t in trades_in_view if t.side == "short"]
short_entry_px = [t.entry_price   for t in trades_in_view if t.side == "short"]

win_exit_ts  = [ts(t.exit_bar) for t in trades_in_view if t.exit_bar and t.is_win]
win_exit_px  = [t.exit_price   for t in trades_in_view if t.exit_bar and t.is_win]
loss_exit_ts = [ts(t.exit_bar) for t in trades_in_view if t.exit_bar and not t.is_win]
loss_exit_px = [t.exit_price   for t in trades_in_view if t.exit_bar and not t.is_win]

# ── Построение графика ────────────────────────────────────────────────────────
fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    row_heights=[0.55, 0.25, 0.20],
    vertical_spacing=0.02,
    subplot_titles=("Цена (15m)", "MACD 4h", "Equity"),
)

# Свечи
fig.add_trace(go.Candlestick(
    x=df_view.index,
    open=df_view["open"], high=df_view["high"],
    low=df_view["low"],   close=df_view["close"],
    name="Цена", showlegend=False,
    increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    increasing_fillcolor="#26a69a",  decreasing_fillcolor="#ef5350",
), row=1, col=1)

# Лонг входы (синий треугольник вверх)
if long_entry_ts:
    fig.add_trace(go.Scatter(
        x=long_entry_ts, y=long_entry_px, mode="markers",
        marker=dict(symbol="triangle-up", size=13, color="#2196F3",
                    line=dict(color="#ffffff", width=1)),
        name="Long вход",
    ), row=1, col=1)

# Шорт входы (оранжевый треугольник вниз)
if short_entry_ts:
    fig.add_trace(go.Scatter(
        x=short_entry_ts, y=short_entry_px, mode="markers",
        marker=dict(symbol="triangle-down", size=13, color="#FF9800",
                    line=dict(color="#ffffff", width=1)),
        name="Short вход",
    ), row=1, col=1)

# Выходы в плюс (зелёный крест)
if win_exit_ts:
    fig.add_trace(go.Scatter(
        x=win_exit_ts, y=win_exit_px, mode="markers",
        marker=dict(symbol="x", size=11, color="#4CAF50",
                    line=dict(width=2)),
        name="Выход WIN",
    ), row=1, col=1)

# Выходы в минус (красный крест)
if loss_exit_ts:
    fig.add_trace(go.Scatter(
        x=loss_exit_ts, y=loss_exit_px, mode="markers",
        marker=dict(symbol="x", size=11, color="#ef5350",
                    line=dict(width=2)),
        name="Выход LOSS",
    ), row=1, col=1)

# MACD гистограмма
hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in hist_view.values]
fig.add_trace(go.Bar(
    x=df4h_view.index, y=hist_view.values,
    marker_color=hist_colors, name="Histogram", showlegend=False,
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df4h_view.index, y=macd_view.values,
    line=dict(color="#2196F3", width=1.5), name="MACD",
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df4h_view.index, y=sig_view.values,
    line=dict(color="#FF9800", width=1.5), name="Signal",
), row=2, col=1)
fig.add_hline(y=0, line_color="#555555", line_width=1, row=2, col=1)

# Equity curve
eq_series  = pd.Series(equity, index=df.index)
eq_view    = eq_series[eq_series.index >= cutoff]
fig.add_trace(go.Scatter(
    x=eq_view.index, y=eq_view.values,
    fill="tozeroy",
    line=dict(color="#7E57C2", width=2),
    fillcolor="rgba(126,87,194,0.15)",
    name="Equity", showlegend=False,
), row=3, col=1)

# Оформление
fig.update_layout(
    height=820,
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font=dict(color="#e0e0e0", size=12),
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", y=1.02, x=0),
    margin=dict(l=10, r=10, t=50, b=10),
)
for i in range(1, 4):
    fig.update_xaxes(gridcolor="#1f2937", zeroline=False, row=i, col=1)
    fig.update_yaxes(gridcolor="#1f2937", zeroline=False, row=i, col=1)

st.plotly_chart(fig, use_container_width=True)

# ── Таблица ордеров ───────────────────────────────────────────────────────────
st.divider()

# Текущая открытая позиция (если есть)
open_trades = [t for t in trades if t.exit_reason == "end_of_data"]
if open_trades:
    st.subheader("📌 Текущие позиции (открытые)")
    open_rows = []
    for t in open_trades:
        open_rows.append({
            "Открыта":    ts(t.entry_bar).strftime("%Y-%m-%d %H:%M"),
            "Сторона":    t.side.upper(),
            "Вход $":     f"{t.entry_price:.4f}",
            "SL $":       f"{t.sl_price:.4f}",
            "TP $":       f"{t.tp_price:.4f}",
            "PnL %":      f"{t.pnl_pct * 100:+.2f}%",
            "Статус":     "🟡 OPEN",
        })
    st.dataframe(pd.DataFrame(open_rows), use_container_width=True)

# Исполненные ордера
closed = [t for t in reversed(trades) if t.exit_reason != "end_of_data"]
st.subheader(f"📋 Исполненные ордера ({len(closed)} шт.)")
if closed:
    rows = []
    for t in closed:
        rows.append({
            "Вход":        ts(t.entry_bar).strftime("%Y-%m-%d %H:%M"),
            "Выход":       ts(t.exit_bar).strftime("%Y-%m-%d %H:%M"),
            "Сторона":     t.side.upper(),
            "Вход $":      f"{t.entry_price:.4f}",
            "Выход $":     f"{t.exit_price:.4f}",
            "PnL %":       f"{t.pnl_pct * 100:+.2f}%",
            "Держали":     f"{t.bars_held * 15} мин",
            "Причина":     t.exit_reason,
            "Итог":        "✅" if t.is_win else "❌",
        })
    df_table = pd.DataFrame(rows)
    st.dataframe(df_table, use_container_width=True, height=450)
else:
    st.info("Нет исполненных ордеров в выбранном периоде.")
