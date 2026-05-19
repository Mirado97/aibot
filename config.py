SYMBOL    = "ETH/USDT-SWAP"   # OKX фьючерсы (нужны для шорта)
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730

# Комиссии OKX фьючерсы
COMMISSION = 0.0005   # 0.05% taker (фьючи дешевле спота)
SLIPPAGE   = 0.0003

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ ЗЕРКАЛО
# Сигнал лонг → открываем ШОРТ (цена падает 91% раз)
# ──────────────────────────────────────────────────────
TRADE_SIDE = "short"   # "long" или "short"

# ADX
ADX_PERIOD = 14
ADX_MIN    = 22

# EMA
EMA_FAST  = 20
EMA_SLOW  = 50
EMA_MID   = 100
EMA_MACRO = 2016   # ~7 дней на 5m

# RSI — зона «перекупленности» — наш сигнал входа в шорт
RSI_PERIOD = 14
RSI_LOW    = 52
RSI_HIGH   = 72

# Bollinger Bands
BB_PERIOD = 20
BB_STD    = 2.0

# Риск-менеджмент
ATR_PERIOD        = 14
SL_ATR            = 2.0
TP_ATR            = 3.0
TRAIL_TRIGGER_ATR = 1.5
TRAIL_SL_ATR      = 0.5
MAX_HOLD_BARS     = 48
POSITION_PCT      = 0.95
LEVERAGE          = 2       # плечо фьючерсов
