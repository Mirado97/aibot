import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ccxt
import pandas as pd

from config import DAYS_BACK, TIMEFRAME

CACHE_DIR = Path("data")


def load_ohlcv(symbol: str = "ETH/USDT:USDT") -> pd.DataFrame:
    CACHE_DIR.mkdir(exist_ok=True)
    safe  = symbol.replace("/", "_")
    cache = CACHE_DIR / f"{safe}_{TIMEFRAME}_{DAYS_BACK}d.parquet"

    if cache.exists():
        df = pd.read_parquet(cache)
        age = pd.Timestamp.now(tz="UTC") - df.index[-1]
        if age < pd.Timedelta(hours=6):
            print(f"  [{symbol}] кэш актуален: {len(df):,} свечей  "
                  f"({df.index[0].date()} → {df.index[-1].date()})")
            return df
        print(f"  [{symbol}] кэш устарел, докачиваю…")

    print(f"  [{symbol}] загружаю {DAYS_BACK} дней {TIMEFRAME} с OKX …")
    exchange = ccxt.okx({"enableRateLimit": True, "options": {"defaultType": "swap"}})

    since_ms = int((datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).timestamp() * 1000)
    now_ms   = int(datetime.now(timezone.utc).timestamp() * 1000)
    bar_ms   = 15 * 60 * 1000   # 15m в мс

    all_rows: list[list] = []
    while since_ms < now_ms - bar_ms:
        batch = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=since_ms, limit=300)
        if not batch:
            break
        all_rows.extend(batch)
        since_ms = batch[-1][0] + 1
        print(f"    {len(all_rows):,} свечей …", end="\r")
        time.sleep(0.2)

    print(f"\n  [{symbol}] загружено {len(all_rows):,} свечей")

    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.set_index("ts", inplace=True)
    df = df[~df.index.duplicated()].sort_index().astype(float)

    df.to_parquet(cache)
    print(f"  [{symbol}] сохранено: {cache}")
    return df
