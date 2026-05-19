SYMBOL    = "ETH/USDT:USDT"   # OKX perpetual swap
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730

# Комиссии OKX фьючерсы
COMMISSION = 0.0005
SLIPPAGE   = 0.0003

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ: тренд-выровненный mean reversion
# Нисходящий тренд + RSI > 65 → SHORT (продаём ралли)
# Восходящий тренд + RSI < 35 → LONG  (покупаем откат)
# ──────────────────────────────────────────────────────

# Определение тренда: наклон EMA50 за последние N баров
EMA_SLOPE_BARS = 24   # 2 часа

# ADX
ADX_PERIOD = 14
ADX_MIN    = 18

# EMA
EMA_FAST   = 20
EMA_SLOW   = 50

# RSI
RSI_PERIOD    = 14
RSI_LONG_MAX  = 35    # LONG только когда RSI ниже этого (перепроданность)
RSI_SHORT_MIN = 65    # SHORT только когда RSI выше этого (перекупленность)

# Bollinger Bands
BB_PERIOD = 20
BB_STD    = 2.0

# Риск-менеджмент
ATR_PERIOD    = 14
SL_ATR        = 1.5
TP_ATR        = 2.5   # R:R = 1.67, breakeven WR = 37.5%
MAX_HOLD_BARS = 36
POSITION_PCT  = 0.95
LEVERAGE      = 2
