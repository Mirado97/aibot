SYMBOL    = "ETH/USDT:USDT"
TIMEFRAME = "15m"
CAPITAL   = 300.0
DAYS_BACK = 1095

COMMISSION = 0.0002   # maker-ордер OKX futures (0.02%)
SLIPPAGE   = 0.0002

# ──────────────────────────────────────────────────────
# СТРАТЕГИЯ: Smart Money Concepts
# CHoCH (смена структуры) → откат в Order Block → вход
# SL под/над OB (структурный), TP фиксированный
# ──────────────────────────────────────────────────────

# EMA макро-тренд: 48 × 15m = 12 часов
EMA_1H       = 48    # span EMA
EMA_1H_SLOPE = 12    # наклон за 3 часа (12 × 15m)

# Pivot detection
SWING_LEN   = 15   # баров для подтверждения свинг-пивота (15 × 15m = 3.75 ч)
OB_LOOKBACK = 15   # поиск OB в последних N барах до CHoCH

# BB (оставлен как индикатор)
BB_PERIOD = 20
BB_STD    = 2.0

# RSI (оставлен как индикатор)
RSI_PERIOD = 14

# SL/TP
SL_PCT = 0.020   # 2.0% — максимальный SL (структурный SL обычно тiже)
TP_PCT = 0.035   # 3.5%

# Выход по развороту тренда
TREND_EXIT_BARS = 15   # минимум 15 баров (3.75 ч) перед trend exit

MAX_HOLD_BARS = 32     # 8 часов (32 × 15m)
POSITION_PCT  = 0.95
LEVERAGE      = 2

# ATR
ATR_PERIOD = 14
