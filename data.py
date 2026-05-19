import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ccxt
import pandas as pd

from config import DAYS_BACK, SYMBOL, TIMEFRAME

CACHE_DIR = Path("data")


def _cache_path() -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    safe = SYMBOL.replace("/", "_")
    return CACHE_DIR / f"{safe}_{TIMEFRAME}_{DAYS_BACK}d.parquet"


def load_ohlcv() -> pd.DataFrame:
    cache = _cache_path()

    if cache.exists():
        df = pd.read_parquet(cache)
        age = pd.Timestamp.now(tz="UTC") - df.index[-1]
        if age < pd.Timedelta(hours=6):
            print(f"Кэш актуален: {len(df):,} свечей  ({df.index[0].date()} → {df.index[-1].date()})")
            return df
        print("Кэш устарел, докачиваю...")

    print(f"Загружаю {DAYS_BACK} дней {TIMEFRAME} {SYMBOL} с OKX …")
    exchange = ccxt.okx({"enableRateLimit": True, "options": {"defaultType": "swap"}})

    since_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).timestamp() * 1000
    )
    now_ms   = int(datetime.now(timezone.utc).timestamp() * 1000)
    bar_ms   = 5 * 60 * 1000  # 5 минут в мс

    all_rows: list[list] = []

    while since_ms < now_ms - bar_ms:
        batch = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since_ms, limit=300)
        if not batch:
            break
        all_rows.extend(batch)
        since_ms = batch[-1][0] + 1
        print(f"  {len(all_rows):,} свечей …", end="\r")
        time.sleep(0.2)

    print(f"\nЗагружено {len(all_rows):,} свечей")

    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.set_index("ts", inplace=True)
    df = df[~df.index.duplicated()].sort_index()
    df = df.astype(float)

    df.to_parquet(cache)
    print(f"Сохранено в кэш: {cache}")
    return df
