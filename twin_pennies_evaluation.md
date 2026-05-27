# TwinPennies V4 — Hourly Evaluation Log

Auto-gerado por `scripts/twin_pennies_hourly_eval.py` (cron, horário).
Cada seção = um snapshot. Lê de baixo (mais novo) pra cima.
Para revisar sugestões e ajustar a estratégia, abra o Claude e peça para analisar este arquivo.

---

## 2026-05-23 22:04 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 3 | XRP/USDC:USDC | L | $45.54 | 3x | -0.087→-1.471 | -1.49% | 2.93% | 14c | 0.08 |
| 4 | SUI/USDC:USDC | S | $12.24 | 3x | 0.618→2.207 | 2.61% | 4.95% | 17c | 0.08 |

**Cumulativo (n=3):** PnL $-0.16 | WR 33% (1W/2L) | avg $-0.053 | win $+0.071 | loss $-0.115 | dur 16.8m
**Desde última run (n=3):** PnL $-0.16 | WR 33% (1W/2L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-0.18 (1 trades)
- `SOL/USDC:USDC`: $-0.05 (1 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)

**Exit reasons:**
- `unknown`: 1
- `twin_loser_close`: 1
- `twin_winner_revert`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 33% + PnL $-0.16 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-23 22:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 3 | XRP/USDC:USDC | L | $45.54 | 3x | -0.087→-1.471 | -1.49% | 2.93% | 14c | 0.08 |
| 4 | SUI/USDC:USDC | S | $12.24 | 3x | 0.618→2.207 | 2.61% | 4.95% | 17c | 0.08 |

**Cumulativo (n=3):** PnL $-0.16 | WR 33% (1W/2L) | avg $-0.053 | win $+0.071 | loss $-0.115 | dur 16.8m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-0.18 (1 trades)
- `SOL/USDC:USDC`: $-0.05 (1 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)

**Exit reasons:**
- `unknown`: 1
- `twin_loser_close`: 1
- `twin_winner_revert`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 33% + PnL $-0.16 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-23 23:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 3 | XRP/USDC:USDC | L | $45.54 | 3x | 0.790→-1.471 | -2.20% | 2.93% | 2c | 0.08 |
| 6 | ETH/USDC:USDC | S | $4.94 | 3x | 1.414→1.602 | 0.24% | 0.24% | 28c | 0.08 |

**Cumulativo (n=4):** PnL $+0.56 | WR 50% (2W/2L) | avg $+0.141 | win $+0.397 | loss $-0.115 | dur 40.1m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-0.18 (1 trades)
- `SOL/USDC:USDC`: $-0.05 (1 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `SUI/USDC:USDC`: $+0.72 (1 trades)

**Exit reasons:**
- `twin_winner_revert`: 2
- `unknown`: 1
- `twin_loser_close`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.40) >2× perda média ($-0.12). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.

---

## 2026-05-24 00:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 6 | ETH/USDC:USDC | S | $12.90 | 3x | 0.179→1.602 | -0.37% | 0.30% | 16c | 0.08 |
| 7 | SOL/USDC:USDC | L | $4.85 | 3x | -1.321→-1.384 | 0.32% | 0.37% | 28c | 0.08 |
| 8 | ONDO/USDC:USDC | S | $4.98 | 3x | 1.349→1.856 | 0.12% | 1.15% | 29c | 0.08 |

**Cumulativo (n=5):** PnL $-0.33 | WR 40% (2W/3L) | avg $-0.067 | win $+0.397 | loss $-0.376 | dur 1.0h
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.90 (1 trades)
- `ETH/USDC:USDC`: $-0.18 (1 trades)
- `SOL/USDC:USDC`: $-0.05 (1 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `SUI/USDC:USDC`: $+0.72 (1 trades)

**Exit reasons:**
- `twin_winner_revert`: 2
- `unknown`: 1
- `twin_loser_close`: 1
- `twin_time_stop`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 40% + PnL $-0.33 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-24 01:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 6 | ETH/USDC:USDC | S | $52.94 | 3x | 0.136→1.602 | -0.77% | 0.30% | 4c | 0.08 |

**Cumulativo (n=7):** PnL $-0.10 | WR 57% (4W/3L) | avg $-0.014 | win $+0.258 | loss $-0.376 | dur 51.8m
**Desde última run (n=2):** PnL $+0.24 | WR 100% (2W/0L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.90 (1 trades)
- `ETH/USDC:USDC`: $-0.18 (1 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.72 (1 trades)

**Exit reasons:**
- `twin_winner_revert`: 4
- `unknown`: 1
- `twin_loser_close`: 1
- `twin_time_stop`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ 4× winner_revert mas avg_win $0.26 pequeno. `winner_exit_z` (0.08) pode estar saindo cedo demais — testar 0.0 ou negativo.

---

## 2026-05-24 02:05 UTC

**Open trades:** 0

**Cumulativo (n=9):** PnL $-0.53 | WR 44% (4W/5L) | avg $-0.059 | win $+0.258 | loss $-0.313 | dur 58.7m
**Desde última run (n=1):** PnL $-0.02 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.72 (1 trades)

**Exit reasons:**
- `twin_winner_revert`: 4
- `twin_loser_close`: 2
- `twin_time_stop`: 2
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 44% + PnL $-0.53 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-24 03:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 10 | SUI/USDC:USDC | L | $4.98 | 3x | -0.720→2.087 | 1.41% | 1.69% | 24c | 0.08 |

**Cumulativo (n=9):** PnL $-0.53 | WR 44% (4W/5L) | avg $-0.059 | win $+0.258 | loss $-0.313 | dur 58.7m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.72 (1 trades)

**Exit reasons:**
- `twin_winner_revert`: 4
- `twin_loser_close`: 2
- `twin_time_stop`: 2
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 44% + PnL $-0.53 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-24 04:05 UTC

**Open trades:** 0

**Cumulativo (n=10):** PnL $-0.40 | WR 50% (5W/5L) | avg $-0.040 | win $+0.233 | loss $-0.313 | dur 56.9m
**Desde última run (n=1):** PnL $+0.13 | WR 100% (1W/0L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.86 (2 trades)

**Exit reasons:**
- `twin_winner_revert`: 5
- `twin_loser_close`: 2
- `twin_time_stop`: 2
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ✅ Sem alertas heurísticos — comportamento dentro do esperado.

---

## 2026-05-24 05:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 11 | TON/USDC:USDC | L | $4.97 | 3x | -1.591→-1.870 | -0.25% | 0.16% | 28c | 0.08 |

**Cumulativo (n=10):** PnL $-0.40 | WR 50% (5W/5L) | avg $-0.040 | win $+0.233 | loss $-0.313 | dur 56.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $+0.07 (1 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.86 (2 trades)

**Exit reasons:**
- `twin_winner_revert`: 5
- `twin_loser_close`: 2
- `twin_time_stop`: 2
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ✅ Sem alertas heurísticos — comportamento dentro do esperado.

---

## 2026-05-24 06:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 13 | SUI/USDC:USDC | L | $57.42 | 3x | -1.283→-1.453 | 0.65% | 0.74% | 22c | 0.08 |

**Cumulativo (n=11):** PnL $-0.51 | WR 45% (5W/6L) | avg $-0.046 | win $+0.233 | loss $-0.279 | dur 54.0m
**Desde última run (n=1):** PnL $-0.11 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $-0.04 (2 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.86 (2 trades)

**Exit reasons:**
- `twin_winner_revert`: 5
- `twin_loser_close`: 3
- `twin_time_stop`: 2
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 45% + PnL $-0.51 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-24 07:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 13 | SUI/USDC:USDC | L | $58.45 | 3x | 0.046→-1.453 | -0.08% | 2.90% | 10c | 0.08 |

**Cumulativo (n=11):** PnL $-0.51 | WR 45% (5W/6L) | avg $-0.046 | win $+0.233 | loss $-0.279 | dur 54.0m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $-0.04 (2 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.86 (2 trades)

**Exit reasons:**
- `twin_winner_revert`: 5
- `twin_loser_close`: 3
- `twin_time_stop`: 2
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 45% + PnL $-0.51 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-24 08:05 UTC

**Open trades:** 0

**Cumulativo (n=12):** PnL $-0.62 | WR 42% (5W/7L) | avg $-0.051 | win $+0.233 | loss $-0.255 | dur 57.8m
**Desde última run (n=1):** PnL $-0.11 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `TON/USDC:USDC`: $-0.04 (2 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.75 (3 trades)

**Exit reasons:**
- `twin_winner_revert`: 5
- `twin_loser_close`: 3
- `twin_time_stop`: 3
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 42% + PnL $-0.62 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.

---

## 2026-05-24 09:05 UTC

**Open trades:** 0

**Cumulativo (n=13):** PnL $-0.70 | WR 38% (5W/8L) | avg $-0.054 | win $+0.233 | loss $-0.234 | dur 54.8m
**Desde última run (n=1):** PnL $-0.09 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `TON/USDC:USDC`: $-0.13 (3 trades)
- `SOL/USDC:USDC`: $-0.04 (2 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.75 (3 trades)

**Exit reasons:**
- `twin_winner_revert`: 5
- `twin_loser_close`: 4
- `twin_time_stop`: 3
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 38% + PnL $-0.70 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: TON/USDC:USDC ($-0.13/3). Avaliar remover do `basket.pairs`.

---

## 2026-05-24 10:05 UTC

**Open trades:** 0

**Cumulativo (n=14):** PnL $-0.47 | WR 43% (6W/8L) | avg $-0.034 | win $+0.233 | loss $-0.234 | dur 53.5m
**Desde última run (n=1):** PnL $+0.23 | WR 100% (1W/0L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `TON/USDC:USDC`: $-0.13 (3 trades)
- `SOL/USDC:USDC`: $+0.20 (3 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.75 (3 trades)

**Exit reasons:**
- `twin_winner_revert`: 6
- `twin_loser_close`: 4
- `twin_time_stop`: 3
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 43% + PnL $-0.47 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: TON/USDC:USDC ($-0.13/3). Avaliar remover do `basket.pairs`.

---

## 2026-05-24 11:05 UTC

**Open trades:** 0

**Cumulativo (n=14):** PnL $-0.47 | WR 43% (6W/8L) | avg $-0.034 | win $+0.233 | loss $-0.234 | dur 53.5m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `TON/USDC:USDC`: $-0.13 (3 trades)
- `SOL/USDC:USDC`: $+0.20 (3 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.75 (3 trades)

**Exit reasons:**
- `twin_winner_revert`: 6
- `twin_loser_close`: 4
- `twin_time_stop`: 3
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 43% + PnL $-0.47 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: TON/USDC:USDC ($-0.13/3). Avaliar remover do `basket.pairs`.

---

## 2026-05-24 12:05 UTC

**Open trades:** 0

**Cumulativo (n=14):** PnL $-0.47 | WR 43% (6W/8L) | avg $-0.034 | win $+0.233 | loss $-0.234 | dur 53.5m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.92 (2 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `TON/USDC:USDC`: $-0.13 (3 trades)
- `SOL/USDC:USDC`: $+0.20 (3 trades)
- `ONDO/USDC:USDC`: $+0.22 (1 trades)
- `SUI/USDC:USDC`: $+0.75 (3 trades)

**Exit reasons:**
- `twin_winner_revert`: 6
- `twin_loser_close`: 4
- `twin_time_stop`: 3
- `unknown`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 43% + PnL $-0.47 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: TON/USDC:USDC ($-0.13/3). Avaliar remover do `basket.pairs`.

---

## 2026-05-24 13:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 20 | TON/USDC:USDC | L | $4.96 | 3x | -1.844→-1.844 | -0.32% | 0.00% | 30c | 0.08 |

**Cumulativo (n=18):** PnL $-0.74 | WR 39% (7W/11L) | avg $-0.041 | win $+0.200 | loss $-0.195 | dur 44.8m
**Desde última run (n=4):** PnL $-0.27 | WR 25% (1W/3L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.93 (3 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `TON/USDC:USDC`: $-0.13 (3 trades)
- `DOGE/USDC:USDC`: $-0.03 (1 trades)
- `ONDO/USDC:USDC`: $+0.00 (2 trades)
- `SOL/USDC:USDC`: $+0.20 (3 trades)
- `SUI/USDC:USDC`: $+0.75 (4 trades)

**Exit reasons:**
- `twin_loser_close`: 7
- `twin_winner_revert`: 6
- `twin_time_stop`: 3
- `unknown`: 1
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 39% + PnL $-0.74 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-0.93/3), TON/USDC:USDC ($-0.13/3). Avaliar remover do `basket.pairs`.

---

## 2026-05-24 14:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 22 | SUI/USDC:USDC | L | $4.99 | 3x | -1.522→-1.361 | 0.20% | 0.17% | 29c | 0.08 |

**Cumulativo (n=20):** PnL $-0.61 | WR 40% (8W/12L) | avg $-0.030 | win $+0.194 | loss $-0.180 | dur 42.3m
**Desde última run (n=2):** PnL $+0.13 | WR 50% (1W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-0.93 (3 trades)
- `ETH/USDC:USDC`: $-0.59 (2 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.03 (1 trades)
- `ONDO/USDC:USDC`: $+0.15 (3 trades)
- `SOL/USDC:USDC`: $+0.20 (3 trades)
- `SUI/USDC:USDC`: $+0.75 (4 trades)

**Exit reasons:**
- `twin_loser_close`: 9
- `twin_winner_revert`: 6
- `twin_time_stop`: 3
- `unknown`: 1
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 40% + PnL $-0.61 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-0.93/3), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.

---

## 2026-05-24 15:05 UTC

**Open trades:** 0

**Cumulativo (n=25):** PnL $-0.75 | WR 36% (9W/16L) | avg $-0.030 | win $+0.173 | loss $-0.144 | dur 37.1m
**Desde última run (n=5):** PnL $-0.14 | WR 20% (1W/4L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.61 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `ONDO/USDC:USDC`: $+0.15 (3 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.75 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 14
- `twin_winner_revert`: 6
- `twin_time_stop`: 3
- `unknown`: 1
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 36% + PnL $-0.75 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.61/3), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 14× `twin_loser_close` vs 6× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 16:05 UTC

**Open trades:** 0

**Cumulativo (n=27):** PnL $-0.75 | WR 37% (10W/17L) | avg $-0.028 | win $+0.157 | loss $-0.136 | dur 35.4m
**Desde última run (n=2):** PnL $-0.00 | WR 50% (1W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.63 (4 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `ONDO/USDC:USDC`: $+0.16 (4 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.75 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 16
- `twin_winner_revert`: 6
- `twin_time_stop`: 3
- `unknown`: 1
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 37% + PnL $-0.75 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.63/4), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 16× `twin_loser_close` vs 6× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 17:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 29 | ETH/USDC:USDC | L | $4.98 | 3x | -1.339→-1.339 | 0.17% | 0.07% | 30c | 0.08 |
| 30 | SUI/USDC:USDC | L | $4.98 | 3x | -1.243→-1.243 | 0.43% | 0.14% | 30c | 0.08 |

**Cumulativo (n=27):** PnL $-0.75 | WR 37% (10W/17L) | avg $-0.028 | win $+0.157 | loss $-0.136 | dur 35.4m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.63 (4 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `ONDO/USDC:USDC`: $+0.16 (4 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.75 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 16
- `twin_winner_revert`: 6
- `twin_time_stop`: 3
- `unknown`: 1
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 37% + PnL $-0.75 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.63/4), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 16× `twin_loser_close` vs 6× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 18:05 UTC

**Open trades:** 0

**Cumulativo (n=31):** PnL $-0.83 | WR 32% (10W/21L) | avg $-0.027 | win $+0.157 | loss $-0.114 | dur 33.2m
**Desde última run (n=4):** PnL $-0.08 | WR 0% (0W/4L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.67 (6 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `ONDO/USDC:USDC`: $+0.15 (5 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.73 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 6
- `unknown`: 3
- `twin_time_stop`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 32% + PnL $-0.83 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.67/6), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 6× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 19:05 UTC

**Open trades:** 0

**Cumulativo (n=31):** PnL $-0.83 | WR 32% (10W/21L) | avg $-0.027 | win $+0.157 | loss $-0.114 | dur 33.2m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.67 (6 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `ONDO/USDC:USDC`: $+0.15 (5 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.73 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 6
- `unknown`: 3
- `twin_time_stop`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 32% + PnL $-0.83 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.67/6), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 6× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 20:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 33 | ONDO/USDC:USDC | L | $57.20 | 3x | -1.098→-1.324 | -2.07% | 1.81% | 24c | 0.08 |

**Cumulativo (n=31):** PnL $-0.83 | WR 32% (10W/21L) | avg $-0.027 | win $+0.157 | loss $-0.114 | dur 33.2m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.67 (6 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `ONDO/USDC:USDC`: $+0.15 (5 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.73 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 6
- `unknown`: 3
- `twin_time_stop`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 32% + PnL $-0.83 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.67/6), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 6× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 21:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 34 | SOL/USDC:USDC | L | $45.45 | 3x | -0.642→-1.623 | -0.23% | 0.25% | 28c | 0.08 |
| 35 | SUI/USDC:USDC | L | $11.98 | 3x | -1.667→-3.327 | 0.44% | 0.74% | 28c | 0.08 |

**Cumulativo (n=32):** PnL $-0.47 | WR 34% (11W/21L) | avg $-0.015 | win $+0.176 | loss $-0.114 | dur 34.1m
**Desde última run (n=1):** PnL $+0.36 | WR 100% (1W/0L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.67 (6 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SUI/USDC:USDC`: $+0.73 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 7
- `unknown`: 3
- `twin_time_stop`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 34% + PnL $-0.47 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.67/6), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 7× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 22:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 34 | SOL/USDC:USDC | L | $45.45 | 3x | 0.305→-1.623 | -2.11% | 0.60% | 16c | 0.08 |
| 36 | ETH/USDC:USDC | S | $4.99 | 3x | 0.691→2.392 | -0.35% | 1.87% | 25c | 0.08 |
| 37 | DOGE/USDC:USDC | S | $4.98 | 3x | 0.438→1.984 | -1.00% | 0.75% | 25c | 0.08 |

**Cumulativo (n=33):** PnL $-0.91 | WR 33% (11W/22L) | avg $-0.028 | win $+0.176 | loss $-0.129 | dur 34.4m
**Desde última run (n=1):** PnL $-0.44 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.67 (6 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `SOL/USDC:USDC`: $+0.20 (4 trades)
- `SUI/USDC:USDC`: $+0.29 (7 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 7
- `unknown`: 3
- `twin_time_stop`: 3
- `twin_max_loss`: 1
- `trailing_stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 33% + PnL $-0.91 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.67/6), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 7× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-24 23:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 37 | DOGE/USDC:USDC | S | $4.98 | 3x | 0.109→1.984 | -3.08% | 0.75% | 13c | 0.08 |

**Cumulativo (n=35):** PnL $-0.44 | WR 34% (12W/23L) | avg $-0.013 | win $+0.213 | loss $-0.130 | dur 36.0m
**Desde última run (n=1):** PnL $-0.15 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.82 (7 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `DOGE/USDC:USDC`: $-0.08 (2 trades)
- `SUI/USDC:USDC`: $+0.29 (7 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.82 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 2
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 34% + PnL $-0.44 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.82/7), TON/USDC:USDC ($-0.15/4). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 00:05 UTC

**Open trades:** 0

**Cumulativo (n=36):** PnL $-0.65 | WR 33% (12W/24L) | avg $-0.018 | win $+0.213 | loss $-0.133 | dur 38.2m
**Desde última run (n=1):** PnL $-0.21 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.82 (7 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.29 (7 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.82 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 33% + PnL $-0.65 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.82/7), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 01:05 UTC

**Open trades:** 0

**Cumulativo (n=36):** PnL $-0.65 | WR 33% (12W/24L) | avg $-0.018 | win $+0.213 | loss $-0.133 | dur 38.2m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.82 (7 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.29 (7 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.82 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 33% + PnL $-0.65 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.82/7), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 02:05 UTC

**Open trades:** 0

**Cumulativo (n=36):** PnL $-0.65 | WR 33% (12W/24L) | avg $-0.018 | win $+0.213 | loss $-0.133 | dur 38.2m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.82 (7 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.29 (7 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.82 (5 trades)

**Exit reasons:**
- `twin_loser_close`: 18
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 33% + PnL $-0.65 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.82/7), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 18× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 03:05 UTC

**Open trades:** 0

**Cumulativo (n=38):** PnL $-0.77 | WR 32% (12W/26L) | avg $-0.020 | win $+0.213 | loss $-0.128 | dur 37.1m
**Desde última run (n=2):** PnL $-0.12 | WR 0% (0W/2L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.88 (8 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.29 (7 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.76 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 20
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 32% + PnL $-0.77 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.88/8), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 20× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 04:05 UTC

**Open trades:** 0

**Cumulativo (n=39):** PnL $-0.79 | WR 31% (12W/27L) | avg $-0.020 | win $+0.213 | loss $-0.124 | dur 36.5m
**Desde última run (n=1):** PnL $-0.02 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.88 (8 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.27 (8 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.76 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 21
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.79 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.88/8), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 21× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 05:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 41 | ONDO/USDC:USDC | L | $57.22 | 3x | -0.090→-1.338 | 3.31% | 3.71% | 21c | 0.08 |

**Cumulativo (n=39):** PnL $-0.79 | WR 31% (12W/27L) | avg $-0.020 | win $+0.213 | loss $-0.124 | dur 36.5m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.88 (8 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.27 (8 trades)
- `ONDO/USDC:USDC`: $+0.51 (6 trades)
- `SOL/USDC:USDC`: $+0.76 (6 trades)

**Exit reasons:**
- `twin_loser_close`: 21
- `twin_winner_revert`: 8
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.79 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.88/8), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 21× `twin_loser_close` vs 8× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 06:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 43 | ETH/USDC:USDC | L | $6.96 | 3x | -1.321→-2.298 | -0.17% | 0.00% | 28c | 0.08 |
| 44 | SOL/USDC:USDC | L | $4.87 | 3x | -0.590→-1.776 | -0.25% | 0.00% | 28c | 0.08 |
| 45 | XRP/USDC:USDC | L | $6.80 | 3x | -1.216→-2.170 | -0.35% | 0.00% | 28c | 0.08 |

**Cumulativo (n=41):** PnL $+2.00 | WR 32% (13W/28L) | avg $+0.049 | win $+0.417 | loss $-0.122 | dur 37.2m
**Desde última run (n=2):** PnL $+2.79 | WR 50% (1W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.00 (4 trades)
- `ETH/USDC:USDC`: $-0.88 (8 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.19 (9 trades)
- `SOL/USDC:USDC`: $+0.76 (6 trades)
- `ONDO/USDC:USDC`: $+3.38 (7 trades)

**Exit reasons:**
- `twin_loser_close`: 22
- `twin_winner_revert`: 9
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.42) >2× perda média ($-0.12). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.00/4), ETH/USDC:USDC ($-0.88/8), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 22× `twin_loser_close` vs 9× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 07:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 46 | SUI/USDC:USDC | S | $4.98 | 3x | 1.017→1.212 | 0.14% | 2.87% | 19c | 0.08 |

**Cumulativo (n=44):** PnL $+1.91 | WR 30% (13W/31L) | avg $+0.044 | win $+0.417 | loss $-0.113 | dur 35.8m
**Desde última run (n=3):** PnL $-0.09 | WR 0% (0W/3L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.04 (5 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.19 (9 trades)
- `SOL/USDC:USDC`: $+0.74 (7 trades)
- `ONDO/USDC:USDC`: $+3.38 (7 trades)

**Exit reasons:**
- `twin_loser_close`: 25
- `twin_winner_revert`: 9
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.42) >2× perda média ($-0.11). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.04/5), ETH/USDC:USDC ($-0.91/9), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 25× `twin_loser_close` vs 9× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 08:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 46 | SUI/USDC:USDC | S | $54.90 | 3x | -0.533→1.212 | -1.07% | 2.87% | 7c | 0.08 |
| 47 | ONDO/USDC:USDC | S | $4.88 | 3x | 0.717→1.449 | 0.87% | 0.96% | 28c | 0.08 |

**Cumulativo (n=44):** PnL $+1.91 | WR 30% (13W/31L) | avg $+0.044 | win $+0.417 | loss $-0.113 | dur 35.8m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.04 (5 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SUI/USDC:USDC`: $+0.19 (9 trades)
- `SOL/USDC:USDC`: $+0.74 (7 trades)
- `ONDO/USDC:USDC`: $+3.38 (7 trades)

**Exit reasons:**
- `twin_loser_close`: 25
- `twin_winner_revert`: 9
- `unknown`: 3
- `twin_time_stop`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.42) >2× perda média ($-0.11). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.04/5), ETH/USDC:USDC ($-0.91/9), DOGE/USDC:USDC ($-0.29/3). Avaliar remover do `basket.pairs`.
- ⚠️ 25× `twin_loser_close` vs 9× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 09:05 UTC

**Open trades:** 0

**Cumulativo (n=46):** PnL $+1.42 | WR 30% (14W/32L) | avg $+0.031 | win $+0.395 | loss $-0.128 | dur 36.8m
**Desde última run (n=2):** PnL $-0.49 | WR 50% (1W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.04 (5 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.40 (10 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SOL/USDC:USDC`: $+0.74 (7 trades)
- `ONDO/USDC:USDC`: $+3.49 (8 trades)

**Exit reasons:**
- `twin_loser_close`: 25
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `unknown`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.13). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.04/5), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.40/10). Avaliar remover do `basket.pairs`.
- ⚠️ 25× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 10:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 50 | XRP/USDC:USDC | S | $4.99 | 3x | 1.383→1.383 | -0.11% | 0.00% | 30c | 0.08 |
| 51 | DOGE/USDC:USDC | S | $5.00 | 3x | -0.096→1.984 | -3.94% | 0.75% | 7c | 0.08 |

**Cumulativo (n=48):** PnL $+1.42 | WR 31% (15W/33L) | avg $+0.030 | win $+0.369 | loss $-0.125 | dur 35.9m
**Desde última run (n=2):** PnL $-0.01 | WR 50% (1W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (6 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.40 (10 trades)
- `DOGE/USDC:USDC`: $-0.29 (3 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+3.49 (8 trades)

**Exit reasons:**
- `twin_loser_close`: 27
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `unknown`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.37) >2× perda média ($-0.12). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/6), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.40/10). Avaliar remover do `basket.pairs`.
- ⚠️ 27× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 11:05 UTC

**Open trades:** 0

**Cumulativo (n=51):** PnL $+1.38 | WR 31% (16W/35L) | avg $+0.027 | win $+0.346 | loss $-0.119 | dur 34.6m
**Desde última run (n=3):** PnL $-0.04 | WR 33% (1W/2L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (7 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.42 (11 trades)
- `DOGE/USDC:USDC`: $-0.32 (4 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+3.49 (8 trades)

**Exit reasons:**
- `twin_loser_close`: 30
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `unknown`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.35) >2× perda média ($-0.12). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/7), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.42/11). Avaliar remover do `basket.pairs`.
- ⚠️ 30× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 12:05 UTC

**Open trades:** 0

**Cumulativo (n=51):** PnL $+1.38 | WR 31% (16W/35L) | avg $+0.027 | win $+0.346 | loss $-0.119 | dur 34.6m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (7 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.42 (11 trades)
- `DOGE/USDC:USDC`: $-0.32 (4 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+3.49 (8 trades)

**Exit reasons:**
- `twin_loser_close`: 30
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `unknown`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 3
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.35) >2× perda média ($-0.12). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/7), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.42/11). Avaliar remover do `basket.pairs`.
- ⚠️ 30× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 13:05 UTC

**Open trades:** 0

**Cumulativo (n=51):** PnL $+1.38 | WR 31% (16W/35L) | avg $+0.027 | win $+0.346 | loss $-0.119 | dur 34.6m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (7 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.42 (11 trades)
- `DOGE/USDC:USDC`: $-0.32 (4 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+3.49 (8 trades)

**Exit reasons:**
- `twin_loser_close`: 30
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `unknown`: 3
- `trailing_stop_loss`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.35) >2× perda média ($-0.12). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/7), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.42/11). Avaliar remover do `basket.pairs`.
- ⚠️ 30× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 14:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 54 | TON/USDC:USDC | S | $6.98 | 3x | 2.367→2.424 | -2.50% | 0.04% | 29c | 0.08 |
| 55 | DOGE/USDC:USDC | L | $5.00 | 3x | 1.136→1.535 | -0.50% | 0.09% | 28c | 0.08 |
| 56 | ONDO/USDC:USDC | S | $4.86 | 3x | 1.573→1.573 | 0.06% | 0.22% | 30c | 0.08 |

**Cumulativo (n=52):** PnL $-1.33 | WR 31% (16W/36L) | avg $-0.026 | win $+0.346 | loss $-0.191 | dur 34.9m
**Desde última run (n=1):** PnL $-2.71 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (7 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.42 (11 trades)
- `DOGE/USDC:USDC`: $-0.32 (4 trades)
- `TON/USDC:USDC`: $-0.15 (4 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+0.77 (9 trades)

**Exit reasons:**
- `twin_loser_close`: 30
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `trailing_stop_loss`: 4
- `unknown`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-1.33 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/7), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.42/11). Avaliar remover do `basket.pairs`.
- ⚠️ 30× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 15:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 57 | SOL/USDC:USDC | L | $41.41 | 3x | -1.351→-1.552 | 0.15% | 0.58% | 21c | 0.08 |
| 58 | DOGE/USDC:USDC | L | $4.98 | 3x | -1.373→-1.634 | 0.55% | 0.67% | 21c | 0.08 |
| 60 | XRP/USDC:USDC | L | $4.99 | 3x | -1.403→-1.381 | 0.11% | 0.24% | 22c | 0.08 |

**Cumulativo (n=55):** PnL $-1.42 | WR 31% (17W/38L) | avg $-0.026 | win $+0.327 | loss $-0.184 | dur 34.0m
**Desde última run (n=3):** PnL $-0.09 | WR 33% (1W/2L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (7 trades)
- `ETH/USDC:USDC`: $-0.91 (9 trades)
- `SUI/USDC:USDC`: $-0.42 (12 trades)
- `DOGE/USDC:USDC`: $-0.32 (4 trades)
- `TON/USDC:USDC`: $-0.26 (5 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+0.80 (10 trades)

**Exit reasons:**
- `twin_loser_close`: 33
- `twin_winner_revert`: 10
- `twin_time_stop`: 4
- `trailing_stop_loss`: 4
- `unknown`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-1.42 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/7), ETH/USDC:USDC ($-0.91/9), SUI/USDC:USDC ($-0.42/12). Avaliar remover do `basket.pairs`.
- ⚠️ 33× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 16:05 UTC

**Open trades:** 4

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 57 | SOL/USDC:USDC | L | $41.41 | 3x | -1.527→-1.552 | -0.23% | 0.61% | 9c | 0.08 |
| 58 | DOGE/USDC:USDC | L | $4.98 | 3x | -1.563→-1.634 | -0.18% | 1.39% | 9c | 0.08 |
| 60 | XRP/USDC:USDC | L | $4.99 | 3x | -1.504→-1.381 | -0.51% | 0.77% | 10c | 0.08 |
| 64 | SUI/USDC:USDC | L | $5.00 | 3x | -1.897→-1.892 | -0.26% | 0.06% | 28c | 0.08 |

**Cumulativo (n=58):** PnL $-1.62 | WR 31% (18W/40L) | avg $-0.028 | win $+0.310 | loss $-0.180 | dur 33.0m
**Desde última run (n=3):** PnL $-0.21 | WR 33% (1W/2L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.05 (7 trades)
- `ETH/USDC:USDC`: $-0.94 (10 trades)
- `TON/USDC:USDC`: $-0.45 (6 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.32 (4 trades)
- `SOL/USDC:USDC`: $+0.75 (8 trades)
- `ONDO/USDC:USDC`: $+0.80 (10 trades)

**Exit reasons:**
- `twin_loser_close`: 35
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 5
- `twin_time_stop`: 4
- `unknown`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-1.62 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.05/7), ETH/USDC:USDC ($-0.94/10), TON/USDC:USDC ($-0.45/6). Avaliar remover do `basket.pairs`.
- ⚠️ 35× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 17:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 66 | ETH/USDC:USDC | L | $4.99 | 3x | -1.108→-1.425 | -0.02% | 0.08% | 28c | 0.08 |
| 67 | SOL/USDC:USDC | L | $4.89 | 3x | -1.324→-1.498 | -0.52% | 0.00% | 28c | 0.08 |

**Cumulativo (n=63):** PnL $-2.22 | WR 32% (20W/43L) | avg $-0.035 | win $+0.282 | loss $-0.183 | dur 37.9m
**Desde última run (n=2):** PnL $-0.37 | WR 0% (0W/2L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.03 (8 trades)
- `ETH/USDC:USDC`: $-0.94 (10 trades)
- `TON/USDC:USDC`: $-0.69 (7 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.28 (5 trades)
- `SOL/USDC:USDC`: $+0.46 (9 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 36
- `twin_winner_revert`: 10
- `twin_time_stop`: 7
- `trailing_stop_loss`: 6
- `unknown`: 3
- `twin_max_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 32% + PnL $-2.22 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.03/8), ETH/USDC:USDC ($-0.94/10), TON/USDC:USDC ($-0.69/7). Avaliar remover do `basket.pairs`.
- ⚠️ 36× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 18:05 UTC

**Open trades:** 0

**Cumulativo (n=70):** PnL $-0.97 | WR 31% (22W/48L) | avg $-0.014 | win $+0.338 | loss $-0.175 | dur 35.8m
**Desde última run (n=7):** PnL $+1.25 | WR 29% (2W/5L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.02 (9 trades)
- `ETH/USDC:USDC`: $-0.96 (11 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.31 (6 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.62 (10 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 40
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 2

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.97 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.02/9), ETH/USDC:USDC ($-0.96/11), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 40× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 19:05 UTC

**Open trades:** 0

**Cumulativo (n=70):** PnL $-0.97 | WR 31% (22W/48L) | avg $-0.014 | win $+0.338 | loss $-0.175 | dur 35.8m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.02 (9 trades)
- `ETH/USDC:USDC`: $-0.96 (11 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.31 (6 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.62 (10 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 40
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 2

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.97 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.02/9), ETH/USDC:USDC ($-0.96/11), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 40× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 20:05 UTC

**Open trades:** 0

**Cumulativo (n=70):** PnL $-0.97 | WR 31% (22W/48L) | avg $-0.014 | win $+0.338 | loss $-0.175 | dur 35.8m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.02 (9 trades)
- `ETH/USDC:USDC`: $-0.96 (11 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.31 (6 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.62 (10 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 40
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 2

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 4
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.97 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.02/9), ETH/USDC:USDC ($-0.96/11), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 40× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 21:05 UTC

**Open trades:** 0

**Cumulativo (n=70):** PnL $-0.97 | WR 31% (22W/48L) | avg $-0.014 | win $+0.338 | loss $-0.175 | dur 35.8m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.02 (9 trades)
- `ETH/USDC:USDC`: $-0.96 (11 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.31 (6 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.62 (10 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 40
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 2

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 480
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 50
- `twin.loser_max_candles` = 7
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.97 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.02/9), ETH/USDC:USDC ($-0.96/11), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 40× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 22:05 UTC

**Open trades:** 0

**Cumulativo (n=70):** PnL $-0.97 | WR 31% (22W/48L) | avg $-0.014 | win $+0.338 | loss $-0.175 | dur 35.8m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.02 (9 trades)
- `ETH/USDC:USDC`: $-0.96 (11 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.31 (6 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.62 (10 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 40
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 2

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 480
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 50
- `twin.loser_max_candles` = 7
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-0.97 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.02/9), ETH/USDC:USDC ($-0.96/11), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 40× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-25 23:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 74 | ETH/USDC:USDC | S | $6.95 | 3x | 1.171→2.243 | -0.07% | 0.48% | 44c | 0.08 |
| 75 | XRP/USDC:USDC | S | $4.94 | 3x | 0.580→1.266 | -0.37% | 0.07% | 44c | 0.08 |
| 76 | DOGE/USDC:USDC | S | $4.99 | 3x | 0.006→1.921 | 0.18% | 0.48% | 44c | 0.08 |

**Cumulativo (n=71):** PnL $-1.12 | WR 31% (22W/49L) | avg $-0.016 | win $+0.338 | loss $-0.175 | dur 35.8m
**Desde última run (n=1):** PnL $-0.15 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.02 (9 trades)
- `ETH/USDC:USDC`: $-0.96 (11 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.31 (6 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)
- `ONDO/USDC:USDC`: $+0.67 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 41
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 2

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 480
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 50
- `twin.loser_max_candles` = 7
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 31% + PnL $-1.12 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.02/9), ETH/USDC:USDC ($-0.96/11), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 41× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 00:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 78 | ETH/USDC:USDC | S | $6.96 | 3x | 1.541→2.032 | -0.47% | 0.00% | 45c | 0.08 |
| 79 | ONDO/USDC:USDC | L | $4.88 | 3x | -1.377→-1.907 | -1.89% | 0.00% | 46c | 0.08 |

**Cumulativo (n=75):** PnL $-1.49 | WR 29% (22W/53L) | avg $-0.020 | win $+0.338 | loss $-0.168 | dur 35.3m
**Desde última run (n=4):** PnL $-0.37 | WR 0% (0W/4L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.06 (10 trades)
- `ETH/USDC:USDC`: $-0.98 (12 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.33 (7 trades)
- `ONDO/USDC:USDC`: $+0.38 (12 trades)
- `SOL/USDC:USDC`: $+0.44 (10 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 44
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `unknown`: 3
- `twin_max_loss`: 3

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 480
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 50
- `twin.loser_max_candles` = 7
- `twin.safety_stop` = -0.05
- `twin.initial_leverage` = 3
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 29% + PnL $-1.49 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ℹ️ Ganho médio ($0.34) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.06/10), ETH/USDC:USDC ($-0.98/12), SUI/USDC:USDC ($-0.41/13). Avaliar remover do `basket.pairs`.
- ⚠️ 44× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 01:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 80 | XRP/USDC:USDC | S | $40.74 | 3x | 0.825→1.246 | 0.63% | 1.19% | 20c | 0.08 |
| 81 | DOGE/USDC:USDC | S | $4.99 | 3x | 0.784→1.102 | 2.63% | 3.01% | 20c | 0.08 |

**Cumulativo (n=80):** PnL $-2.37 | WR 28% (22W/58L) | avg $-0.030 | win $+0.338 | loss $-0.169 | dur 34.5m
**Desde última run (n=5):** PnL $-0.88 | WR 0% (0W/5L)

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.06 (10 trades)
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.33 (7 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.0833
- `twin.initial_leverage` = 5
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 28% + PnL $-2.37 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.06/10), ETH/USDC:USDC ($-1.00/13), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 02:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 80 | XRP/USDC:USDC | S | $40.74 | 3x | 0.703→1.077 | 0.84% | 1.28% | 8c | 0.08 |
| 81 | DOGE/USDC:USDC | S | $14.91 | 3x | 0.211→0.748 | 1.61% | 2.17% | 8c | 0.08 |

**Cumulativo (n=80):** PnL $-2.37 | WR 28% (22W/58L) | avg $-0.030 | win $+0.338 | loss $-0.169 | dur 34.5m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `XRP/USDC:USDC`: $-1.06 (10 trades)
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.33 (7 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `trailing_stop_loss`: 8
- `twin_time_stop`: 7
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 28% + PnL $-2.37 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ⚠️ Pares persistindo negativos: XRP/USDC:USDC ($-1.06/10), ETH/USDC:USDC ($-1.00/13), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 03:05 UTC

**Open trades:** 0

**Cumulativo (n=82):** PnL $-1.68 | WR 29% (24W/58L) | avg $-0.020 | win $+0.339 | loss $-0.169 | dur 37.3m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 29% + PnL $-1.68 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ℹ️ Ganho médio ($0.34) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 04:05 UTC

**Open trades:** 0

**Cumulativo (n=82):** PnL $-1.68 | WR 29% (24W/58L) | avg $-0.020 | win $+0.339 | loss $-0.169 | dur 37.3m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 29% + PnL $-1.68 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ℹ️ Ganho médio ($0.34) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 05:05 UTC

**Open trades:** 0

**Cumulativo (n=82):** PnL $-1.68 | WR 29% (24W/58L) | avg $-0.020 | win $+0.339 | loss $-0.169 | dur 37.3m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 29% + PnL $-1.68 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ℹ️ Ganho médio ($0.34) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 06:05 UTC

**Open trades:** 0

**Cumulativo (n=82):** PnL $-1.68 | WR 29% (24W/58L) | avg $-0.020 | win $+0.339 | loss $-0.169 | dur 37.3m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 29% + PnL $-1.68 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ℹ️ Ganho médio ($0.34) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 07:05 UTC

**Open trades:** 0

**Cumulativo (n=82):** PnL $-1.68 | WR 29% (24W/58L) | avg $-0.020 | win $+0.339 | loss $-0.169 | dur 37.3m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `SUI/USDC:USDC`: $-0.41 (13 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+0.47 (11 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 10
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `twin_max_loss`: 5
- `unknown`: 4
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ⚠️ Win-rate 29% + PnL $-1.68 = expectância negativa. Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos.
- ℹ️ Ganho médio ($0.34) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 10× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 08:05 UTC

**Open trades:** 0

**Cumulativo (n=84):** PnL $+0.16 | WR 31% (26W/58L) | avg $+0.002 | win $+0.384 | loss $-0.169 | dur 37.0m
**Desde última run (n=2):** PnL $+1.84 | WR 100% (2W/0L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SUI/USDC:USDC`: $-0.09 (14 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `TON/USDC:USDC`: $+1.99 (12 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 11
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.38) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 11× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 09:05 UTC

**Open trades:** 0

**Cumulativo (n=85):** PnL $+0.81 | WR 32% (27W/58L) | avg $+0.010 | win $+0.394 | loss $-0.169 | dur 36.7m
**Desde última run (n=1):** PnL $+0.66 | WR 100% (1W/0L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `ONDO/USDC:USDC`: $-0.45 (15 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `SUI/USDC:USDC`: $+0.57 (15 trades)
- `TON/USDC:USDC`: $+1.99 (12 trades)

**Exit reasons:**
- `twin_loser_close`: 45
- `twin_winner_revert`: 12
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), XRP/USDC:USDC ($-0.57/11), ONDO/USDC:USDC ($-0.45/15). Avaliar remover do `basket.pairs`.
- ⚠️ 45× `twin_loser_close` vs 12× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 10:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 91 | ONDO/USDC:USDC | S | $7.00 | 7x | 2.248→2.241 | -3.87% | 1.33% | 28c | 0.08 |

**Cumulativo (n=86):** PnL $+0.43 | WR 31% (27W/59L) | avg $+0.005 | win $+0.394 | loss $-0.173 | dur 36.5m
**Desde última run (n=1):** PnL $-0.38 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `SUI/USDC:USDC`: $+0.57 (15 trades)
- `TON/USDC:USDC`: $+1.99 (12 trades)

**Exit reasons:**
- `twin_loser_close`: 46
- `twin_winner_revert`: 12
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.57/11). Avaliar remover do `basket.pairs`.
- ⚠️ 46× `twin_loser_close` vs 12× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 11:05 UTC

**Open trades:** 3

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 90 | DOGE/USDC:USDC | L | $52.09 | 7x | -1.126→-1.930 | -0.20% | 2.54% | 24c | 0.08 |
| 92 | SOL/USDC:USDC | L | $2.08 | 7x | -1.186→-1.346 | -0.53% | 0.48% | 26c | 0.08 |
| 94 | XRP/USDC:USDC | L | $2.13 | 7x | -1.357→-1.725 | 0.10% | 0.21% | 29c | 0.08 |

**Cumulativo (n=88):** PnL $+0.35 | WR 31% (27W/61L) | avg $+0.004 | win $+0.394 | loss $-0.169 | dur 36.0m
**Desde última run (n=2):** PnL $-0.08 | WR 0% (0W/2L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.57 (11 trades)
- `DOGE/USDC:USDC`: $-0.12 (8 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `SUI/USDC:USDC`: $+0.53 (16 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 48
- `twin_winner_revert`: 12
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.57/11). Avaliar remover do `basket.pairs`.
- ⚠️ 48× `twin_loser_close` vs 12× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 12:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 92 | SOL/USDC:USDC | L | $2.08 | 7x | 0.828→-1.346 | -3.82% | 0.48% | 14c | 0.08 |

**Cumulativo (n=90):** PnL $+0.52 | WR 31% (28W/62L) | avg $+0.006 | win $+0.386 | loss $-0.166 | dur 36.1m
**Desde última run (n=1):** PnL $-0.01 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.00 (13 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `SUI/USDC:USDC`: $+0.53 (16 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 49
- `twin_winner_revert`: 13
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.17). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.00/13), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 49× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 13:05 UTC

**Open trades:** 2

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 92 | SOL/USDC:USDC | L | $2.08 | 7x | 0.027→-1.346 | -2.86% | 0.48% | 2c | 0.08 |
| 95 | DOGE/USDC:USDC | S | $2.14 | 7x | 0.555→1.484 | -1.56% | 2.13% | 19c | 0.08 |

**Cumulativo (n=91):** PnL $+0.49 | WR 31% (28W/63L) | avg $+0.005 | win $+0.386 | loss $-0.164 | dur 35.9m
**Desde última run (n=1):** PnL $-0.03 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.40 (11 trades)
- `SUI/USDC:USDC`: $+0.53 (16 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 50
- `twin_winner_revert`: 13
- `twin_time_stop`: 9
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 50× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 14:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run (n=1):** PnL $-0.13 | WR 0% (0W/1L)

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 15:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 16:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 17:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 18:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 19:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 20:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 21:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 22:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-26 23:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 00:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 01:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 02:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 03:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 04:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 05:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 06:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 07:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 08:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 09:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 10:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 11:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 12:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 13:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 14:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 15:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 16:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 17:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 18:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 19:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 20:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---

## 2026-05-27 21:05 UTC

**Open trades:** 1

| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |
|----|------|------|-------|-----|---------|--------|------|-------|--------|
| 95 | DOGE/USDC:USDC | S | $56.30 | 7x | -0.618→1.484 | -1.64% | 3.29% | 9c | 0.08 |

**Cumulativo (n=93):** PnL $+0.30 | WR 30% (28W/65L) | avg $+0.003 | win $+0.386 | loss $-0.162 | dur 36.9m
**Desde última run:** nenhum trade novo.

**Por par (cumulativo):**
- `ETH/USDC:USDC`: $-1.02 (14 trades)
- `ONDO/USDC:USDC`: $-0.84 (16 trades)
- `XRP/USDC:USDC`: $-0.58 (12 trades)
- `DOGE/USDC:USDC`: $+0.06 (9 trades)
- `SOL/USDC:USDC`: $+0.33 (12 trades)
- `SUI/USDC:USDC`: $+0.40 (17 trades)
- `TON/USDC:USDC`: $+1.94 (13 trades)

**Exit reasons:**
- `twin_loser_close`: 51
- `twin_winner_revert`: 13
- `twin_time_stop`: 10
- `trailing_stop_loss`: 8
- `unknown`: 5
- `twin_max_loss`: 5
- `stop_loss`: 1

**Tunables atuais:**
- `basket.entry_z` = 1.2
- `basket.exit_z` = 0.5
- `basket.zscore_method` = kalman
- `zscore.zscore_window` = 288
- `twin.winner_exit_z` = 0.08
- `twin.max_candles` = 30
- `twin.loser_max_candles` = 3
- `twin.safety_stop` = -0.1167
- `twin.initial_leverage` = 7
- `twin.scale_stake` = 250.0
- `twin.max_scale_times` = 1
- `twin.z_revert_min` = 0.35

**Sugestões heurísticas:**
- ℹ️ Ganho médio ($0.39) >2× perda média ($-0.16). Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`.
- ⚠️ Pares persistindo negativos: ETH/USDC:USDC ($-1.02/14), ONDO/USDC:USDC ($-0.84/16), XRP/USDC:USDC ($-0.58/12). Avaliar remover do `basket.pairs`.
- ⚠️ 51× `twin_loser_close` vs 13× `twin_winner_revert`. Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar.

---
