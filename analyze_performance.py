#!/usr/bin/env python3
"""Analyze TwinPennies trading performance every 2 hours."""
import sqlite3
import os
import sys
import json
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = os.environ.get("FREQTRADE_DB", "/root/freqtrade/twin_pennies_mainnet.sqlite")
STATE_FILE = "/root/freqtrade/.performance_analysis_state.json"
REPORT_FILE = "/root/freqtrade/performance_report.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_report_time": None, "trade_hashes": []}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def analyze_trades():
    if not os.path.exists(DB_PATH):
        return None, "Database not found"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    
    if 'trades' not in tables:
        conn.close()
        return None, "No trades table"
    
    # Get all trades
    cursor.execute("""
        SELECT id, pair, is_short, open_date, close_date, 
               open_rate, close_rate, amount, stake_amount,
               realized_profit, close_profit, close_profit_abs, fee_open, fee_close,
               stop_loss, initial_stop_loss,
               max_rate, min_rate,
               exit_reason, strategy
        FROM trades 
        ORDER BY open_date DESC
    """)
    trades = cursor.fetchall()
    
    # Get orders for volume analysis
    if 'orders' in tables:
        cursor.execute("""
            SELECT ft_trade_id, order_id, status, filled, remaining, cost
            FROM orders WHERE status = 'closed'
            ORDER BY order_date DESC
        """)
        orders = cursor.fetchall()
    else:
        orders = []
    
    conn.close()
    
    return trades, orders

def calculate_metrics(trades, orders):
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "total_trades": len(trades),
        "open_trades": 0,
        "closed_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_profit_abs": 0.0,
        "total_volume": 0.0,
        "avg_profit_per_trade": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "largest_win": 0.0,
        "largest_loss": 0.0,
        "max_drawdown": 0.0,
        "sharpe_approx": 0.0,
        "by_pair": {},
        "by_side": {"LONG": {"count": 0, "wins": 0, "profit": 0.0}, 
                    "SHORT": {"count": 0, "wins": 0, "profit": 0.0}},
        "by_exit_reason": defaultdict(lambda: {"count": 0, "profit": 0.0}),
        "recent_trades": [],
        "recommendations": [],
        "alerts": []
    }
    
    if not trades:
        return metrics
    
    wins = []
    losses = []
    daily_pnl = defaultdict(float)
    equity_curve = []
    running_pnl = 0.0
    peak_equity = 0.0
    
    for trade in trades:
        pair = trade['pair']
        is_short = trade['is_short']
        side = "SHORT" if is_short else "LONG"
        profit = trade['realized_profit'] or 0.0
        profit_pct = trade['close_profit'] or 0.0
        
        # Track by pair
        if pair not in metrics["by_pair"]:
            metrics["by_pair"][pair] = {
                "count": 0, "wins": 0, "profit": 0.0, 
                "volume": 0.0, "avg_profit": 0.0
            }
        
        metrics["by_pair"][pair]["count"] += 1
        metrics["by_pair"][pair]["profit"] += profit
        metrics["by_pair"][pair]["volume"] += trade['stake_amount'] or 0
        
        # Track by side
        metrics["by_side"][side]["count"] += 1
        metrics["by_side"][side]["profit"] += profit
        
        if trade['close_date']:
            metrics["closed_trades"] += 1
            metrics["total_profit_abs"] += profit
            
            if profit > 0:
                metrics["winning_trades"] += 1
                wins.append(profit)
                metrics["by_pair"][pair]["wins"] += 1
                metrics["by_side"][side]["wins"] += 1
            else:
                metrics["losing_trades"] += 1
                losses.append(profit)
            
            # Track by exit reason
            exit_reason = trade['exit_reason'] or 'unknown'
            metrics["by_exit_reason"][exit_reason]["count"] += 1
            metrics["by_exit_reason"][exit_reason]["profit"] += profit
            
            # Daily P&L for Sharpe approximation
            day = trade['close_date'][:10] if trade['close_date'] else 'unknown'
            daily_pnl[day] += profit
            
            running_pnl += profit
            equity_curve.append(running_pnl)
            peak_equity = max(peak_equity, running_pnl)
            drawdown = peak_equity - running_pnl
            metrics["max_drawdown"] = max(metrics["max_drawdown"], drawdown)
            
            # Recent closed trades (last 5)
            if len(metrics["recent_trades"]) < 5:
                metrics["recent_trades"].append({
                    "pair": pair,
                    "side": side,
                    "profit": profit,
                    "profit_pct": profit_pct * 100,
                    "exit_reason": exit_reason,
                    "close_date": trade['close_date']
                })
        else:
            metrics["open_trades"] += 1
    
    # Calculate derived metrics
    closed = metrics["closed_trades"]
    if closed > 0:
        metrics["win_rate"] = (metrics["winning_trades"] / closed) * 100
        metrics["avg_profit_per_trade"] = metrics["total_profit_abs"] / closed
    
    if wins:
        metrics["avg_win"] = sum(wins) / len(wins)
        metrics["largest_win"] = max(wins)
    
    if losses:
        metrics["avg_loss"] = sum(losses) / len(losses)
        metrics["largest_loss"] = min(losses)
    
    # Profit factor
    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 1
    metrics["profit_factor"] = total_wins / total_losses if total_losses > 0 else float('inf')
    
    # Sharpe approximation (simplified)
    if len(daily_pnl) > 1:
        daily_returns = list(daily_pnl.values())
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance ** 0.5
        metrics["sharpe_approx"] = (avg_return / std_dev * (252 ** 0.5)) if std_dev > 0 else 0
    
    # Calculate per-pair averages
    for pair, data in metrics["by_pair"].items():
        if data["count"] > 0:
            data["avg_profit"] = data["profit"] / data["count"]
            data["win_rate"] = (data["wins"] / data["count"]) * 100
    
    # Generate recommendations
    metrics["recommendations"] = generate_recommendations(metrics)
    metrics["alerts"] = generate_alerts(metrics)
    
    return metrics

