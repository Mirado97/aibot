from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    ADX_MIN, ADX_PERIOD,
    ATR_PERIOD, BB_PERIOD, BB_STD,
    CAPITAL, COMMISSION,
    EMA_FAST, EMA_MID, EMA_MACRO, EMA_SLOW,
    MAX_HOLD_BARS, POSITION_PCT,
    RSI_HIGH, RSI_LOW, RSI_PERIOD,
    SL_ATR, SLIPPAGE, TP_ATR,
    TRAIL_SL_ATR, TRAIL_TRIGGER_ATR,
)

# Сколько баров назад смотрим для определения наклона EMA_MACRO (12 часов)
_MACRO_SLOPE_BARS = 144


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]

    # True Range → ATR
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
    plus_di  = 100 * plus_dm.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr_adx.replace(0, np.nan)
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

    # EMA лесенка
    df["ema_fast"]  = c.ewm(span=EMA_FAST,  adjust=False).mean()
    df["ema_slow"]  = c.ewm(span=EMA_SLOW,  adjust=False).mean()
    df["ema_mid"]   = c.ewm(span=EMA_MID,   adjust=False).mean()
    df["ema_macro"] = c.ewm(span=EMA_MACRO, adjust=False).mean()

    # Bollinger Bands
    df["bb_mid"]   = c.rolling(BB_PERIOD).mean()
    bb_std         = c.rolling(BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std

    # Volume MA
    df["vol_ma"] = df["volume"].rolling(20).mean()

    return df.dropna()


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass
class Trade:
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
        cost = self.entry_price * (1 + COMMISSION + SLIPPAGE)
        net  = self.exit_price  * (1 - COMMISSION - SLIPPAGE)
        return net / cost - 1.0

    @property
    def is_win(self) -> bool:
        return self.pnl_pct > 0

    @property
    def bars_held(self) -> int:
        if self.exit_bar is None:
            return 0
        return self.exit_bar - self.entry_bar


# ---------------------------------------------------------------------------
# Backtest engine
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
    ema_m    = df["ema_mid"].values
    ema_mac  = df["ema_macro"].values
    vols     = df["volume"].values
    vol_ma   = df["vol_ma"].values

    n         = len(df)
    equity    = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital   = CAPITAL

    trades:  list[Trade]     = []
    pos:     Optional[Trade] = None
    pending: bool            = False

    for i in range(_MACRO_SLOPE_BARS + 1, n):
        atr = atrs[i]

        # ── Вход по отложенному сигналу ──────────────────────────────────
        if pending and pos is None:
            entry = opens[i]
            sl    = entry - atr * SL_ATR
            tp    = entry + atr * TP_ATR
            pos   = Trade(entry_bar=i, entry_price=entry, sl_price=sl, tp_price=tp)
            pending = False

        # ── Управление открытой позицией ─────────────────────────────────
        if pos is not None:
            hi, lo, cl = highs[i], lows[i], closes[i]

            # Трейлинг: при +1.5 ATR двигаем стоп в +0.5 ATR
            if not pos.be_moved and hi >= pos.entry_price + atr * TRAIL_TRIGGER_ATR:
                pos.sl_price = pos.entry_price + atr * TRAIL_SL_ATR
                pos.be_moved = True

            def _close(price: float, reason: str) -> None:
                nonlocal capital, pos
                pos.exit_bar    = i
                pos.exit_price  = price
                pos.exit_reason = reason
                capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
                trades.append(pos)
                pos = None

            if opens[i] <= pos.sl_price:
                _close(opens[i], "sl_gap")
            elif lo <= pos.sl_price:
                _close(pos.sl_price, "sl")
            elif hi >= pos.tp_price:
                _close(pos.tp_price, "tp")
            elif (i - pos.entry_bar) >= MAX_HOLD_BARS:
                _close(cl, "timeout")
            elif ema_f[i] < ema_s[i] and (i - pos.entry_bar) > 5:
                _close(cl, "trend_break")

        equity[i] = capital

        # ── Генерация сигнала ─────────────────────────────────────────────
        if pos is None and not pending:
            cl  = closes[i]
            rsi = rsis[i]

            # 1. Макро тренд: 7-дневная EMA растёт (12-часовой наклон)
            macro_up = (cl > ema_mac[i]
                        and ema_mac[i] > ema_mac[i - _MACRO_SLOPE_BARS])

            # 2. Краткосрочный и среднесрочный тренд выровнены
            trend_aligned = ema_f[i] > ema_s[i] > ema_m[i]

            # 3. Покупаем импульс, не откат (RSI в зоне силы)
            momentum = RSI_LOW <= rsi <= RSI_HIGH

            # 4. Покупатели доминируют
            buyers = plus_di[i] > minus_di[i]

            # 5. Есть тренд (не боковик)
            adx_ok = adxs[i] > ADX_MIN

            # 6. Объём подтверждает (не тихое время)
            vol_ok = vols[i] > vol_ma[i] * 0.9

            if macro_up and trend_aligned and momentum and buyers and adx_ok and vol_ok:
                pending = True

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
        print("Нет сделок — возможно, условия входа слишком строгие.")
        return

    sep = "─" * 44
    print(f"\n{sep}")
    print(f"  РЕЗУЛЬТАТЫ БЭКТЕСТА  ETH/USDT  5m")
    print(sep)
    print(f"  Сделок всего     : {stats['n_trades']}")
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
    print(f"  Трейлинг (BE+)   : {stats['be_trades']} сделок")
    print(sep)
    print("  Причины выходов:")
    for reason, cnt in sorted(stats["exit_reasons"].items(), key=lambda x: -x[1]):
        print(f"    {reason:<20} {cnt}")
    print(sep)
