"""Бэктест RSI MeanRev + EMA480 на расширенном списке монет (10 новых)."""
import numpy as np
from data import load_ohlcv
from backtest import add_indicators, run_backtest, calc_stats

SYMBOLS = [
    "BNB/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "ADA/USDT:USDT",
    "DOT/USDT:USDT",
    "UNI/USDT:USDT",
    "ATOM/USDT:USDT",
    "LTC/USDT:USDT",
    "TRX/USDT:USDT",
    "BCH/USDT:USDT",
]

SEP = "─" * 60


def run_symbol(symbol: str):
    try:
        df_raw = load_ohlcv(symbol)
    except Exception as e:
        print(f"  [{symbol}] ошибка загрузки: {e}")
        return None, []
    df = add_indicators(df_raw)
    if len(df) < 1000:
        print(f"  [{symbol}] слишком мало баров: {len(df)}")
        return None, []
    trades, equity = run_backtest(df)
    s = calc_stats(trades, equity)
    return s, trades


def main():
    print(f"\n{'=' * 60}")
    print(f"  EXTENDED MULTI  RSI 28/72 + EMA480  |  15m  |  4 года")
    print(f"  Новые монеты: BNB AVAX LINK ADA DOT UNI ATOM LTC TRX BCH")
    print(f"{'=' * 60}\n")

    results = {}
    all_trades = []

    for sym in SYMBOLS:
        print(f"\n{SEP}")
        s, trades = run_symbol(sym)
        results[sym] = s
        all_trades.extend(trades)

    print(f"\n\n{'=' * 60}")
    print(f"  ИТОГИ ПО МОНЕТАМ")
    print(f"{'=' * 60}")
    print(f"  {'Символ':<22}  {'n':>4}  {'WR':>6}  {'PF':>5}  {'Ret':>7}  {'DD':>7}")
    print(f"  {SEP}")

    for sym, s in results.items():
        if not s:
            print(f"  {sym:<22}  нет сделок")
            continue
        marker = "★" if s["profit_factor"] >= 1.0 else " "
        print(f"{marker} {sym:<22}  "
              f"n={s['n_trades']:3d}  "
              f"WR={s['win_rate']:.1f}%  "
              f"PF={s['profit_factor']:.2f}  "
              f"ret={s['total_return']:+.1f}%  "
              f"DD={s['max_drawdown']:.1f}%")

    if all_trades:
        wins  = [t for t in all_trades if t.is_win]
        loses = [t for t in all_trades if not t.is_win]
        total_wr = len(wins) / len(all_trades) * 100
        gp = sum(t.pnl_pct for t in wins)
        gl = abs(sum(t.pnl_pct for t in loses))
        pf = gp / gl if gl > 0 else float("inf")
        avg_win  = np.mean([t.pnl_pct for t in wins])  * 100 if wins  else 0
        avg_loss = np.mean([t.pnl_pct for t in loses]) * 100 if loses else 0

        print(f"\n  АГРЕГИРОВАННО (10 новых монет):")
        print(f"  Сделок всего : {len(all_trades)}  (~{len(all_trades)//4}/год)")
        print(f"  Win rate     : {total_wr:.1f}%")
        print(f"  Profit factor: {pf:.2f}")
        print(f"  Ср. победа   : {avg_win:+.2f}%")
        print(f"  Ср. потеря   : {avg_loss:+.2f}%")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
