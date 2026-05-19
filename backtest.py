from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    ADX_PERIOD, ADX_RANGE, ADX_TREND,
    ATR_PERIOD, BB_PERIOD, BB_STD,
    CAPITAL, COMMISSION,
    EMA_FAST, EMA_SLOW, EMA_TREND_FILTER,
    MAX_HOLD_BARS, POSITION_PCT,
    RSI_BUY, RSI_EXIT, RSI_PERIOD,
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

    # True Range
    tr = pd.concat([
        h - l,
        (h - df["close"].shift(1)).abs(),
        (l - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)

    # ATR (Wilder via ewm alpha=1/N)
    df["atr"] = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean()

    # ADX
    up   = h.diff()
    down = -l.diff()
    plus_dm  = np.where((up > down) & (up > 0),  up,   0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    plus_dm_s  = pd.Series(plus_dm,  index=df.index).ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    minus_dm_s = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    atr_adx    = tr.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()

    plus_di  = 100 * plus_dm_s  / atr_adx.replace(0, np.nan)
    minus_di = 100 * minus_dm_s / atr_adx.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    df["adx"]      = dx.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    df["plus_di"]  = plus_di
    df["minus_di"] = minus_di

    # RSI (Wilder)
    delta    = c.diff()
    gain     = delta.clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    loss     = (-delta).clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # Bollinger Bands
    df["bb_mid"]   = c.rolling(BB_PERIOD).mean()
    bb_std         = c.rolling(BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std

    # EMA
    df["ema_fast"]  = c.ewm(span=EMA_FAST,         adjust=False).mean()
    df["ema_slow"]  = c.ewm(span=EMA_SLOW,         adjust=False).mean()
    df["ema_trend"] = c.ewm(span=EMA_TREND_FILTER, adjust=False).mean()

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
    exit_bar:    Optional[int]   = None
    exit_price:  Optional[float] = None
    exit_reason: Optional[str]   = None

    @property
    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        cost  = self.entry_price * (1 + COMMISSION + SLIPPAGE)
        net   = self.exit_price  * (1 - COMMISSION - SLIPPAGE)
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
    opens   = df["open"].values
    highs   = df["high"].values
    lows    = df["low"].values
    closes  = df["close"].values
    atrs    = df["atr"].values
    adxs     = df["adx"].values
    plus_di  = df["plus_di"].values
    minus_di = df["minus_di"].values
    rsis     = df["rsi"].values
    bb_low    = df["bb_lower"].values
    bb_mid    = df["bb_mid"].values
    ema_f     = df["ema_fast"].values
    ema_s     = df["ema_slow"].values
    ema_trend = df["ema_trend"].values
    vols      = df["volume"].values
    vol_ma    = df["vol_ma"].values

    n       = len(df)
    equity  = np.full(n, np.nan)
    equity[0] = CAPITAL
    capital = CAPITAL

    trades:  list[Trade]      = []
    pos:     Optional[Trade]  = None
    pending: bool             = False   # сигнал с прошлой свечи, войти на открытии текущей

    for i in range(1, n):
        atr = atrs[i]

        # ── Вход по отложенному сигналу ──────────────────────────────────
        if pending and pos is None:
            raw_entry = opens[i]
            cost = raw_entry * (1 + SLIPPAGE + COMMISSION)
            sl   = raw_entry - atr * SL_ATR
            tp   = raw_entry + atr * TP_ATR
            pos  = Trade(entry_bar=i, entry_price=raw_entry, sl_price=sl, tp_price=tp)
            pending = False

        # ── Управление открытой позицией ─────────────────────────────────
        if pos is not None:
            o, h2, lo, cl = opens[i], highs[i], lows[i], closes[i]

            def _close(price: float, reason: str) -> None:
                nonlocal capital, pos
                pos.exit_bar   = i
                pos.exit_price = price
                pos.exit_reason = reason
                capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
                trades.append(pos)
                pos = None

            # Гэп вниз ниже стопа
            if o <= pos.sl_price:
                _close(o, "sl_gap")
            # Стоп внутри свечи
            elif lo <= pos.sl_price:
                _close(pos.sl_price, "sl")
            # Тейк внутри свечи
            elif h2 >= pos.tp_price:
                _close(pos.tp_price, "tp")
            # Максимальное удержание
            elif (i - pos.entry_bar) >= MAX_HOLD_BARS:
                _close(cl, "timeout")
            # Сигнал выхода mean-reversion (RSI перекуплен)
            elif adxs[i] < ADX_RANGE and rsis[i] > RSI_EXIT:
                _close(cl, "signal_exit")
            # Тренд сломан (EMA пересечение вниз)
            elif adxs[i] > ADX_TREND and ema_f[i] < ema_s[i]:
                _close(cl, "trend_break")

        equity[i] = capital

        # ── Генерация сигнала на вход (исполнение — следующая свеча) ─────
        if pos is None and not pending:
            adx  = adxs[i]
            rsi  = rsis[i]
            vol  = vols[i]
            vma  = vol_ma[i]
            cl   = closes[i]
            et   = ema_trend[i]

            # Глобальный фильтр: не торгуем в устойчивом нисходящем тренде
            # (цена должна быть не ниже 3% от EMA200)
            above_trend = cl > et * 0.97

            if above_trend and adx < ADX_RANGE:
                # Режим боковика → mean reversion
                # Требуем объёмный всплеск — признак капитуляции
                if (rsi < RSI_BUY
                        and cl < bb_low[i]
                        and vol > vma * 1.3):
                    pending = True

            elif above_trend and adx > ADX_TREND:
                # Режим тренда → покупка на откате к EMA20
                near_ema   = ema_f[i] * 0.990 < cl < ema_f[i] * 1.005
                uptrend    = ema_f[i] > ema_s[i] and plus_di[i] > minus_di[i] + 8
                adx_rising = adxs[i] > adxs[i - 1]
                if (uptrend and near_ema
                        and 42 < rsi < 60
                        and adx_rising):
                    pending = True

    # Закрываем позицию по последней свече
    if pos is not None:
        pos.exit_bar    = n - 1
        pos.exit_price  = closes[n - 1]
        pos.exit_reason = "end_of_data"
        capital = capital * (1 + POSITION_PCT * pos.pnl_pct)
        trades.append(pos)
        equity[n - 1] = capital

    # Заполняем пропуски в кривой капитала (нет сделки → капитал не меняется)
    equity = pd.Series(equity).ffill().values

    return trades, equity


# ---------------------------------------------------------------------------
# Statistics & report
# ---------------------------------------------------------------------------

def calc_stats(trades: list[Trade], equity: np.ndarray) -> dict:
    if not trades:
        return {}

    wins  = [t for t in trades if t.is_win]
    loses = [t for t in trades if not t.is_win]

    total_return = (equity[-1] - equity[0]) / equity[0] * 100
    win_rate     = len(wins) / len(trades) * 100

    avg_win  = np.mean([t.pnl_pct for t in wins])  * 100 if wins  else 0.0
    avg_loss = np.mean([t.pnl_pct for t in loses]) * 100 if loses else 0.0
    gross_profit = sum(t.pnl_pct for t in wins)
    gross_loss   = abs(sum(t.pnl_pct for t in loses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    peak  = np.maximum.accumulate(equity)
    dd    = (equity - peak) / peak
    max_dd = dd.min() * 100

    # Sharpe (аннуализированный, 5m → 105 120 баров/год)
    eq_s = pd.Series(equity)
    rets = eq_s.pct_change().dropna()
    bars_per_year = 365 * 24 * 12
    sharpe = (rets.mean() / rets.std() * np.sqrt(bars_per_year)) if rets.std() > 0 else 0.0

    avg_hold = np.mean([t.bars_held for t in trades])

    exit_reasons = {}
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
        "avg_hold_bars": avg_hold,
        "exit_reasons":  exit_reasons,
    }


def print_report(stats: dict) -> None:
    if not stats:
        print("Нет сделок.")
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
    print(sep)
    print("  Причины выходов:")
    for reason, cnt in sorted(stats["exit_reasons"].items(), key=lambda x: -x[1]):
        print(f"    {reason:<20} {cnt}")
    print(sep)
