from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    ATR_PERIOD, BARS_PER_YEAR, BB_PERIOD, BB_STD,
    CAPITAL, COMMISSION,
    EMA_1H, EMA_1H_SLOPE, EMA_MACRO,
    LEVERAGE, MAX_HOLD_BARS, POSITION_PCT,
    RSI_HIGH, RSI_LOW, RSI_PERIOD,
    SL_PCT, SLIPPAGE, TP_PCT, TREND_EXIT_BARS,
)


# ── Indicators ───────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]

    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean()

    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    loss  = (-delta).clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    df["ema1h"] = c.ewm(span=EMA_1H, adjust=False).mean()

    df["bb_mid"]   = c.rolling(BB_PERIOD).mean()
    bb_std         = c.rolling(BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std

    # Макро-фильтр режима: EMA480 = 5 дней (отсекает сделки против рынка)
    df["ema_macro"] = c.ewm(span=EMA_MACRO, adjust=False).mean()

    return df.dropna(subset=["atr", "rsi", "ema1h", "bb_mid", "bb_upper", "bb_lower"])


# ── Trade ────────────────────────────────────────────────────────────────────

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

def run_backtest(
    df: pd.DataFrame,
    rsi_low:  float = RSI_LOW,
    rsi_high: float = RSI_HIGH,
    sl_pct:   float = SL_PCT,
    tp_pct:   float = TP_PCT,
) -> tuple[list[Trade], np.ndarray]:
    opens     = df["open"].values
    highs     = df["high"].values
    lows      = df["low"].values
    closes    = df["close"].values
    rsi       = df["rsi"].values
    ema1h     = df["ema1h"].values
    ema_macro = df["ema_macro"].values
    bb_upper  = df["bb_upper"].values
    bb_lower  = df["bb_lower"].values

    n         = len(df)
    equity    = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital   = CAPITAL

    trades: list[Trade]         = []
    pos:    Optional[Trade]     = None
    pending_side: Optional[str] = None

    start = EMA_1H_SLOPE + 2

    for i in range(start, n):

        # ── Entry ────────────────────────────────────────────────────────
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

        # ── Position management ──────────────────────────────────────────
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

        # ── Signal: RSI extremum + BB touch + EMA trend ───────────────────
        if pos is None and pending_side is None:
            trend_up   = ema1h[i] > ema1h[i - EMA_1H_SLOPE]
            trend_down = ema1h[i] < ema1h[i - EMA_1H_SLOPE]

            # Макро-фильтр: торгуем только в согласии с 5-дневным трендом
            bull_regime = closes[i] > ema_macro[i]
            bear_regime = closes[i] < ema_macro[i]

            if (rsi[i] < rsi_low
                    and closes[i] <= bb_lower[i] * 1.005
                    and trend_up
                    and bull_regime):
                pending_side = "long"

            elif (rsi[i] > rsi_high
                    and closes[i] >= bb_upper[i] * 0.995
                    and trend_down
                    and bear_regime):
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


def print_report(stats: dict, label: str = "") -> None:
    if not stats:
        print("Нет сделок — условия не выполнились за период.")
        return

    sep = "─" * 44
    title = f"15m  |  RSI MeanRev{' ' + label if label else ''}"
    print(f"\n{sep}")
    print(f"  БЭКТЕСТ ETH/USDT:USDT  {title}")
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
          f"({stats['avg_hold_bars'] * 15 / 60:.1f} ч)")
    print(sep)
    print("  Причины выходов:")
    for reason, cnt in sorted(stats["exit_reasons"].items(), key=lambda x: -x[1]):
        print(f"    {reason:<20} {cnt}")
    print(sep)