def generate_recommendations(metrics):
    recs = []
    
    # Win rate analysis
    if metrics["win_rate"] < 40 and metrics["closed_trades"] > 10:
        recs.append("⚠️ Win rate abaixo de 40%. Considerar ajustar entry_z threshold ou revisar critérios de entrada.")
    elif metrics["win_rate"] > 60 and metrics["closed_trades"] > 20:
        recs.append("✅ Win rate saudável (>60%). Pode considerar aumentar stake size gradualmente.")
    
    # Profit factor
    if metrics["profit_factor"] < 1.0 and metrics["closed_trades"] > 5:
        recs.append("🔴 Profit factor < 1.0. Estratégia está perdendo dinheiro. Revisar urgentemente.")
    elif metrics["profit_factor"] > 2.0:
        recs.append("🟢 Profit factor excelente (>2.0). Estratégia está bem calibrada.")
    
    # Drawdown
    if metrics["max_drawdown"] > 100:
        recs.append(f"⚠️ Max drawdown alto (${metrics['max_drawdown']:.2f}). Considerar reduzir leverage ou stake.")
    
    # Pair performance
    worst_pair = None
    worst_profit = 0
    for pair, data in metrics["by_pair"].items():
        if data["count"] >= 3 and data["profit"] < worst_profit:
            worst_pair = pair
            worst_profit = data["profit"]
    
    if worst_pair:
        recs.append(f"📉 Par {worst_pair} com performance negativa (${worst_profit:.2f}). Considerar remover da whitelist.")
    
    # Best pair
    best_pair = None
    best_profit = 0
    for pair, data in metrics["by_pair"].items():
        if data["count"] >= 3 and data["profit"] > best_profit:
            best_pair = pair
            best_profit = data["profit"]
    
    if best_pair:
        recs.append(f"📈 Par {best_pair} é o melhor performer (${best_profit:.2f}). Considerar aumentar alocação.")
    
    # Side bias
    long_profit = metrics["by_side"]["LONG"]["profit"]
    short_profit = metrics["by_side"]["SHORT"]["profit"]
    if abs(long_profit - short_profit) > 50:
        if long_profit > short_profit:
            recs.append("📊 Bias para LONG está funcionando melhor. Verificar se o mercado está em uptrend.")
        else:
            recs.append("📊 Bias para SHORT está funcionando melhor. Verificar se o mercado está em downtrend.")
    
    # Exit reasons
    for reason, data in metrics["by_exit_reason"].items():
        if reason != 'force_exit' and data["count"] > 3 and data["profit"] < -20:
            recs.append(f"🚪 Exit reason '{reason}' está gerando perdas consistentes. Revisar lógica de saída.")
    
    return recs

