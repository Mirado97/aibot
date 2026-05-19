SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730

COMMISSION = 0.0005
SLIPPAGE   = 0.0003

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ: Multi-Timeframe Mean Reversion
# 1h тренд вниз + 5m RSI пик → SHORT
# 1h тренд вверх + 5m RSI дно → LONG
# Вход ПОСЛЕ подтверждения разворота RSI (не в момент экстремума)
# ──────────────────────────────────────────────────────

# Симуляция 1h тренда через EMA(144) на 5m барах
EMA_1H         = 144   # 144 × 5m = 12 часов ≈ 1h тренд
EMA_1H_SLOPE   = 36    # наклон за 3 часа

# RSI пороги (вход только в экстремальных зонах)
RSI_PERIOD    = 14
RSI_LONG_MAX  = 33     # RSI дно для лонга
RSI_SHORT_MIN = 67     # RSI пик для шорта

# BB
BB_PERIOD = 20
BB_STD    = 2.0

# ADX
ADX_PERIOD = 14
ADX_MIN    = 15

# Фиксированный % SL/TP (не ATR — стабильнее на волатильном рынке)
SL_PCT = 0.020    # 2.0% стоп
TP_PCT = 0.030    # 3.0% тейк  (R:R = 1.5, breakeven WR = 40%)

MAX_HOLD_BARS = 48
POSITION_PCT  = 0.95
LEVERAGE      = 2

# ATR нужен только для индикаторов
ATR_PERIOD = 14
