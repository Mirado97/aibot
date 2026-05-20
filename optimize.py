"""Fine-tune RSI MeanRev 15m + EMA480 macro filter."""
import numpy as np
import pandas as pd
from data import load_ohlcv
from backtest import add_indicators, calc_stats, Trade
from config import (
    CAPITAL, COMMISSION, SLIPPAGE, LEVERAGE, POSITION_PCT,
    EMA_1H, EMA_1H_SLOPE, TREND_EXIT_BARS, MAX_HOLD_BARS,
)
from typing import Optional

MACRO_SPAN = 480   # EMA480 = 5 дней на 15m


def add_macro_ema(df, span):
    df = df.copy()
    df["ema_macro"] = df["close"].ewm(span=span, adjust=False).mean()
    return df


def run_bt(df, rsi_low, rsi_high, sl_pct, tp_pct):
    opens    = df["open"].values
    highs    = df["high"].values
    lows     = df["low"].values
    closes   = df["close"].values
    rsi      = df["rsi"].values
    ema1h    = df["ema1h"].values
    bb_upper = df["bb_upper"].values
    bb_lower = df["bb_lower"].values
    ema_mac  = df["ema_macro"].values

    n = len(df)
    equity = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital = CAPITAL
    trades = []
    pos: Optional[Trade] = None
    pending_side = None
    start = EMA_1H_SLOPE + 2

    for i in range(start, n):
        if pending_side and pos is None:
            entry = opens[i]
            sl = entry * (1 - sl_pct) if pending_side == "long" else entry * (1 + sl_pct)
            tp = entry * (1 + tp_pct) if pending_side == "long" else entry * (1 - tp_pct)
            pos = Trade(side=pending_side, entry_bar=i, entry_price=entry, sl_price=sl, tp_price=tp)
            pending_side = None

        if pos is not None:
            hi, lo, cl = highs[i], lows[i], closes[i]

            def _close(price, reason):
                nonlocal capital, pos
                pos.exit_bar = i; pos.exit_price = price; pos.exit_reason = reason
                capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
                trades.append(pos); pos = None

            bars_in = i - pos.entry_bar
            if pos.side == "long":
                if   opens[i] <= pos.sl_price:                                              _close(opens[i],     "sl_gap")
                elif lo       <= pos.sl_price:                                              _close(pos.sl_price, "sl")
                elif hi       >= pos.tp_price:                                              _close(pos.tp_price, "tp")
                elif bars_in  >= TREND_EXIT_BARS and ema1h[i] < ema1h[i - EMA_1H_SLOPE]:   _close(cl,           "trend_exit")
                elif bars_in  >= MAX_HOLD_BARS:                                             _close(cl,           "timeout")
            else:
                if   opens[i] >= pos.sl_price:                                              _close(opens[i],     "sl_gap")
                elif hi       >= pos.sl_price:                                              _close(pos.sl_price, "sl")
                elif lo       <= pos.tp_price:                                              _close(pos.tp_price, "tp")
                elif bars_in  >= TREND_EXIT_BARS and ema1h[i] > ema1h[i - EMA_1H_SLOPE]:   _close(cl,           "trend_exit")
                elif bars_in  >= MAX_HOLD_BARS:                                             _close(cl,           "timeout")

        equity[i] = capital

        if pos is None and pending_side is None:
            trend_up   = ema1h[i] > ema1h[i - EMA_1H_SLOPE]
            trend_down = ema1h[i] < ema1h[i - EMA_1H_SLOPE]
            bull_regime = closes[i] > ema_mac[i]
            bear_regime = closes[i] < ema_mac[i]

            if rsi[i] < rsi_low  and closes[i] <= bb_lower[i] * 1.005 and trend_up   and bull_regime:
                pending_side = "long"
            elif rsi[i] > rsi_high and closes[i] >= bb_upper[i] * 0.995 and trend_down and bear_regime:
                pending_side = "short"

    if pos is not None:
        pos.exit_bar = n-1; pos.exit_price = closes[n-1]; pos.exit_reason = "end_of_data"
        capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
        trades.append(pos); equity[n-1] = capital

    equity = pd.Series(equity).ffill().values
    return trades, equity


def test(df, rsi_low, rsi_high, sl_pct, tp_pct):
    trades, equity = run_bt(df, rsi_low, rsi_high, sl_pct, tp_pct)
    s = calc_stats(trades, equity)
    if not s or s["n_trades"] < 15:
        return None
    bwr = abs(s["avg_loss_pct"]) / (s["avg_win_pct"] + abs(s["avg_loss_pct"])) * 100 if s["avg_win_pct"] > 0 else 99
    marker = "★★" if s["profit_factor"] >= 2.0 else ("★" if s["profit_factor"] >= 1.0 else " ")
    print(f"{marker} RSI {rsi_low}/{rsi_high}  SL {sl_pct*100:.1f}%  TP {tp_pct*100:.1f}%  "
          f"→  n={s['n_trades']:3d}  WR={s['win_rate']:.1f}%  "
          f"PF={s['profit_factor']:.2f}  ret={s['total_return']:+.1f}%  "
          f"DD={s['max_drawdown']:.1f}%  bWR={bwr:.1f}%")
    return s


def main():
    print("Загружаю данные 15m 4 года …")
    df_raw = load_ohlcv()
    df_base = add_indicators(df_raw)
    df = add_macro_ema(df_base, MACRO_SPAN)
    print(f"Баров: {len(df):,}  ({df.index[0].date()} → {df.index[-1].date()})\n")

    best = {"pf": 0.0, "params": None}

    rsi_levels = [(26, 74), (27, 73), (28, 72), (29, 71), (30, 70)]
    sl_values  = [0.012, 0.015, 0.018, 0.020, 0.025]
    tp_values  = [0.025, 0.030, 0.035, 0.040, 0.050, 0.060]

    print(f"Макро-фильтр: EMA{MACRO_SPAN} ({MACRO_SPAN*15//60} ч = {MACRO_SPAN*15//60//24} дней)")
    print(f"Данные: 4 года (2022-2026)")
    print("─" * 85)

    for rsi_l, rsi_h in rsi_levels:
        for sl in sl_values:
            for tp in tp_values:
                if tp <= sl * 1.2:
                    continue
                s = test(df, rsi_l, rsi_h, sl, tp)
                if s and s["profit_factor"] > best["pf"]:
                    best["pf"] = s["profit_factor"]
                    best["params"] = (rsi_l, rsi_h, sl, tp, s)

    print("\n" + "═" * 85)
    if best["params"]:
        rsi_l, rsi_h, sl, tp, s = best["params"]
        print(f"\n★★  ЛУЧШИЙ: RSI {rsi_l}/{rsi_h}  SL {sl*100:.1f}%  TP {tp*100:.1f}%  + EMA{MACRO_SPAN}")
        print(f"    n={s['n_trades']}  WR={s['win_rate']:.1f}%  PF={s['profit_factor']:.2f}  "
              f"ret={s['total_return']:+.1f}%  DD={s['max_drawdown']:.1f}%")

if __name__ == "__main__":
    main()
