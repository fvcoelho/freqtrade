# 2026-05-24 — TwinPennies V4 btc_trend tightening

## O que mudou hoje

**Config alterado** em `user_data/strategies/twin_pennies_config.json`:

| Knob | Antes | Agora |
|---|---|---|
| `pump_threshold` | 3.0 | **1.0** |
| `dump_threshold` | -3.0 | **-1.0** |
| `high_vol_threshold` | 2.0 | **1.0** |

**Bot reiniciado** 2026-05-24 12:25 UTC:
- PID atual: **295075**
- Log backup pré-restart: `twin_pennies.log.pre-restart-20260524-122412`
- Primeira trade pós-restart: SUI/USDC Long #16 (12:25:19 UTC, $15 @ 3x)

## Por quê

Backtest do `btc_trend` original mostrou que estava **praticamente desligado** (filtros disparam só 4,7% do tempo no período Mar-Mai 2026):

| Período | Baseline 3/-3/2 | Tight 1/-1/1 | Δ |
|---|---|---|---|
| Mar-Mai 2026 (BTC +16%) | -73,3% | **-40,2%** | +33pp, DD 81→62% |
| Dez-Fev 2026 (BTC -9,5%) | -45% | **-2,2%** | +43pp, DD 52→31% |

A curva é monotônica — tighter sempre melhora. 1.0 é sweet spot (ainda mantém ~2.243 trades em 78d vs 1.296 a 0.1).

**Caveat brutal:** isso não cria edge, só reduz perda. Strategy continua net-negative em backtest. A "melhora" é tradar menos do que está perdendo dinheiro.

## Outros patches testados e descartados hoje

- **trail_lock** (peak-profit drawdown exit, 0.015/0.4 e 0.025/0.6): +1pp at best, não vale a complexidade. **Revertido.**
- **safety_stop sweep** (-3% / -5% / -7% / -10%): -5% atual é local optimum. Ambas as direções pioram.

## Checklist de verificação para 2026-05-25 ~12:30 UTC

Bot terá ~24h rodando com filtro novo. Comparar com baseline pré-restart (mesma janela do dia anterior 12:25→12:25):

### 1. Trade count
```bash
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('/root/freqtrade/twin_pennies_mainnet.sqlite'); \
  print('Trades últimas 24h:', list(c.execute(\"SELECT COUNT(*) FROM trades WHERE open_date > datetime('now', '-24 hours')\"))[0][0]); \
  print('Closed últimas 24h:', list(c.execute(\"SELECT COUNT(*) FROM trades WHERE close_date > datetime('now', '-24 hours')\"))[0][0])"
```
Comparar com baseline pré-mudança (last 24h before 12:25 UTC):
```bash
grep -c "Long signal found\|Short signal found" twin_pennies.log.pre-restart-20260524-122412
```

### 2. % de ticks bloqueados pelo filtro
```bash
# Total ticks últimas 24h
total=$(grep -c "TICK z=" twin_pennies.log)
# Ticks com pump=True ou dump=True ou chaos=True
blocked=$(grep -E "TICK z=.*pump=True|dump=True|chaos=True" twin_pennies.log | wc -l)
echo "Total ticks: $total"
echo "Blocked: $blocked ($(awk -v t=$total -v b=$blocked 'BEGIN{printf \"%.1f%%\", b/t*100}'))"
```
**Decisão:** se bloqueio > 30%, considerar afrouxar pra 1.5. Se < 10%, considerar apertar pra 0.5.

### 3. HL PnL real (source of truth, não DB)
```bash
.venv/bin/python scripts/hl_trade_report.py --days 1
```
Comparar com o report de 2026-05-23→24 (NET PnL: -34,27 USDC) — esse foi com filtro antigo.

### 4. Long vs Short breakdown
```bash
.venv/bin/python -c "
import sqlite3
c = sqlite3.connect('/root/freqtrade/twin_pennies_mainnet.sqlite')
rows = c.execute(\"\"\"SELECT pair, is_short, COUNT(*) as n,
  COALESCE(SUM(close_profit_abs), 0) as pnl
  FROM trades WHERE open_date > datetime('now', '-24 hours')
  GROUP BY pair, is_short ORDER BY pair, is_short\"\"\").fetchall()
print(f'{\"PAIR\":<15} {\"DIR\":<6} {\"N\":>4} {\"PnL\":>8}')
for p, s, n, pnl in rows:
    print(f'{p:<15} {\"SHORT\" if s else \"LONG\":<6} {n:>4} {pnl:>8.2f}')
"
```
Em uptrend BTC (período atual), expectativa: shorts cair de proporção (filtro pump bloqueia mais).

## Estado atual da live (snapshot 12:44 UTC)

- Bot PID 295075 — `pgrep -af TwinPennies` pra confirmar ainda vivo
- Config knobs:
  - `safety_stop: -0.05` (não mexido)
  - `winner_exit_z: 0.08` (não mexido)
  - `max_candles: 30` (não mexido)
  - `pump/dump/hivol: 1.0/-1.0/1.0` ← ÚNICA MUDANÇA HOJE

## Próximos vetores se filtro for bem

1. **Stake size menor** — atual `unlimited` com first stake $5; talvez `min_winner_profit` mais alto evita scaling em sinais fracos.
2. **Leverage 3→2** — fee multiplier menor (HL ~5bps round-trip vira 10bps efetivo a 3x).
3. **Pair selection** — sweep por pair: alguns (BTC?) podem ter edge negativo claro.
4. **Trail_lock revisitado** com filtro tight — talvez o ganho mude quando o pool de trades é diferente.
