SYMBOL    = "ETH/USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730

# Комиссии OKX spot
COMMISSION = 0.001
SLIPPAGE   = 0.0005

# ADX
ADX_PERIOD = 14
ADX_MIN    = 20    # минимальный ADX для входа (есть хоть какой-то тренд)

# EMA фильтры тренда (на 5m данных)
EMA_FAST         = 20    # ~100 мин
EMA_SLOW         = 50    # ~250 мин
EMA_MID          = 100   # ~500 мин  (~8ч)
EMA_TREND_FILTER = 200   # ~1000 мин (~16ч) — макро тренд

# RSI
RSI_PERIOD    = 14
RSI_PULL_LOW  = 38   # нижняя граница зоны отката
RSI_PULL_HIGH = 55   # верхняя граница зоны отката

# Риск-менеджмент
ATR_PERIOD    = 14
SL_ATR        = 1.5
TP_ATR        = 2.5
MAX_HOLD_BARS = 36   # 3 часа принудительный выход
POSITION_PCT  = 0.95
