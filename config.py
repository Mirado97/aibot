SYMBOL    = "ETH/USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730

# Комиссии OKX spot
COMMISSION = 0.001
SLIPPAGE   = 0.0005

# ADX
ADX_PERIOD = 14
ADX_MIN    = 22

# EMA фильтры тренда (на 5m барах)
EMA_FAST  = 20     # ~100 мин
EMA_SLOW  = 50     # ~250 мин
EMA_MID   = 100    # ~500 мин (~8 ч)
EMA_MACRO = 2016   # 7 дней (7 * 24 * 12 = 2016 баров по 5m)

# RSI
RSI_PERIOD = 14
RSI_LOW    = 52    # нижняя граница зоны силы (покупаем импульс, не откат)
RSI_HIGH   = 72    # верхняя граница (не гонимся за перекупленностью)

# Bollinger Bands (только для индикатора, не для сигналов)
BB_PERIOD = 20
BB_STD    = 2.0

# Риск-менеджмент
ATR_PERIOD        = 14
SL_ATR            = 2.0   # шире — меньше ложных стопов
TP_ATR            = 3.0   # R:R = 1.5 (breakeven при WR > 40%)
TRAIL_TRIGGER_ATR = 1.5   # при достижении +1.5 ATR — стоп в +0.5 ATR
TRAIL_SL_ATR      = 0.5
MAX_HOLD_BARS     = 48    # 4 часа
POSITION_PCT      = 0.95
