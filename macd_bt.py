"""MACD Histogram Reversal strategy backtest.

Signal (на 1h барах — меньше шума):
  Long  — hist падал, теперь растёт, и hist < 0 (перелом под нулём)
          + 1h свеча разворота бычья (close > open)
  Short — hist рос,  теперь падает, и hist > 0 (перелом над нулём)
          + 1h свеча разворота медвежья (close < open)

Entry: следующая 15m свеча (open).
Filter: EMA480 macro на 15m (long только выше EMA, short только ниже).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

from data import load_ohlcv
from config import (
    CAPITAL, COMMISSION, SLIPPAGE, LEVERAGE, POSITION_PCT,
    SL_PCT, TP_PCT, TREND_EXIT_BARS, MAX_HOLD_BARS, EMA_1H, EMA_1H_SLOPE,
    BARS_PER_YEAR,
)

# ── MACD параметры (на 1h) ────────────────────────────────────────────────────
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
EMA_MACRO   = 480   # 5 дней на 15m


# ── Индикаторы ────────────────────────────────────────────────────────────────

def add_indicators(df15: pd.DataFrame) -> pd.DataFrame:
    """Возвращает 15m df с колонками hist_1h и ema_macro для сигналов."""
    # 4h OHLC из 15m
    df1h = df15.resample("4h").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()

    c1h = df1h["close"]
    ema_fast = c1h.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = c1h.ewm(span=MACD_SLOW, adjust=False).mean()
    macd     = ema_fast - ema_slow
    signal   = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    df1h["macd"]        = macd
    df1h["hist"]        = macd - signal
    df1h["candle_bull"] = df1h["close"] > df1h["open"]
    df1h["candle_bear"] = df1h["close"] < df1h["open"]

    # Сигнал: гистограмма пересекает ноль (MACD crossover) пока macd < 0 или > 0
    # Long : hist пересёк 0 снизу вверх (было <0, стало >0) и macd < 0 (всё ещё в отрицательной зоне → нет, smarter:
    # Long : hist[prev] < 0 and hist[cur] > 0 → crossover вверх  (short-term EMA пересекла long-term EMA снизу)
    #        AND macd (ema_fast - ema_slow) всё ещё < 0 значит мы ниже нуля → нет смысла
    #
    # Правильная логика oversold crossover:
    #   Long  — macd < 0 (ниже нуля, медвежья зона) + crossover вверх (hist: <0 → >0)
    #   Short — macd > 0 (выше нуля, бычья зона)    + crossover вниз  (hist: >0 → <0)
    h = df1h["hist"]
    m = df1h["macd"]
    df1h["long_signal"]  = (
        (h.shift(1) < 0) & (h > 0)      # hist пересёк 0 вверх (crossover)
        & (m < 0)                         # MACD всё ещё в отрицательной зоне
        & df1h["candle_bull"]             # подтверждающая бычья свеча
    )
    df1h["short_signal"] = (
        (h.shift(1) > 0) & (h < 0)      # hist пересёк 0 вниз (crossover)
        & (m > 0)                         # MACD всё ещё в положительной зоне
        & df1h["candle_bear"]             # подтверждающая медвежья свеча
    )

    # Макро-фильтр на 15m
    df15 = df15.copy()
    df15["ema_macro"] = df15["close"].ewm(span=EMA_MACRO, adjust=False).mean()
    df15["ema1h"]     = df15["close"].ewm(span=EMA_1H, adjust=False).mean()

    # Сдвиг на 1 бар: сигнал 1h доступен только после закрытия этого бара.
    # Без ffill — сигнал True только на первом 15m баре следующего часа.
    sig = df1h[["long_signal", "short_signal"]].shift(1).reindex(df15.index)
    df15["long_signal"]  = sig["long_signal"].fillna(False).astype(bool)
    df15["short_signal"] = sig["short_signal"].fillna(False).astype(bool)

    return df15.dropna(subset=["ema_macro", "ema1h"])


# ── Trade ─────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    side:        str
    entry_bar:   int
    entry_price: float
    sl_price:    float
    tp_price:    float
    exit_bar:    Optional[int]   = None
    exit_price:  Optional[float] = None
    exit_reason: Optional[str]   = None
    best_price:  Optional[float] = None   # для трейлинга

    @property
    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        ep, xp = self.entry_price, self.exit_price
        c1 = COMMISSION + SLIPPAGE
        if self.side == "long":
            raw = xp * (1 - c1) / (ep * (1 + c1)) - 1
        else:
            raw = ep * (1 - c1) / (xp * (1 + c1)) - 1
        return raw * LEVERAGE

    @property
    def is_win(self) -> bool:
        return self.pnl_pct > 0

    @property
    def bars_held(self) -> int:
        return 0 if self.exit_bar is None else self.exit_bar - self.entry_bar


# ── Engine ────────────────────────────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    sl_pct: float = SL_PCT,
    tp_pct: float = TP_PCT,
    trail_trigger_pct: float = 0.0,   # при каком движении в пользу включить трейлинг (0 = откл)
    trail_dist_pct:    float = 0.0,   # расстояние трейлинга от пика (0 = откл)
) -> tuple[list[Trade], np.ndarray]:
    opens        = df["open"].values
    highs        = df["high"].values
    lows         = df["low"].values
    closes       = df["close"].values
    ema1h        = df["ema1h"].values
    ema_macro    = df["ema_macro"].values
    long_signal  = df["long_signal"].values
    short_signal = df["short_signal"].values

    n         = len(df)
    equity    = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital   = CAPITAL

    trades: list[Trade]         = []
    pos:    Optional[Trade]     = None
    pending_side: Optional[str] = None

    start = EMA_1H_SLOPE + 2

    for i in range(start, n):

        # ── Entry ─────────────────────────────────────────────────────────
        if pending_side and pos is None:
            entry = opens[i]
            side  = pending_side
            if side == "long":
                sl = entry * (1 - sl_pct)
                tp = entry * (1 + tp_pct)
            else:
                sl = entry * (1 + sl_pct)
                tp = entry * (1 - tp_pct)
            pos = Trade(side=side, entry_bar=i,
                        entry_price=entry, sl_price=sl, tp_price=tp)
            pending_side = None

        # ── Position management ───────────────────────────────────────────
        if pos is not None:
            hi, lo, cl = highs[i], lows[i], closes[i]

            def _close(price: float, reason: str) -> None:
                nonlocal capital, pos
                pos.exit_bar    = i
                pos.exit_price  = price
                pos.exit_reason = reason
                capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
                trades.append(pos)
                pos = None

            # ── Trailing SL ───────────────────────────────────────────────
            if trail_trigger_pct > 0:
                if pos.side == "long":
                    if pos.best_price is None or hi > pos.best_price:
                        pos.best_price = hi
                    if pos.best_price >= pos.entry_price * (1 + trail_trigger_pct):
                        new_sl = pos.best_price * (1 - trail_dist_pct)
                        if new_sl > pos.sl_price:
                            pos.sl_price = new_sl
                else:
                    if pos.best_price is None or lo < pos.best_price:
                        pos.best_price = lo
                    if pos.best_price <= pos.entry_price * (1 - trail_trigger_pct):
                        new_sl = pos.best_price * (1 + trail_dist_pct)
                        if new_sl < pos.sl_price:
                            pos.sl_price = new_sl

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

        # ── Signal: 1h MACD перелом + EMA480 macro ───────────────────────
        if pos is None and pending_side is None:
            bull_regime = closes[i] > ema_macro[i]
            bear_regime = closes[i] < ema_macro[i]

            if long_signal[i] and bull_regime:
                pending_side = "long"
            elif short_signal[i] and bear_regime:
                pending_side = "short"

    if pos is not None:
        pos.exit_bar    = n - 1
        pos.exit_price  = closes[n - 1]
        pos.exit_reason = "end_of_data"
        capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
        trades.append(pos)
        equity[n - 1] = capital

    equity = pd.Series(equity).ffill().values
    return trades, equity


# ── Stats ─────────────────────────────────────────────────────────────────────

def calc_stats(trades: list[Trade], equity: np.ndarray) -> dict:
    if not trades:
        return {}
    wins  = [t for t in trades if t.is_win]
    loses = [t for t in trades if not t.is_win]
    longs  = [t for t in trades if t.side == "long"]
    shorts = [t for t in trades if t.side == "short"]

    total_return  = (equity[-1] - equity[0]) / equity[0] * 100
    win_rate      = len(wins) / len(trades) * 100
    avg_win       = np.mean([t.pnl_pct for t in wins])  * 100 if wins  else 0.0
    avg_loss      = np.mean([t.pnl_pct for t in loses]) * 100 if loses else 0.0
    gross_profit  = sum(t.pnl_pct for t in wins)
    gross_loss    = abs(sum(t.pnl_pct for t in loses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    peak   = np.maximum.accumulate(equity)
    max_dd = ((equity - peak) / peak).min() * 100
    rets   = pd.Series(equity).pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(BARS_PER_YEAR) if rets.std() > 0 else 0.0
    bwr    = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100 if avg_win > 0 else 0.0
    exit_reasons: dict[str, int] = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    return {
        "n_trades": len(trades), "n_long": len(longs), "n_short": len(shorts),
        "win_rate": win_rate, "breakeven_wr": bwr, "profit_factor": profit_factor,
        "total_return": total_return, "final_capital": equity[-1],
        "max_drawdown": max_dd, "sharpe": sharpe,
        "avg_win_pct": avg_win, "avg_loss_pct": avg_loss,
        "avg_hold_bars": np.mean([t.bars_held for t in trades]),
        "exit_reasons": exit_reasons,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

SYMBOLS = ["ETH/USDT:USDT", "SOL/USDT:USDT", "DOGE/USDT:USDT",
           "BTC/USDT:USDT", "XRP/USDT:USDT"]

def main() -> None:
    sep = "─" * 60
    print(f"\n{'=' * 60}")
    print(f"  MACD Histogram Reversal  |  15m  |  4 года  |  EMA480")
    print(f"  MACD({MACD_FAST},{MACD_SLOW},{MACD_SIGNAL})  SL={SL_PCT*100:.1f}%  TP={TP_PCT*100:.1f}%")
    print(f"{'=' * 60}\n")

    all_trades = []
    print(f"  {'Символ':<22}  {'n':>4}  {'WR':>6}  {'PF':>5}  {'Ret':>7}  {'DD':>7}  {'bWR':>6}")
    print(f"  {sep}")

    for sym in SYMBOLS:
        try:
            df_raw = load_ohlcv(sym)
        except Exception as e:
            print(f"  {sym:<22}  ошибка: {e}")
            continue
        df = add_indicators(df_raw)
        trades, equity = run_backtest(df)
        s = calc_stats(trades, equity)
        if not s:
            print(f"  {sym:<22}  нет сделок")
            continue
        all_trades.extend(trades)
        marker = "★" if s["profit_factor"] >= 1.0 else " "
        print(f"{marker} {sym:<22}  "
              f"n={s['n_trades']:3d}  "
              f"WR={s['win_rate']:.1f}%  "
              f"PF={s['profit_factor']:.2f}  "
              f"ret={s['total_return']:+.1f}%  "
              f"DD={s['max_drawdown']:.1f}%  "
              f"bWR={s['breakeven_wr']:.1f}%")

    if all_trades:
        wins  = [t for t in all_trades if t.is_win]
        loses = [t for t in all_trades if not t.is_win]
        gp = sum(t.pnl_pct for t in wins)
        gl = abs(sum(t.pnl_pct for t in loses))
        pf = gp / gl if gl > 0 else float("inf")
        wr = len(wins) / len(all_trades) * 100
        avg_win  = np.mean([t.pnl_pct for t in wins])  * 100 if wins  else 0
        avg_loss = np.mean([t.pnl_pct for t in loses]) * 100 if loses else 0
        print(f"\n  АГРЕГАТ (5 монет): {len(all_trades)} сделок (~{len(all_trades)//4}/год)")
        print(f"  WR={wr:.1f}%  PF={pf:.2f}  Ср.победа={avg_win:+.2f}%  Ср.потеря={avg_loss:+.2f}%")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
