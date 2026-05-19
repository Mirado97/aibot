SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730

COMMISSION = 0.0002   # maker-ордер OKX futures (0.02%)
SLIPPAGE   = 0.0002

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ: Multi-Timeframe Mean Reversion
# 1h тренд вниз + 5m RSI пик → SHORT
# 1h тренд вверх + 5m RSI дно → LONG
# Вход ПОСЛЕ подтверждения разворота RSI (не в момент экстремума)
# ──────────────────────────────────────────────────────

# Симуляция 1h тренда через EMA(144) на 5m барах
EMA_1H         = 144   # 144 × 5m = 12 часов
EMA_1H_SLOPE   = 36    # наклон за 3 часа

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

# SL/TP — возвращаемся к параметрам, давшим 42.8% WR
SL_PCT    = 0.020   # 2.0%
TP_PCT    = 0.035   # 3.5%  (R:R = 1.75, breakeven WR = 36.4% с maker-комиссией)

# Выход по развороту тренда (вместо таймаута)
TREND_EXIT_BARS = 30   # минимум баров (2.5 ч) перед trend exit

MAX_HOLD_BARS = 48
POSITION_PCT  = 0.95
LEVERAGE      = 2

# ATR нужен только для индикаторов
ATR_PERIOD = 14
