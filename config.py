SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "3m"
CAPITAL   = 300.0
DAYS_BACK = 1095

COMMISSION = 0.0002   # maker-ордер OKX futures (0.02%)
SLIPPAGE   = 0.0002

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ: RSI Mean Reversion (скальп 3m)
# RSI экстремум + BB touch → вход по тренду EMA
# SL/TP фиксированные
# ──────────────────────────────────────────────────────

# EMA тренд: 100 × 3m = 5 часов
EMA_1H       = 100   # span EMA
EMA_1H_SLOPE = 20    # наклон за 1 час (20 × 3m)

# BB
BB_PERIOD = 20
BB_STD    = 2.0

# RSI
RSI_PERIOD = 14
RSI_LOW    = 25   # порог перепроданности
RSI_HIGH   = 75   # порог перекупленности

# SL/TP
SL_PCT = 0.003   # 0.3%
TP_PCT = 0.006   # 0.6%  →  R:R = 2.0

# Выход по развороту тренда
TREND_EXIT_BARS = 8    # минимум 8 баров (24 мин) перед trend exit

MAX_HOLD_BARS = 20     # 1 час (20 × 3m)
POSITION_PCT  = 0.95
LEVERAGE      = 2

# ATR
ATR_PERIOD = 14
