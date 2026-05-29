# ZAP — ZScore Agent Pipeline Strategy

**Date:** 2026-05-28
**Status:** Approved
**Exchange:** Hyperliquid
**Pairs:** 15-20 crypto pairs

## Overview

4 independent agents in a pipeline architecture, two queues (LONG/SHORT) with ~50+ pre-computed features per pair, FreqAI regression model (LightGBM) that predicts expected return over next N candles, automatic ranking of pairs.

The queues are passive — they organize and score, they don't decide. Each agent has its own execution cycle and responsibility.

## Architecture

```
                        Every 1h/15m
  ┌──────────────┐     ┌──────────────┐
  │ Agent: Regime │     │ Agent: Scanner│
  │ (macro/BTC)   │     │ (indicators)  │
  └──────┬───────┘     └──────┬───────┘
         │                     │
         v                     v
    regime_state         ┌──────────┐
    (bull/bear/range)    │ LONG Q   │ pair -> {score, 50+ features}
         │               ├──────────┤
         │               │ SHORT Q  │ pair -> {score, 50+ features}
         │               └────┬─────┘
         │                    │
         v                    v          Every 5m
  ┌─────────────────────────────────┐
  │       Agent: Entry              │
  │  FreqAI (regression -> ranking) │
  │  Queries queues + regime_state  │
  │  Top-K pairs -> entry           │
  └──────────────┬──────────────────┘
                 │
                 v                     Every 5m
  ┌─────────────────────────────────┐
  │       Agent: Manager            │
  │  Trailing + stoploss + ML exit  │
  │  DCA if model confirms          │
  └─────────────────────────────────┘
```

## Agents

### 1. Scanner Agent (every candle, 5m)

Computes ~46 features per pair across 6 categories. Updates both queues.

Runs in: `populate_indicators()`

### 2. Regime Agent (every candle, uses informative 1h)

Evaluates macro market state: bull/bear/ranging with strength score.

Runs in: `populate_indicators()` via `@informative("1h")`

### 3. Entry Agent (every 5m candle)

Queries FreqAI model with queue features, gets predicted return per pair, ranks them, enters Top-K.

Runs in: `populate_entry_trend()`

### 4. Manager Agent (every 5m candle)

Manages open trades: exits, DCA, trailing, time stops.

Runs in: `custom_exit()`, `custom_stoploss()`, `adjust_trade_position()`

## Pre-computed Features per Pair

### Statistical (~10 features)
- z-score (basket spread)
- half-life of mean reversion
- hurst exponent
- cointegration score (Engle-Granger)
- spread velocity
- spread acceleration
- EWM correlation (vs basket)
- log spread z-score
- cumulative returns z-score
- kalman filtered z-score

### Momentum (~8 features)
- RSI (14)
- MACD (12/26/9) signal + histogram
- ADX (14)
- EMA slopes (8, 21, 55)
- Rate of change (12)
- Stochastic RSI

### Microstructure (~6 features)
- Funding rate (current)
- Funding rate delta (change)
- Open interest delta
- Volume profile (VWAP deviation)
- CVD (cumulative volume delta)
- Volume ratio (current vs avg)

### Cross-pair (~8 features)
- Spread z vs each pair in basket
- Rolling beta (vs BTC)
- Rolling beta (vs ETH)
- Lead-lag score (vs BTC)
- Pair correlation matrix rank
- Relative strength vs basket
- Spread velocity rank
- Mean spread divergence

### Volatility (~8 features)
- ATR (14)
- Bollinger Band width
- Realized volatility (close-close)
- Volume-weighted volatility
- Keltner Channel squeeze flag
- Volatility ratio (short/long)
- Parkinson volatility
- ATR percentile rank

### Macro (~6 features)
- BTC trend direction
- BTC momentum (ROC)
- BTC dominance delta
- Total market volatility index
- BTC ADX
- Altcoin correlation mean

**Total: ~46 base features per pair**
With FreqAI multi-timeframe (5m + 15m + 1h), total ~100+ features per pair.

## FreqAI Configuration

- **Model:** LightGBMRegressor (built-in FreqAI)
- **Target:** % return over next 12 candles (1h forward on 5m)
- **Training:** Rolling window, 720 candles (60h)
- **Retrain:** Every 4 hours
- **Timeframes:** 5m, 15m, 1h
- **Feature selection:** Implicit via LightGBM (tree-based)

## Queue Structure

```python
LONG_QUEUE = {
    "XRP/USDT": {
        "features": {46 pre-computed values},
        "predicted_return": 0.012,   # from FreqAI
        "rank": 1,                    # sorted by predicted_return
        "regime_adjusted_score": 0.012,  # * regime_multiplier
        "last_updated": candle_timestamp,
    },
    ...
}

SHORT_QUEUE = { same structure }
```

