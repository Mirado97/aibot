from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    ADX_MIN, ADX_PERIOD,
    ATR_PERIOD, BB_PERIOD, BB_STD,
    CAPITAL, COMMISSION,
    EMA_FAST, EMA_SLOW, EMA_SLOPE_BARS,
    LEVERAGE, MAX_HOLD_BARS, POSITION_PCT,
    RSI_LONG_MAX, RSI_PERIOD, RSI_SHORT_MIN,
    SL_ATR, SLIPPAGE, TP_ATR,
)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]

    # ATR
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean()

    # ADX / +DI / -DI
    up       = h.diff()
    down     = -l.diff()
    plus_dm  = pd.Series(np.where((up > down) & (up > 0),   up,   0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr_adx  = tr.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(alpha=1 / ADX_PERIOD,  adjust=False).mean() / atr_adx.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr_adx.replace(0, np.nan)
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    df["adx"]      = dx.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    df["plus_di"]  = plus_di
    df["minus_di"] = minus_di

    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    loss  = (-delta).clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # EMA
    df["ema_fast"] = c.ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = c.ewm(span=EMA_SLOW, adjust=False).mean()

    # Bollinger Bands
    df["bb_mid"]   = c.rolling(BB_PERIOD).mean()
    bb_std         = c.rolling(BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std

    # Volume MA
    df["vol_ma"] = df["volume"].rolling(20).mean()

    return df.dropna()


# ---------------------------------------------------------------------------
# Trade
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    side:        str
    entry_bar:   int
    entry_price: float
    sl_price:    float
    tp_price:    float
    be_moved:    bool          = False
    exit_bar:    Optional[int]   = None
    exit_price:  Optional[float] = None
    exit_reason: Optional[str]   = None

    @property
    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        ep, xp = self.entry_price, self.exit_price
        if self.side == "long":
            raw = xp * (1 - COMMISSION - SLIPPAGE) / (ep * (1 + COMMISSION + SLIPPAGE)) - 1
        else:
            raw = ep * (1 - COMMISSION - SLIPPAGE) / (xp * (1 + COMMISSION + SLIPPAGE)) - 1
        return raw * LEVERAGE

    @property
    def is_win(self) -> bool:
        return self.pnl_pct > 0

    @property
    def bars_held(self) -> int:
        if self.exit_bar is None:
            return 0
        return self.exit_bar - self.entry_bar


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def run_backtest(df: pd.DataFrame) -> tuple[list[Trade], np.ndarray]:
    opens    = df["open"].values
    highs    = df["high"].values
    lows     = df["low"].values
    closes   = df["close"].values
    atrs     = df["atr"].values
    adxs     = df["adx"].values
    plus_di  = df["plus_di"].values
    minus_di = df["minus_di"].values
    rsis     = df["rsi"].values
    ema_f    = df["ema_fast"].values
    ema_s    = df["ema_slow"].values
    bb_up    = df["bb_upper"].values
    bb_lo    = df["bb_lower"].values
    vols     = df["volume"].values
    vol_ma   = df["vol_ma"].values

    n         = len(df)
    equity    = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital   = CAPITAL

    trades:  list[Trade]     = []
    pos:     Optional[Trade] = None
    pending_side: Optional[str] = None

    for i in range(EMA_SLOPE_BARS + 1, n):
        atr = atrs[i]

        # ── Вход ─────────────────────────────────────────────────────────
        if pending_side and pos is None:
            entry = opens[i]
            side  = pending_side
            if side == "long":
                sl = entry - atr * SL_ATR
                tp = entry + atr * TP_ATR
            else:
                sl = entry + atr * SL_ATR
                tp = entry - atr * TP_ATR
            pos = Trade(side=side, entry_bar=i, entry_price=entry,
                        sl_price=sl, tp_price=tp)
            pending_side = None

        # ── Управление позицией ───────────────────────────────────────────
        if pos is not None:
            hi, lo, cl = highs[i], lows[i], closes[i]

            # Трейлинг: lock in profit после движения на 1 ATR
            if not pos.be_moved:
                if pos.side == "long"  and hi >= pos.entry_price + atr:
                    pos.sl_price = pos.entry_price
                    pos.be_moved = True
                elif pos.side == "short" and lo <= pos.entry_price - atr:
                    pos.sl_price = pos.entry_price
                    pos.be_moved = True

            def _close(price: float, reason: str) -> None:
                nonlocal capital, pos
                pos.exit_bar    = i
                pos.exit_price  = price
                pos.exit_reason = reason
                capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
                trades.append(pos)
                pos = None

            if pos.side == "long":
                if   opens[i] <= pos.sl_price:                     _close(opens[i],     "sl_gap")
                elif lo       <= pos.sl_price:                      _close(pos.sl_price, "sl")
                elif hi       >= pos.tp_price:                      _close(pos.tp_price, "tp")
                elif (i - pos.entry_bar) >= MAX_HOLD_BARS:          _close(cl,           "timeout")
                elif rsis[i] > 65 and (i - pos.entry_bar) > 3:     _close(cl,           "rsi_exit")
            else:  # short
                if   opens[i] >= pos.sl_price:                     _close(opens[i],     "sl_gap")
                elif hi       >= pos.sl_price:                      _close(pos.sl_price, "sl")
                elif lo       <= pos.tp_price:                      _close(pos.tp_price, "tp")
                elif (i - pos.entry_bar) >= MAX_HOLD_BARS:          _close(cl,           "timeout")
                elif rsis[i] < 35 and (i - pos.entry_bar) > 3:     _close(cl,           "rsi_exit")

        equity[i] = capital

        # ── Генерация сигнала ─────────────────────────────────────────────
        if pos is None and pending_side is None:
            rsi  = rsis[i]
            cl   = closes[i]
            adx  = adxs[i]

            # Наклон EMA50 определяет тренд
            ema_slope_up   = ema_s[i] > ema_s[i - EMA_SLOPE_BARS]
            ema_slope_down = ema_s[i] < ema_s[i - EMA_SLOPE_BARS]

            adx_ok = adx > ADX_MIN
            vol_ok = vols[i] > vol_ma[i] * 0.7

            # LONG: восходящий тренд + перепроданность
            if (ema_slope_up
                    and ema_f[i] > ema_s[i]      # краткосрочный тренд вверх
                    and rsi < RSI_LONG_MAX        # RSI перепродан
                    and cl < bb_lo[i]             # цена у нижней полосы BB
                    and adx_ok
                    and vol_ok):
                pending_side = "long"

            # SHORT: нисходящий тренд + перекупленность
            elif (ema_slope_down
                    and ema_f[i] < ema_s[i]      # краткосрочный тренд вниз
                    and rsi > RSI_SHORT_MIN       # RSI перекуплен
                    and cl > bb_up[i]             # цена у верхней полосы BB
                    and adx_ok
                    and vol_ok):
                pending_side = "short"

    # Закрываем остаток
    if pos is not None:
        pos.exit_bar    = n - 1
        pos.exit_price  = closes[n - 1]
        pos.exit_reason = "end_of_data"
        capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
        trades.append(pos)
        equity[n - 1] = capital

    equity = pd.Series(equity).ffill().values
    return trades, equity


# ---------------------------------------------------------------------------
# Stats & report
# ---------------------------------------------------------------------------

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

    eq_s          = pd.Series(equity)
    rets          = eq_s.pct_change().dropna()
    bars_per_year = 365 * 24 * 12
    sharpe = rets.mean() / rets.std() * np.sqrt(bars_per_year) if rets.std() > 0 else 0.0

    exit_reasons: dict[str, int] = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    return {
        "n_trades":      len(trades),
        "n_long":        len(longs),
        "n_short":       len(shorts),
        "win_rate":      win_rate,
        "profit_factor": profit_factor,
        "total_return":  total_return,
        "final_capital": equity[-1],
        "max_drawdown":  max_dd,
        "sharpe":        sharpe,
        "avg_win_pct":   avg_win,
        "avg_loss_pct":  avg_loss,
        "avg_hold_bars": np.mean([t.bars_held for t in trades]),
        "exit_reasons":  exit_reasons,
        "be_trades":     sum(1 for t in trades if t.be_moved),
    }


def print_report(stats: dict) -> None:
    if not stats:
        print("Нет сделок.")
        return

    sep = "─" * 44
    print(f"\n{sep}")
    print(f"  БЭКТЕСТ ETH/USDT  5m  |  Trend Mean Reversion")
    print(sep)
    print(f"  Сделок всего     : {stats['n_trades']}  "
          f"(лонг: {stats['n_long']}, шорт: {stats['n_short']})")
    print(f"  Win rate         : {stats['win_rate']:.1f}%")
    print(f"  Profit factor    : {stats['profit_factor']:.2f}")
    print(f"  Доходность       : {stats['total_return']:+.1f}%")
    print(f"  Итоговый капитал : ${stats['final_capital']:.2f}")
    print(f"  Max drawdown     : {stats['max_drawdown']:.1f}%")
    print(f"  Sharpe (ann)     : {stats['sharpe']:.2f}")
    print(f"  Ср. победа       : {stats['avg_win_pct']:+.2f}%")
    print(f"  Ср. потеря       : {stats['avg_loss_pct']:+.2f}%")
    print(f"  Ср. держание     : {stats['avg_hold_bars']:.0f} баров  "
          f"({stats['avg_hold_bars'] * 5 / 60:.1f} ч)")
    print(f"  Трейлинг (BE)    : {stats['be_trades']} сделок")
    print(sep)
    print("  Причины выходов:")
    for reason, cnt in sorted(stats["exit_reasons"].items(), key=lambda x: -x[1]):
        print(f"    {reason:<20} {cnt}")
    print(sep)
