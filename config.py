SYMBOL    = "ETH/USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 730        # 2 года истории

# Комиссии OKX spot
COMMISSION = 0.001     # 0.1% per side
SLIPPAGE   = 0.0005    # 0.05% per side

# Детектирование режима рынка
ADX_PERIOD = 14
ADX_TREND  = 25        # ADX > 25 → тренд
ADX_RANGE  = 20        # ADX < 20 → боковик

# Mean reversion (боковик)
RSI_PERIOD = 14
RSI_BUY    = 32        # oversold порог входа
RSI_EXIT   = 58        # overbought порог выхода

BB_PERIOD  = 20
BB_STD     = 2.0

# Trend following (тренд)
EMA_FAST   = 20
EMA_SLOW   = 50

# Риск-менеджмент
ATR_PERIOD    = 14
SL_ATR        = 1.5    # стоп = вход - ATR * 1.5
TP_ATR        = 2.5    # тейк = вход + ATR * 2.5
MAX_HOLD_BARS = 48     # принудительный выход через 4 часа (48 × 5m)
POSITION_PCT  = 0.95   # 95% капитала на сделку
