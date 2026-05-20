SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 1095

COMMISSION = 0.0002   # maker OKX (0.02%)
SLIPPAGE   = 0.0002

# ── Стратегия: EMA Momentum + ATR Trailing Stop ────────────────────────────
# Вход: свежий крест EMA9/21 + RSI зона + объём + макротренд EMA50
# SL: фиксированный 1.5× ATR; TP: динамический trailing от пика

EMA_FAST  = 9    # 45 мин
EMA_SLOW  = 21   # 1 ч 45 мин
EMA_TREND = 50   # 4 ч 10 мин (макро-фильтр)

ATR_PERIOD     = 14
ATR_SL_MULT    = 1.5   # SL = 1.5× ATR от цены входа
ATR_TRAIL_MULT = 1.5   # trailing SL = пик − 1.5× ATR

VOL_PERIOD = 20
VOL_MULT   = 1.3       # объём > 1.3× средний (импульс, не дрейф)

RSI_PERIOD    = 14
RSI_LONG_MIN  = 45     # нет перепроданности (мы входим в тренд)
RSI_LONG_MAX  = 72
RSI_SHORT_MIN = 28
RSI_SHORT_MAX = 55

MIN_HOLD_BARS = 3      # минимум 15 мин до выхода по signal_exit
MAX_HOLD_BARS = 48     # максимум 4 часа (48 × 5m)

LEVERAGE     = 2
POSITION_PCT = 0.95

BARS_PER_YEAR = 365 * 24 * 12  # 5m баров в году