## Data Flow

```
populate_indicators()
|
+-- Scanner.update(dataframe, pair)
|   +-- statistical.compute(df)     -> 10 features
|   +-- momentum.compute(df)        -> 8 features
|   +-- microstructure.compute(df)  -> 6 features
|   +-- cross_pair.compute(df, all) -> 8 features
|   +-- volatility.compute(df)      -> 8 features
|   +-- macro.compute(btc_df)       -> 6 features
|
+-- Regime.update(btc_df)
|   -> regime_state = {bull|bear|ranging, strength, btc_mom}
|
+-- Queues.update(pair, features, regime)
    +-- LONG_QUEUE[pair] = {features, predicted_return, rank}
    +-- SHORT_QUEUE[pair] = {features, predicted_return, rank}

populate_entry_trend()
|   +-- Entry.analyze(LONG_QUEUE, SHORT_QUEUE, regime)
|   +-- Model.predict(features) -> predicted_return
|   +-- Rank by predicted_return
|   +-- Top-K -> enter_long / enter_short signal

custom_exit() / custom_stoploss() / adjust_trade_position()
    +-- Manager.check_ml_exit(trade, current_features)
    +-- Manager.check_trailing(trade, profit)
    +-- Manager.check_time_stop(trade, candles)
    +-- Manager.check_dca(trade, predicted_return)
```

## Agent Cycles

| Agent   | Cycle          | Freqtrade Callback                                     |
|---------|----------------|--------------------------------------------------------|
| Scanner | Every 5m       | `populate_indicators()`                                |
| Regime  | Every 5m (1h)  | `populate_indicators()` via `@informative("1h")`       |
| Entry   | Every 5m       | `populate_entry_trend()`                               |
| Manager | Every 5m       | `custom_exit()` + `custom_stoploss()` + `adjust_trade_position()` |

## Manager Agent (Exit Logic)

| Exit Type      | Condition                                        |
|----------------|--------------------------------------------------|
| Safety stoploss| Loss >= -10%                                     |
| ML exit        | predicted_return flips sign (positive -> negative)|
| Trailing stop  | Activates after +2% profit, 0.5% offset          |
| Time stop      | 48 candles (4h) without reaching target           |
| DCA            | Loss > -3% AND model re-confirms (score > 0.008) |

## Configuration

```python
ZAP_CONFIG = {
    "pairs_count": 20,
    "max_open_trades": 6,
    "leverage": {"min": 2, "max": 8},

    "scanner": {
        "zscore_window": 288,
        "half_life_max": 100,
        "correlation_window": 144,
    },

    "regime": {
        "adx_ranging": 18,
        "adx_trending": 25,
        "btc_momentum_window": 48,
    },

    "entry": {
        "top_k": 3,
        "min_predicted_return": 0.005,
        "regime_multipliers": {
            "bull_long": 1.0, "bull_short": 0.3,
            "bear_long": 0.3, "bear_short": 1.0,
            "ranging": 0.5,
        },
    },

    "manager": {
        "stoploss": -0.10,
        "trailing_activate": 0.02,
        "trailing_offset": 0.005,
        "time_stop_candles": 48,
        "dca_threshold": -0.03,
        "dca_min_predicted": 0.008,
    },
}
```

## File Structure

```
user_data/strategies/zap/
├── __init__.py
├── strategy.py          # IStrategy — orchestrates 4 agents
├── config.py            # Constants and params
├── queues.py            # LONG/SHORT queues with pre-computed features
├── agents/
│   ├── __init__.py
│   ├── scanner.py       # Scanner Agent — computes 50+ features per pair
│   ├── regime.py        # Regime Agent — BTC trend, macro state
│   ├── entry.py         # Entry Agent — FreqAI + queues -> decision
│   └── manager.py       # Manager Agent — exits, DCA, trailing
├── features/
│   ├── __init__.py
│   ├── statistical.py   # z-score, half-life, hurst, cointegration
│   ├── momentum.py      # RSI, MACD, ADX, EMA slopes, ROC
│   ├── microstructure.py# funding rate, OI delta, volume profile, CVD
│   ├── cross_pair.py    # spread z between pairs, beta, lead-lag
│   ├── volatility.py    # ATR, BB width, realized vol, Keltner
│   └── macro.py         # BTC trend/momentum, dominance, total vol
└── model/
    ├── __init__.py
    ├── training.py      # Rolling window training, feature selection
    └── prediction.py    # Inference — predicted return per pair
```

## Pairs (Initial 20)

BTC, ETH, SOL, XRP, ADA, DOGE, LINK, SUI, TON, ONDO,
AVAX, ARB, OP, MATIC, DOT, NEAR, ATOM, FTM, INJ, SEI
