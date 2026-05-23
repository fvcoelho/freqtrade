# MicroRevert Strategy — Design Spec

**Date:** 2026-05-23
**Status:** Approved

## Overview

Scalp de mean reversion individual no 5m. Entra com penny stake quando o preco desvia da propria media (z-score individual). Avalia apos 1 candle (5 min) — se nao tem lucro, corta. Se tem, escala com confirmacao de z-delta e busca reversao completa. Inspirado no TwinPennies V4.

## Architecture

```
user_data/strategies/micro_revert/
├── __init__.py
├── strategy.py      # IStrategy principal
├── config.py        # Loader do JSON config
├── zscore.py        # Z-score individual (preco vs EMA + rolling_std)
├── btc_trend.py     # Copy do TwinPennies (filtro BTC chaos/pump/dump)
└── volume.py        # Copy do TwinPennies (filtro volume)
```

Config file: `user_data/strategies/micro_revert_config.json`
Backtest config: `config_micro_revert_backtest_5m.json`

## Z-Score Individual

Calculo simples — desvio do preco em relacao a propria media movel:

```python
ema = close.ewm(span=ema_window).mean()
std = close.rolling(zscore_window).std()
z = (close - ema) / std
```

Parametros iniciais (grid search depois):
- `ema_window`: 30 (moderado, ~2.5h no 5m)
- `zscore_window`: 30 (matching)
- `entry_z`: 2.0

Grid search planejado:
- Conservador: EMA 60, z >= 2.5
- Moderado: EMA 30, z >= 2.0 (default)
- Agressivo: EMA 20, z >= 1.5

## Trade Flow

### Entry
1. Calcula z-score individual do par
2. z <= -entry_z → enter_long (preco abaixo da media)
3. z >= entry_z → enter_short (preco acima da media)
4. Stake tiered pela magnitude do z:
   - |z| < 2.0: $5
   - |z| >= 2.0: $7
   - |z| >= 2.5: $9
   - |z| >= 3.0: $12
5. Filtros: volume OK + BTC nao caotico (pump/dump/high_vol)
6. Direcao: long + short simetrico

### Eval (apos 1 candle = 5 min)
- profit > 0 → winner (candidato a scale)
- profit <= 0 → loser → fecha imediato (loser_close)

### Scaling (winners apenas)
- Escala +$100 quando z-delta confirma reversao (delta >= z_revert_min)
- z_delta calculado: long = z_current - z_entry (z subindo de volta), short = z_entry - z_current
- Maximo 2 scales (max_scale_times=2)
- Precisa profit >= scale_min_profit pra escalar
- Scale progressivo: 2o scale exige z_delta >= z_revert_min * 1.8

### Exit
| Exit | Condicao | Esperado |
|------|----------|----------|
| `mr_winner_revert` | z cruzou de volta pra ≈0 (|z| < exit_z) com profit > 0.3% | Profit engine |
| `mr_time_stop` | trade_age >= max_candles (5 candles = 25 min) | Scaled winners que nao reverteram |
| `mr_loser_close` | Apos eval_candles (1), profit <= 0 | Penny losses, custo aceitavel |
| `mr_safety_stop` | profit < safety_stop (-5%) | Hard stop, emergencia |

## Pairs (expandido)

18 pares com volume razoavel na Hyperliquid:
```
BTC/USDC:USDC, ETH/USDC:USDC, SOL/USDC:USDC, XRP/USDC:USDC,
DOGE/USDC:USDC, SUI/USDC:USDC, ONDO/USDC:USDC, TON/USDC:USDC,
LINK/USDC:USDC, ADA/USDC:USDC, AVAX/USDC:USDC, PEPE/USDC:USDC,
WIF/USDC:USDC, HYPE/USDC:USDC, AAVE/USDC:USDC, OP/USDC:USDC,
ARB/USDC:USDC, SEI/USDC:USDC
```

BTC serve como referencia (btc_trend filter), mas tambem e tradeavel.

## Config JSON

```json
{
    "timeframe": "5m",
    "startup_candle_count": 200,
    "pairs": [
        "BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC", "XRP/USDC:USDC",
        "DOGE/USDC:USDC", "SUI/USDC:USDC", "ONDO/USDC:USDC", "TON/USDC:USDC",
        "LINK/USDC:USDC", "ADA/USDC:USDC", "AVAX/USDC:USDC", "PEPE/USDC:USDC",
        "WIF/USDC:USDC", "HYPE/USDC:USDC", "AAVE/USDC:USDC", "OP/USDC:USDC",
        "ARB/USDC:USDC", "SEI/USDC:USDC"
    ],
    "btc_ref": "BTC/USDC:USDC",
    "zscore": {
        "ema_window": 30,
        "zscore_window": 30,
        "entry_z": 2.0,
        "exit_z": 0.1
    },
    "risk": {
        "stoploss": -0.99
    },
    "btc_trend": {
        "timeframe": "1h",
        "pump_threshold": 3.0,
        "dump_threshold": -3.0,
        "high_vol_threshold": 2.0,
        "vol_ended_threshold": 1.5,
        "mom_period": 4,
        "atr_period": 14,
        "atr_z_window": 72
    },
    "volume": {
        "vol_ma_window": 144,
        "vol_ok_threshold": 1.0
    },
    "twin": {
        "eval_candles": 1,
        "max_positions": 8,
        "initial_leverage": 3,
        "winner_exit_z": 0.1,
        "max_candles": 5,
        "loser_max_candles": 1,
        "safety_stop": -0.05,
        "min_winner_profit": 0.0001,
        "scale_stake": 100.0,
        "max_scale_times": 2,
        "z_revert_min": 0.3,
        "scale_min_profit": 0.0003
    }
}
```

## Key Differences from TwinPennies

| Aspecto | TwinPennies V4 | MicroRevert |
|---------|----------------|-------------|
| Z-score | Basket (par vs grupo) | Individual (par vs propria media) |
| Entry z window | 288 (24h) | 30 (~2.5h) |
| Eval | 2 candles (10 min) | 1 candle (5 min) |
| Max hold | 24-30 candles (2-2.5h) | 5 candles (25 min) |
| Pairs | 8 | 18 |
| confirm_trade_entry | Exige par oposto com z extremo | Nao precisa (individual) |
| Scale trigger | Basket z-delta revert | Individual z-delta revert |

## Backtest Plan

1. Rodar com config default (moderado) no periodo Apr 1 - May 18
2. Grid search: ema_window × entry_z × max_candles
3. Comparar com TwinPennies V4 no mesmo periodo
4. Se funcionar em 5m, migrar pra 1m com dados baixados

## Migration to 1m (futuro)

Quando validado em 5m:
1. Baixar dados 1m via `freqtrade download-data`
2. Ajustar: eval_candles=1 (1 min), max_candles=5 (5 min)
3. Reduzir ema_window e zscore_window proporcionalmente (÷5)
4. Re-otimizar entry_z e scale params
