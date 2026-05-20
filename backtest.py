from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    ATR_PERIOD, ATR_SL_MULT, ATR_TRAIL_MULT,
    BARS_PER_YEAR, BREAKOUT_BARS, CAPITAL, COMMISSION,
    EMA_TREND, EMA_TREND_SLOPE,
    LEVERAGE, MAX_HOLD_BARS, MIN_HOLD_BARS, POSITION_PCT,
    RSI_LONG_MAX, RSI_LONG_MIN, RSI_PERIOD,
    RSI_SHORT_MAX, RSI_SHORT_MIN,
    SLIPPAGE, VOL_MULT, VOL_PERIOD,
)


# ── Indicators ───────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    # ATR
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean()

    # Макро-тренд
    df["ema_trend"] = c.ewm(span=EMA_TREND, adjust=False).mean()

    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    loss  = (-delta).clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # Объём MA
    df["vol_ma"] = v.rolling(VOL_PERIOD).mean()

    # Пробойные уровни: максимум/минимум предыдущих N баров (shift(1) = без текущего)
    df["break_high"] = h.rolling(BREAKOUT_BARS).max().shift(1)
    df["break_low"]  = l.rolling(BREAKOUT_BARS).min().shift(1)

    return df.dropna(subset=["atr", "ema_trend", "rsi", "vol_ma", "break_high", "break_low"])


# ── Trade ────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    side:        str
    entry_bar:   int
    entry_price: float
    sl_price:    float
    exit_bar:    Optional[int]   = None
    exit_price:  Optional[float] = None
    exit_reason: Optional[str]   = None

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
        if self.exit_bar is None:
            return 0
        return self.exit_bar - self.entry_bar


# ── Engine ───────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame) -> tuple[list[Trade], np.ndarray]:
    opens       = df["open"].values
    highs       = df["high"].values
    lows        = df["low"].values
    closes      = df["close"].values
    atr         = df["atr"].values
    ema_trend   = df["ema_trend"].values
    rsi         = df["rsi"].values
    volume      = df["volume"].values
    vol_ma      = df["vol_ma"].values
    break_high  = df["break_high"].values
    break_low   = df["break_low"].values

    n         = len(df)
    equity    = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital   = CAPITAL

    trades: list[Trade]         = []
    pos:    Optional[Trade]     = None
    pending_side: Optional[str] = None

    trail_sl:   float = np.nan
    peak_price: float = np.nan

    start = EMA_TREND + BREAKOUT_BARS + 2

    for i in range(start, n):

        # ── Entry ────────────────────────────────────────────────────────
        if pending_side and pos is None:
            entry   = opens[i]
            side    = pending_side
            sl_dist = ATR_SL_MULT * atr[i - 1]

            # Отклоняем если SL слишком мал для покрытия комиссий
            if sl_dist / entry < (COMMISSION + SLIPPAGE) * 3:
                pending_side = None
            else:
                sl = entry - sl_dist if side == "long" else entry + sl_dist
                pos        = Trade(side=side, entry_bar=i, entry_price=entry, sl_price=sl)
                trail_sl   = sl
                peak_price = entry
                pending_side = None

        # ── Position management ──────────────────────────────────────────
        if pos is not None:
            hi, lo, cl  = highs[i], lows[i], closes[i]
            sl_dist_orig = abs(pos.entry_price - pos.sl_price)
            bars_in      = i - pos.entry_bar

            def _close(price: float, reason: str) -> None:
                nonlocal capital, pos, trail_sl, peak_price
                pos.exit_bar    = i
                pos.exit_price  = price
                pos.exit_reason = reason
                capital    = capital * (1 + POSITION_PCT * pos.pnl_pct)
                trades.append(pos)
                pos        = None
                trail_sl   = np.nan
                peak_price = np.nan

            if pos.side == "long":
                peak_price = max(peak_price, hi)
                # Безубыток при 1R
                if peak_price >= pos.entry_price + sl_dist_orig:
                    trail_sl = max(trail_sl, pos.entry_price)
                # Trailing: тянем за пиком
                trail_sl = max(trail_sl, peak_price - ATR_TRAIL_MULT * atr[i])

                if   opens[i] <= trail_sl:                                    _close(opens[i], "sl_gap")
                elif lo <= trail_sl:                                          _close(trail_sl, "sl")
                elif bars_in >= MAX_HOLD_BARS:                                _close(cl,       "timeout")
                # Выход при развороте тренда (после минимального удержания)
                elif (bars_in >= MIN_HOLD_BARS
                        and closes[i] < ema_trend[i]
                        and ema_trend[i] < ema_trend[i - EMA_TREND_SLOPE]):  _close(cl,       "trend_exit")

            else:  # short
                peak_price = min(peak_price, lo)
                if peak_price <= pos.entry_price - sl_dist_orig:
                    trail_sl = min(trail_sl, pos.entry_price)
                trail_sl = min(trail_sl, peak_price + ATR_TRAIL_MULT * atr[i])

                if   opens[i] >= trail_sl:                                    _close(opens[i], "sl_gap")
                elif hi >= trail_sl:                                          _close(trail_sl, "sl")
                elif bars_in >= MAX_HOLD_BARS:                                _close(cl,       "timeout")
                elif (bars_in >= MIN_HOLD_BARS
                        and closes[i] > ema_trend[i]
                        and ema_trend[i] > ema_trend[i - EMA_TREND_SLOPE]):  _close(cl,       "trend_exit")

        equity[i] = capital

        # ── Signal: свежий пробой N-bar high/low ─────────────────────────
        if pos is None and pending_side is None:
            vol_ok     = volume[i] > vol_ma[i] * VOL_MULT
            trend_up   = (closes[i] > ema_trend[i]
                          and ema_trend[i] > ema_trend[i - EMA_TREND_SLOPE])
            trend_down = (closes[i] < ema_trend[i]
                          and ema_trend[i] < ema_trend[i - EMA_TREND_SLOPE])

            # Свежий пробой: текущий бар пробил, предыдущий — нет
            bo_up   = closes[i] > break_high[i] and closes[i-1] <= break_high[i-1]
            bo_down = closes[i] < break_low[i]  and closes[i-1] >= break_low[i-1]

            if bo_up and RSI_LONG_MIN < rsi[i] < RSI_LONG_MAX and vol_ok and trend_up:
                pending_side = "long"

            elif bo_down and RSI_SHORT_MIN < rsi[i] < RSI_SHORT_MAX and vol_ok and trend_down:
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


