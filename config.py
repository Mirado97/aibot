SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "15m"
CAPITAL   = 300.0
DAYS_BACK = 1460   # 4 года → больше сделок

COMMISSION = 0.0002
SLIPPAGE   = 0.0002

# ── Стратегия: RSI Mean Reversion (15m) ───────────────────────────────────
# RSI экстремум + BB touch + EMA тренд
# Лучший ранее найденный результат: RSI 28/72, PF 1.34 (27 сделок / 3 года)

EMA_1H       = 48    # 48 × 15m = 12 часов
EMA_1H_SLOPE = 12    # наклон за 3 часа
EMA_MACRO    = 480   # 480 × 15m = 120 часов = 5 дней (режим рынка)

BB_PERIOD = 20
BB_STD    = 2.0

RSI_PERIOD = 14
RSI_LOW    = 28
RSI_HIGH   = 72

SL_PCT = 0.020   # 2.0%
TP_PCT = 0.035   # 3.5%

TREND_EXIT_BARS = 15
MAX_HOLD_BARS   = 32
POSITION_PCT    = 0.95
LEVERAGE        = 2

ATR_PERIOD    = 14
BARS_PER_YEAR = 365 * 24 * 4   # 15m баров в году
