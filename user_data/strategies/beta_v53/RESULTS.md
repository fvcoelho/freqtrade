# BetaV53 — Results & Optimization History

## Problem
V53 original was +$124 in bull, +$41 in bear, but **-$252 in ranging** — destroying the total result.
Ranging trades had 81% win rate but 8 trailing stops at -$236 and 4 stop_losses at -$112 were catastrophic.

## Changes Applied (2026-05-22)
1. **entries.py**: `z_entry_multiplier=1.5` for ranging (requires z > 3.15 instead of 2.1 to enter)
2. **exits.py**: Regime-aware exits using CURRENT regime (not entry tag):
   - `ranging_tight_stop`: -5.5% (vs -7% global)
   - `ranging_time_stop`: 180min max hold
   - `ranging_quick_scalp`: take +0.6% profit after 15min
3. **leverage.py**: `ranging_max=2.8` cap (vs 4-6x trending)
4. **v53_config.json**: New `ranging` section with tunable params

## Optimization History (Apr 1 - May 18, $1000 wallet)

| Config | Bull | Bear | Ranging | Total | DD |
|--------|------|------|---------|-------|-----|
| Original | +$124 | +$41 | **-$252** | -$87 | 22% |
| z_mult=1.15, stop=-4% | -$43 | -$12 | -$143 | -$198 | 21% |
| z_mult=1.25, stop=-5.5% | +$20 | -$6 | -$118 | -$104 | 16% |
| **z_mult=1.5, stop=-5.5%** | -$12 | **+$29** | **-$79** | **-$63** | **11%** |

## All Period Results (best config: z_mult=1.5)

| Period | T | Profit | Win% | Bull | Bear | Ranging |
|--------|---|--------|------|------|------|---------|
| Mar 20-Apr 1 | 14 | **+$33** | 86% | 5T +$16 | 4T +$5 | 5T +$12 |
| Apr 1-Apr 25 | 21 | **+$29** | 81% | 13T +$5 | 2T +$13 | 6T +$11 |
| Apr 25-May 18 | 36 | -$89 | 58% | 16T -$17 | 7T +$15 | 13T -$87 |
| Apr 1-May 18 | 57 | -$63 | 67% | 29T -$12 | 9T +$29 | 19T -$79 |
| Mar 20-May 18 | 71 | -$33 | 70% | 34T +$4 | 13T +$34 | 24T -$72 |

## Key Findings

- **Bear is ALWAYS positive** across all periods (+$5 to +$34)
- **Mar 20 to Apr 25 is consistently profitable** (+$33 and +$29)
- **Apr 25 to May 18 ranging market is the killer** (-$87 in ranging alone)
- The strategy works in trending; the late-April ranging shift destroys it
- Check CURRENT regime in exits, not entry tag (regime can change during trade)
- Tag-based exit (first attempt) killed bull trades that entered ranging but turned bull
- `z_entry_multiplier` is the most impactful param — 1.5x reduces ranging trades from 75 to 19

## Architecture
- Dual independent groups: Group A (XRP vs SOL+LINK), Group B (BTC+SOL vs ETH)
- Max 2 concurrent trades (1 per group), per-group cooldown
- Leverage: Warmup 3-5x (streak-based), capped at 2.8x in ranging
- Config: `v53_config.json` (HL), `v53_config_binance.json`, `v53_config_usdt.json`
- Backtest: `config_beta_v53_backtest_5m.json` (5 pairs: BTC/ETH/SOL/XRP/LINK)