def generate_alerts(metrics):
    alerts = []
    
    if metrics["closed_trades"] == 0 and metrics["open_trades"] == 0:
        alerts.append("🚨 NENHUMA TRADE ABERTA OU FECHADA! Bot pode estar parado.")
    
    if metrics["open_trades"] >= 4:
        alerts.append(f"⚠️ {metrics['open_trades']} trades abertas (máximo sugerido). Risco de sobre-exposição.")
    
    if metrics["profit_factor"] < 0.5 and metrics["closed_trades"] > 5:
        alerts.append("🔴 CRÍTICO: Profit factor muito baixo. Estratégia precisa de ajuste imediato.")
    
    if metrics["max_drawdown"] > 200:
        alerts.append(f"🔴 DRAWDOWN CRÍTICO: ${metrics['max_drawdown']:.2f}. Considerar parar trading e revisar.")
    
    # Check for stagnant trades (open for too long)
    # This would need additional logic with current timestamp
    
    return alerts

def format_report(metrics):
    if not metrics or metrics["total_trades"] == 0:
        return "📊 TwinPennies Analysis: Nenhuma trade encontrada no banco de dados."
    
    lines = [
        "📊 TWINPENNIES PERFORMANCE REPORT",
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"📈 ESTATÍSTICAS GERAIS",
        f"   Total trades: {metrics['total_trades']} (Abertas: {metrics['open_trades']}, Fechadas: {metrics['closed_trades']})",
        f"   Win rate: {metrics['win_rate']:.1f}% ({metrics['winning_trades']}/{metrics['closed_trades']})",
        f"   Profit total: ${metrics['total_profit_abs']:.2f}",
        f"   Média por trade: ${metrics['avg_profit_per_trade']:.2f}",
        f"   Profit factor: {metrics['profit_factor']:.2f}",
        f"   Max drawdown: ${metrics['max_drawdown']:.2f}",
        "",
        f"💰 RESULTADOS POR LADO",
        f"   LONG: {metrics['by_side']['LONG']['count']} trades, ${metrics['by_side']['LONG']['profit']:.2f}",
        f"   SHORT: {metrics['by_side']['SHORT']['count']} trades, ${metrics['by_side']['SHORT']['profit']:.2f}",
        "",
    ]
    
    if metrics["by_pair"]:
        lines.append("📉 PERFORMANCE POR PAR (top 5):")
        sorted_pairs = sorted(metrics["by_pair"].items(), key=lambda x: x[1]["profit"], reverse=True)[:5]
        for pair, data in sorted_pairs:
            emoji = "🟢" if data["profit"] > 0 else "🔴"
            lines.append(f"   {emoji} {pair}: {data['count']} trades, ${data['profit']:.2f} (WR: {data.get('win_rate', 0):.0f}%)")
        lines.append("")
    
    if metrics["recent_trades"]:
        lines.append("🕐 TRADES RECENTES (últimas 5):")
        for t in metrics["recent_trades"]:
            emoji = "🟢" if t["profit"] > 0 else "🔴"
            lines.append(f"   {emoji} {t['pair']} {t['side']}: ${t['profit']:.2f} ({t['profit_pct']:.2f}%) - {t['exit_reason']}")
        lines.append("")
    
    if metrics["alerts"]:
        lines.append("🚨 ALERTAS:")
        for alert in metrics["alerts"]:
            lines.append(f"   {alert}")
        lines.append("")
    
    if metrics["recommendations"]:
        lines.append("💡 RECOMENDAÇÕES:")
        for rec in metrics["recommendations"]:
            lines.append(f"   {rec}")
        lines.append("")
    
    lines.append("─" * 40)
    
    return "\n".join(lines)

