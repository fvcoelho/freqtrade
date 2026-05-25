#!/bin/bash
# ============================================================================
# ZScoreV52 — Start Production
# ============================================================================
set -euo pipefail

CONFIG="/root/freqtrade/user_data/configs/config_v52_production.json"
DB="sqlite:///v52_production.sqlite"
LOG="/tmp/v52_production.log"

# --- Validações ---
echo "=== Pre-flight checks ==="

# 1. API keys
if grep -q "PREENCHER" "$CONFIG"; then
    echo "✗ ERRO: API keys não preenchidas em $CONFIG"
    echo "  Edite o arquivo e substitua PREENCHER_API_KEY e PREENCHER_API_SECRET"
    exit 1
fi
echo "  ✓ API keys configuradas"

# 2. dry_run deve ser false
if grep -q '"dry_run": true' "$CONFIG"; then
    echo "✗ ERRO: dry_run ainda é true"
    exit 1
fi
echo "  ✓ dry_run = false (produção)"

# 3. Confirmar com o usuário
echo ""
echo "  ⚠  ATENÇÃO: Vai operar com DINHEIRO REAL na Hyperliquid"
echo "  ⚠  Estratégia: ZScoreV52Strategy"
echo "  ⚠  Config: $CONFIG"
echo ""
read -p "  Confirmar? (digite 'SIM' em maiúsculo): " confirm
if [ "$confirm" != "SIM" ]; then
    echo "  Cancelado."
    exit 0
fi

# --- Parar bot existente ---
echo ""
echo "=== Parando bots existentes ==="
pkill -f "freqtrade trade" 2>/dev/null && echo "  ✓ Bots parados" || echo "  Nenhum bot rodando"
sleep 2

# --- Iniciar ---
echo ""
echo "=== Iniciando V52 PRODUÇÃO ==="
cd /root/freqtrade
nohup .venv/bin/freqtrade trade \
    --strategy ZScoreV52Strategy \
    --config "$CONFIG" \
    --db-url "$DB" \
    -v > "$LOG" 2>&1 &

sleep 5

if pgrep -f "ZScoreV52Strategy" > /dev/null; then
    PID=$(pgrep -f "ZScoreV52Strategy" | head -1)
    echo "  ✓ V52 PRODUÇÃO rodando (PID: $PID)"
    echo "  Log: tail -f $LOG"
    echo "  API: http://$(hostname -I | awk '{print $1}'):8081"
else
    echo "  ✗ Falhou ao iniciar. Verifique:"
    echo "  tail -50 $LOG"
fi
