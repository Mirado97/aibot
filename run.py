import matplotlib.pyplot as plt
import numpy as np

from backtest import add_indicators, calc_stats, print_report, run_backtest
from data import load_ohlcv


def main() -> None:
    # 1. Данные
    df = load_ohlcv()

    # 2. Индикаторы
    print("Считаю индикаторы …")
    df = add_indicators(df)
    print(f"Баров после dropna: {len(df):,}  "
          f"({df.index[0].date()} → {df.index[-1].date()})")

    # 3. Бэктест
    print("Прогоняю бэктест …")
    trades, equity = run_backtest(df)

    # 4. Отчёт
    stats = calc_stats(trades, equity)
    print_report(stats)

    # 5. График
    _plot(df, trades, equity)


def _plot(df, trades, equity) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle("ETH/USDT 5m  |  Hybrid Regime Strategy", fontsize=13)

    idx = np.arange(len(df))

    # Кривая капитала
    ax1.plot(idx, equity, color="steelblue", linewidth=1.2, label="Equity")
    ax1.axhline(equity[0], color="gray", linestyle="--", linewidth=0.8, alpha=0.6)

    # Точки входа/выхода
    entry_idx = [t.entry_bar for t in trades]
    entry_eq  = [equity[t.entry_bar] for t in trades]
    win_exit  = [equity[t.exit_bar]  for t in trades if t.is_win]
    win_idx   = [t.exit_bar          for t in trades if t.is_win]
    los_exit  = [equity[t.exit_bar]  for t in trades if not t.is_win]
    los_idx   = [t.exit_bar          for t in trades if not t.is_win]

    ax1.scatter(entry_idx, entry_eq, marker="^", color="green", s=20, zorder=5, label="Вход")
    ax1.scatter(win_idx,   win_exit,  marker="o", color="lime",  s=15, zorder=5, label="TP/Win")
    ax1.scatter(los_idx,   los_exit,  marker="o", color="red",   s=15, zorder=5, label="SL/Loss")

    ax1.set_ylabel("Капитал ($)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # Просадка
    peak = np.maximum.accumulate(equity)
    dd   = (equity - peak) / peak * 100
    ax2.fill_between(idx, dd, 0, color="red", alpha=0.4, label="Drawdown")
    ax2.set_ylabel("Drawdown %")
    ax2.set_xlabel("Бар (5m)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("backtest_result.png", dpi=130)
    print("График сохранён: backtest_result.png")
    plt.show()


if __name__ == "__main__":
    main()
