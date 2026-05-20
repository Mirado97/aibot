"""Бэктест RSI MeanRev + EMA480 на 5 монетах одновременно."""
import numpy as np
import pandas as pd

from data import load_ohlcv
from backtest import add_indicators, run_backtest, calc_stats

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
]

SEP = "─" * 55


def run_symbol(symbol: str) -> dict | None:
    try:
        df_raw = load_ohlcv(symbol)
    except Exception as e:
        print(f"  [{symbol}] ошибка загрузки: {e}")
        return None

    df = add_indicators(df_raw)
    if len(df) < 1000:
        print(f"  [{symbol}] слишком мало баров: {len(df)}")
        return None

    trades, equity = run_backtest(df)
    s = calc_stats(trades, equity)
    return s


def print_row(symbol: str, s: dict) -> None:
    if not s:
        print(f"  {symbol:<22}  нет сделок")
        return
    marker = "★" if s["profit_factor"] >= 1.0 else " "
    print(f"{marker} {symbol:<22}  "
          f"n={s['n_trades']:3d}  "
          f"WR={s['win_rate']:.1f}%  "
          f"PF={s['profit_factor']:.2f}  "
          f"ret={s['total_return']:+.1f}%  "
          f"DD={s['max_drawdown']:.1f}%")


def main() -> None:
    print(f"\n{'=' * 55}")
    print(f"  MULTI-SYMBOL  RSI 28/72 + EMA480  |  15m  |  4 года")
    print(f"{'=' * 55}\n")

    all_trades = []
    all_equities = []
    results = {}

    for sym in SYMBOLS:
        print(f"\n{SEP}")
        s = run_symbol(sym)
        results[sym] = s

    print(f"\n\n{'=' * 55}")
    print(f"  ИТОГИ ПО МОНЕТАМ")
    print(f"{'=' * 55}")
    print(f"  {'Символ':<22}  {'n':>4}  {'WR':>6}  {'PF':>5}  {'Ret':>7}  {'DD':>7}")
    print(f"  {SEP}")

    for sym, s in results.items():
        print_row(sym, s)

    # Повторный прогон для агрегации
    from backtest import Trade
    all_trades_list = []
    print(f"\n  {SEP}")
    print(f"  Загружаю данные повторно для агрегации …")

    for sym in SYMBOLS:
        try:
            df_raw = load_ohlcv(sym)
            df     = add_indicators(df_raw)
            trades, equity = run_backtest(df)
            all_trades_list.extend(trades)
        except Exception:
            pass

    if all_trades_list:
        wins  = [t for t in all_trades_list if t.is_win]
        loses = [t for t in all_trades_list if not t.is_win]
        total_wr = len(wins) / len(all_trades_list) * 100
        gp = sum(t.pnl_pct for t in wins)
        gl = abs(sum(t.pnl_pct for t in loses))
        pf = gp / gl if gl > 0 else float("inf")
        avg_win  = np.mean([t.pnl_pct for t in wins])  * 100 if wins  else 0
        avg_loss = np.mean([t.pnl_pct for t in loses]) * 100 if loses else 0
        bwr = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100 if avg_win > 0 else 0

        print(f"\n  АГРЕГИРОВАННО (5 монет, независимые капиталы):")
        print(f"  Сделок всего : {len(all_trades_list)}  "
              f"(~{len(all_trades_list)//4}/год)")
        print(f"  Win rate     : {total_wr:.1f}%  (безубыток: {bwr:.1f}%)")
        print(f"  Profit factor: {pf:.2f}")
        print(f"  Ср. победа   : {avg_win:+.2f}%")
        print(f"  Ср. потеря   : {avg_loss:+.2f}%")
        print(f"  Сделок/год   : ~{len(all_trades_list)//4}")

    print(f"\n{'=' * 55}\n")


if __name__ == "__main__":
    main()
