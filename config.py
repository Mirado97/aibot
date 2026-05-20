SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "5m"
CAPITAL   = 300.0
DAYS_BACK = 1095

COMMISSION = 0.0002   # maker OKX (0.02%)
SLIPPAGE   = 0.0002

# ── Стратегия: N-Bar Breakout + ATR Trailing Stop ──────────────────────────
# Сигнал: цена закрывается выше/ниже максимума/минимума последних N баров
# с подтверждением объёма и направления EMA50
# SL: 1.5× ATR от цены входа; TP: динамический trailing

BREAKOUT_BARS = 20     # ширина окна пробоя (20 × 5m = 100 мин)

EMA_TREND       = 50   # макро-тренд (50 × 5m = 4ч10м)
EMA_TREND_SLOPE = 12   # наклон EMA50 за 12 баров (1 час)

ATR_PERIOD     = 14
ATR_SL_MULT    = 1.5   # SL = 1.5× ATR от входа
ATR_TRAIL_MULT = 1.5   # trailing SL = пик − 1.5× ATR

VOL_PERIOD = 20
VOL_MULT   = 1.5       # объём > 1.5× средний (реальный импульс)

RSI_PERIOD    = 14
RSI_LONG_MIN  = 50     # тренд вверх (не перепродан)
RSI_LONG_MAX  = 75     # не перекуплен
RSI_SHORT_MIN = 25
RSI_SHORT_MAX = 50

MIN_HOLD_BARS = 6      # минимум 30 мин до signal_exit
MAX_HOLD_BARS = 48     # максимум 4 часа

LEVERAGE     = 2
POSITION_PCT = 0.95

BARS_PER_YEAR = 365 * 24 * 12  # 5m баров в году