def generate_claude_prompt(metrics, trades):
    """Generate a detailed prompt for Claude Code analysis."""
    
    prompt = f"""# Análise de Performance TwinPennies - Solicitação ao Claude Code

## 📊 Dados Coletados em {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

### Estratégia
- **Nome**: TwinPenniesStrategy
- **Exchange**: Hyperliquid (mainnet)
- **Tipo**: Pair trading com Z-Score (entry_z=1.2)
- **Pares**: BTC/USDC, ETH/USDC, SOL/USDC, XRP/USDC, DOGE/USDC, SUI/USDC, ONDO/USDC, TON/USDC

### Métricas Principais
```json
{{
  "total_trades": {metrics.get('total_trades', 0)},
  "open_trades": {metrics.get('open_trades', 0)},
  "closed_trades": {metrics.get('closed_trades', 0)},
  "win_rate": {metrics.get('win_rate', 0):.2f},
  "total_profit_usd": {metrics.get('total_profit_abs', 0):.2f},
  "avg_profit_per_trade": {metrics.get('avg_profit_per_trade', 0):.2f},
  "profit_factor": {metrics.get('profit_factor', 0):.2f},
  "max_drawdown_usd": {metrics.get('max_drawdown', 0):.2f},
  "sharpe_approx": {metrics.get('sharpe_approx', 0):.2f}
}}
```

### Performance por Lado
- **LONG**: {metrics['by_side']['LONG']['count']} trades, ${metrics['by_side']['LONG']['profit']:.2f}
- **SHORT**: {metrics['by_side']['SHORT']['count']} trades, ${metrics['by_side']['SHORT']['profit']:.2f}

### Performance por Par
"""
    
    # Add pair performance
    sorted_pairs = sorted(metrics["by_pair"].items(), key=lambda x: x[1]["profit"], reverse=True)
    for pair, data in sorted_pairs[:8]:
        wr = (data['wins'] / data['count'] * 100) if data['count'] > 0 else 0
        prompt += f"- {pair}: {data['count']} trades, ${data['profit']:.2f}, WR {wr:.0f}%, Vol ${data.get('volume', 0):.2f}\n"
    
    prompt += "\n### Trades Recentes\n"
    for i, t in enumerate(metrics.get("recent_trades", [])[:5], 1):
        prompt += f"{i}. {t['pair']} {t['side']}: ${t['profit']:.2f} ({t['profit_pct']:.2f}%) - {t['exit_reason']}\n"
    
    if metrics.get("alerts"):
        prompt += "\n### ⚠️ Alertas Atuais\n"
        for alert in metrics["alerts"]:
            prompt += f"- {alert}\n"
    
    if metrics.get("by_exit_reason"):
        prompt += "\n### Razões de Saída\n"
        for reason, data in metrics["by_exit_reason"].items():
            prompt += f"- {reason}: {data['count']} trades, ${data['profit']:.2f}\n"
    
    prompt += """
---

## 🤔 Solicitação de Análise ao Claude Code

Por favor, analise os dados acima do robô de trading TwinPennies e forneça:

### 1. 📈 Análise de Performance
- A estratégia está saudável? (Win rate, profit factor, drawdown)
- Há algum viés de mercado detectado (tendência vs range)?
- Os pares estão bem selecionados?

### 2. 💎 Sugestões de Otimização
- Quais parâmetros deveriam ser ajustados? (entry_z, exit thresholds, stake size)
- Algum par deveria ser removido da whitelist?
- Vale a pena adicionar novos pares?

### 3. 🚨 Identificação de Problemas
- Há sinais de overfitting?
- O risk/reward está equilibrado?
- Há padrões preocupantes nas razões de saída?

### 4. 🎯 Plano de Ação Priorizado
Liste 3-5 ações específicas para melhorar performance, ordenadas por impacto.

### 5. 📊 Benchmarking
- Como esses números se comparam a benchmarks de pair trading?
- O que seria considerado "bom" vs "excelente" para esta estratégia?

**Formate sua resposta em Markdown claro e conciso, com emojis para facilitar leitura.**

---
*Dados gerados automaticamente pelo sistema de monitoramento TwinPennies*
*Job executado a cada 2 horas para garantir consistência e melhoria contínua*
"""
    
    return prompt
def main():
    state = load_state()
    
    trades, orders = analyze_trades()
    
    if trades is None:
        print(f"⚠️ Erro: {orders}")
        return 0
    
    metrics = calculate_metrics(trades, orders)
    
    # Save detailed report
    with open(REPORT_FILE, 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    
    # Generate hash of current trades for change detection
    current_hash = hash(tuple(t['id'] for t in trades[:20])) if trades else 0
    
    # Always print report for cron capture
    report = format_report(metrics)
    print(report)
    
    # Generate Claude Code prompt
    claude_prompt = generate_claude_prompt(metrics, trades)
    prompt_file = "/root/freqtrade/claude_analysis_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(claude_prompt)
    
    print(f"\n📝 Prompt para Claude Code salvo em: {prompt_file}")
    
    # Check if significant change or first run
    last_time = state.get("last_report_time")
    significant_change = False
    
    if last_time:
        last_dt = datetime.fromisoformat(last_time)
        hours_since = (datetime.now() - last_dt).total_seconds() / 3600
        # Always report every 2 hours (cron handles this)
        significant_change = True
    else:
        significant_change = True
    
    if significant_change:
        state["last_report_time"] = datetime.now().isoformat()
        state["trade_hashes"] = [current_hash]
        save_state(state)
        print("\n---REPORT---")
        return 1  # Signal to send notification
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
