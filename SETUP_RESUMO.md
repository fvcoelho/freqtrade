# Freqtrade - Setup Completo

## Instalação
- **Local:** `~/freqtrade/`
- **Versão:** 2026.3
- **Python:** 3.13.12 (via uv)
- **Ambiente:** `.venv/`

## Estrutura
```
~/freqtrade/
├── .venv/                  # Ambiente virtual Python
├── user_data/
│   ├── config.json         # Configuração principal
│   ├── data/
│   │   └── binance/        # Dados OHLCV (BTC, ETH, SOL, BNB, XRP)
│   ├── strategies/
│   │   ├── RSIMACDStrategy.py   # Estratégia principal (RSI + MACD)
│   │   └── sample_strategy.py   # Estratégia exemplo
│   ├── backtest_results/   # Resultados de backtests
│   ├── logs/              # Logs de execução
│   └── tradesv3.sqlite    # Banco de dados de trades
└── setup.sh               # Script de instalação
```

## Configuração Atual (config.json)

### Modo de Operação
- **Exchange:** Hyperliquid (DEX Spot)
- **dry_run:** `true` (simulação - sem dinheiro real)
- **dry_run_wallet:** $1.000 USDC (fictício)
- **Stake:** Unlimited (dividido entre max_open_trades)
- **Stake Currency:** USDC

### Pares Monitorados
- BTC/USDC
- ETH/USDC
- SOL/USDC
- HYPE/USDC

### Exchange
- **Nome:** Hyperliquid (DEX)
- **Tipo:** Spot
- **Timeframe:** 5m

### Risk Management
| Parâmetro | Valor |
|-----------|-------|
| max_open_trades | 3 |
| stoploss | -10% |
| trailing_stop | Ativado |
| trailing_stop_positive | +1% |
| trailing_stop_positive_offset | Após +2% |

### ROI (Take Profit)
```
60 min → 1%
30 min → 2%
0 min  → 4% (máximo)
```

## Estratégia: RSIMACDStrategy

### Indicadores
- RSI (14 períodos)
- MACD (12, 26, 9)
- EMA (9, 21)
- Bollinger Bands (20, 2)

### Sinal de Entrada (Compra)
1. RSI < 35 (sobrevendido)
2. MACD cruza acima do sinal
3. Volume existe

OU

1. RSI < 40
2. Preço toca banda inferior de Bollinger
3. MACD cruzando para cima

### Sinal de Saída (Venda)
1. RSI > 70 (sobrecomprado) + MACD cruzando para baixo
2. OU preço na banda superior com RSI > 65

### Parâmetros Otimizáveis
- `buy_rsi`: 20-45 (padrão: 35)
- `sell_rsi`: 60-85 (padrão: 70)

## Resultado Backtest (Março/2025)

| Métrica | Valor |
|---------|-------|
| Período | 01/03/2025 → 01/04/2025 |
| Trades | 58 |
| Win Rate | 60.3% |
| Lucro/Prejuízo | -4.83% |
| Market Change | -7.38% |
| Drawdown Máx | 7.69% |

**Observação:** Período bearish (mercado caiu 7.38%). Estratégia perdeu menos que o mercado.

## Comandos Úteis

### Ativar ambiente
```bash
cd ~/freqtrade
source .venv/bin/activate
```

### Rodar backtest
```bash
freqtrade backtesting -c user_data/config.json -s RSIMACDStrategy --timerange 20250301-20250401
```

### Iniciar bot (dry-run)
```bash
freqtrade trade -c user_data/config.json --dry-run
```

### Iniciar apenas webserver
```bash
freqtrade webserver -c user_data/config.json
```

### Baixar mais dados
```bash
freqtrade download-data --exchange binance -t 5m --timerange 20240101-
```

### Ver trades em aberto
```bash
freqtrade show-trades -c user_data/config.json
```

### Listar estratégias
```bash
freqtrade list-strategies
```

## Interface Web (FreqUI)
- **URL:** http://localhost:8080
- **Usuário:** freqtrade
- **Senha:** SuperSecretPassword123!

## Próximos Passos para Trading Real

1. **Criar conta na Binance**
2. **Gerar API Keys:**
   - Acesse: https://www.binance.com/en/my/settings/api-management
   - Criar chave com permissões: `Enable Reading`, `Enable Spot & Margin Trading`
3. **Editar config.json:**
   ```json
   "exchange": {
       "name": "binance",
       "key": "SUA_API_KEY",
       "secret": "SUA_API_SECRET"
   },
   "dry_run": false
   ```
4. **Ajustar stake_amount:**
   ```json
   "stake_amount": 100  # ou valor desejado por trade
   ```
5. **Reiniciar bot**

## Segurança
- ⚠️ **NUNCA** compartilhe suas API keys
- ⚠️ **Sempre** use dry-run primeiro
- ⚠️ Comece com valores pequenos
- ⚠️ Monitore os logs regularmente: `user_data/logs/`

## Processo em Execução
Para ver o processo rodando:
```bash
ps aux | grep freqtrade
tail -f ~/freqtrade/user_data/logs/freqtrade.log
```

---
**Setup criado em:** 23/04/2026
**Bot em dry-run:** Ativo
