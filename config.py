SYMBOL    = "ETH/USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730        # 2 года истории

# Комиссии OKX spot
COMMISSION = 0.001     # 0.1% per side
SLIPPAGE   = 0.0005    # 0.05% per side

# Детектирование режима рынка
ADX_PERIOD = 14
ADX_TREND  = 28        # ADX > 28 → тренд (строже)
ADX_RANGE  = 20        # ADX < 20 → боковик

# Глобальный тренд-фильтр — не входить лонг ниже EMA200
EMA_TREND_FILTER = 200

# Mean reversion (боковик)
RSI_PERIOD = 14
RSI_BUY    = 28        # жёстче: только экстремальная перепроданность
RSI_EXIT   = 58

BB_PERIOD  = 20
BB_STD     = 2.0

# Trend following (тренд)
EMA_FAST   = 20
EMA_SLOW   = 50

# Риск-менеджмент
ATR_PERIOD    = 14
SL_ATR        = 1.2    # стоп теснее → R:R = 2.08 (breakeven при WR 32.4%)
TP_ATR        = 2.5
MAX_HOLD_BARS = 48
POSITION_PCT  = 0.95