# ── Stats & report ───────────────────────────────────────────────────────────

def calc_stats(trades: list[Trade], equity: np.ndarray) -> dict:
    if not trades:
        return {}

    wins   = [t for t in trades if t.is_win]
    loses  = [t for t in trades if not t.is_win]
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

    eq_s   = pd.Series(equity)
    rets   = eq_s.pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(BARS_PER_YEAR) if rets.std() > 0 else 0.0

    exit_reasons: dict[str, int] = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    breakeven_wr = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100 if avg_win > 0 else 0.0

    return {
        "n_trades":      len(trades),
        "n_long":        len(longs),
        "n_short":       len(shorts),
        "win_rate":      win_rate,
        "breakeven_wr":  breakeven_wr,
        "profit_factor": profit_factor,
        "total_return":  total_return,
        "final_capital": equity[-1],
        "max_drawdown":  max_dd,
        "sharpe":        sharpe,
        "avg_win_pct":   avg_win,
        "avg_loss_pct":  avg_loss,
        "avg_hold_bars": np.mean([t.bars_held for t in trades]),
        "exit_reasons":  exit_reasons,
    }


def print_report(stats: dict) -> None:
    if not stats:
        print("Нет сделок — условия не выполнились за период.")
        return

    sep = "─" * 44
    print(f"\n{sep}")
    print(f"  БЭКТЕСТ ETH/USDT:USDT  5m  |  Breakout")
    print(sep)
    print(f"  Сделок всего     : {stats['n_trades']}  "
          f"(L:{stats['n_long']} / S:{stats['n_short']})")
    print(f"  Win rate         : {stats['win_rate']:.1f}%  "
          f"(безубыток: {stats['breakeven_wr']:.1f}%)")
    print(f"  Profit factor    : {stats['profit_factor']:.2f}")
    print(f"  Доходность       : {stats['total_return']:+.1f}%")
    print(f"  Итоговый капитал : ${stats['final_capital']:.2f}")
    print(f"  Max drawdown     : {stats['max_drawdown']:.1f}%")
    print(f"  Sharpe (ann)     : {stats['sharpe']:.2f}")
    print(f"  Ср. победа       : {stats['avg_win_pct']:+.2f}%")
    print(f"  Ср. потеря       : {stats['avg_loss_pct']:+.2f}%")
    print(f"  Ср. держание     : {stats['avg_hold_bars']:.0f} баров  "
          f"({stats['avg_hold_bars'] * 5 / 60:.1f} ч)")
    print(sep)
    print("  Причины выходов:")
    for reason, cnt in sorted(stats["exit_reasons"].items(), key=lambda x: -x[1]):
        print(f"    {reason:<20} {cnt}")
    print(sep)
