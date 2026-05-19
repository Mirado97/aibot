SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "15m"
CAPITAL   = 300.0
DAYS_BACK = 1095

COMMISSION = 0.0002   # maker-ордер OKX futures (0.02%)
SLIPPAGE   = 0.0002

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ: Multi-Timeframe Mean Reversion
# Тренд вниз + RSI пик → SHORT
# Тренд вверх + RSI дно → LONG
# Вход ПОСЛЕ подтверждения разворота RSI (не в момент экстремума)
# ──────────────────────────────────────────────────────

# EMA тренда: 48 × 15m = 12 часов
EMA_1H         = 48    # 48 × 15m = 12 часов
EMA_1H_SLOPE   = 12    # наклон за 3 часа (12 × 15m)

# RSI пороги
RSI_PERIOD    = 14
RSI_LONG_MAX  = 28
RSI_SHORT_MIN = 72

# BB
BB_PERIOD = 20
BB_STD    = 2.0

# ADX
ADX_PERIOD = 14
ADX_MIN    = 15

# SL/TP
SL_PCT    = 0.020   # 2.0%
TP_PCT    = 0.035   # 3.5%  (R:R = 1.75)

# Выход по развороту тренда
TREND_EXIT_BARS = 10   # минимум баров (2.5 ч = 10 × 15m) перед trend exit

MAX_HOLD_BARS = 16     # 4 часа (16 × 15m)
POSITION_PCT  = 0.95
LEVERAGE      = 2

# ATR нужен только для индикаторов
ATR_PERIOD = 14
