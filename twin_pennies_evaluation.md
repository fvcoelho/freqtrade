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
