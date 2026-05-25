#!/usr/bin/env python3
"""TwinPennies V4 hourly evaluation — appends a markdown report to disk.

Reads:
  * /root/freqtrade/twin_pennies_mainnet.sqlite (open + closed trades)
  * /root/freqtrade/twin_pennies.log              (last HOLD line per pair, exit reasons)
  * /root/freqtrade/user_data/strategies/twin_pennies_config.json (tunables snapshot)

Writes (append):
  * /root/freqtrade/twin_pennies_evaluation.md    (one timestamped section per run)
  * /root/freqtrade/.twin_pennies_eval_state.json (last-seen trade id + last_run)

Designed to be invoked from cron — exits cleanly even when the bot is briefly
holding the SQLite write lock. Uses ?mode=ro so we never block the bot.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

DB = Path("/root/freqtrade/twin_pennies_mainnet.sqlite")
LOG = Path("/root/freqtrade/twin_pennies.log")
CONFIG = Path("/root/freqtrade/user_data/strategies/twin_pennies_config.json")
OUT = Path("/root/freqtrade/twin_pennies_evaluation.md")
STATE = Path("/root/freqtrade/.twin_pennies_eval_state.json")

LOG_TAIL_BYTES = 2_000_000
NOW = datetime.now(timezone.utc)


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"last_trade_id": 0}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2))


def fetch_trades():
    uri = f"file:{DB}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as c:
        c.row_factory = sqlite3.Row
        open_t = c.execute(
            "SELECT id, pair, is_short, open_date, open_rate, amount, "
            "stake_amount, leverage, enter_tag FROM trades WHERE is_open=1"
        ).fetchall()
        closed_t = c.execute(
            "SELECT id, pair, is_short, open_date, close_date, open_rate, close_rate, "
            "stake_amount, leverage, close_profit, close_profit_abs, exit_reason, enter_tag "
            "FROM trades WHERE is_open=0 ORDER BY id"
        ).fetchall()
    return [dict(r) for r in open_t], [dict(r) for r in closed_t]


def parse_log_tail() -> dict:
    if not LOG.exists():
        return {"hold_latest": {}}
    with LOG.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - LOG_TAIL_BYTES))
        data = f.read().decode(errors="replace")

    hold_pat = re.compile(
        r"HOLD (?P<pair>\S+) (?P<side>[LS])\[(?P<flags>[^\]]+)\] @(?P<cycles>\d+)c.*?"
        r"z=(?P<z>-?[\d.]+) entry_z=(?P<entry_z>-?[\d.]+) delta=(?P<delta>-?[\d.]+).*?"
        r"profit=(?P<profit>-?[\d.]+)% peak=(?P<peak>-?[\d.]+)% \$(?P<stake>[\d.]+).*?"
        r"btc_mom=(?P<btc>-?[\d.]+).*?time_left=(?P<tleft>\d+)c exit_z=(?P<exit_z>-?[\d.]+)"
    )
    hold_latest: dict[str, dict] = {}
    for ln in data.splitlines():
        m = hold_pat.search(ln)
        if m:
            hold_latest[m["pair"]] = m.groupdict()
    return {"hold_latest": hold_latest}


def parse_dt(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", ""))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return NOW


def fmt_dur(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds/60:.1f}m"
    if seconds < 86400:
        return f"{seconds/3600:.1f}h"
    return f"{seconds/86400:.1f}d"


def compute(closed: list, since_id: int):
    def agg(trades):
        if not trades:
            return None
        profits = [t["close_profit_abs"] or 0 for t in trades]
        ratios = [t["close_profit"] or 0 for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        durs = []
        for t in trades:
            try:
                durs.append((parse_dt(t["close_date"]) - parse_dt(t["open_date"])).total_seconds())
            except Exception:
                pass
        per_pair: dict[str, list] = defaultdict(lambda: [0, 0.0])
        for t in trades:
            per_pair[t["pair"]][0] += 1
            per_pair[t["pair"]][1] += t["close_profit_abs"] or 0
        return {
            "n": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": 100 * len(wins) / len(trades),
            "total_pnl": sum(profits),
            "avg_pnl": mean(profits),
            "avg_win": mean(wins) if wins else 0,
            "avg_loss": mean(losses) if losses else 0,
            "median_pct": 100 * median(ratios) if ratios else 0,
            "avg_dur_s": mean(durs) if durs else 0,
            "exit_reasons": Counter(t["exit_reason"] or "unknown" for t in trades),
            "per_pair": dict(per_pair),
        }

    return agg(closed), agg([t for t in closed if t["id"] > since_id])


def suggestions(cum: dict | None) -> list[str]:
    if not cum:
        return ["Nenhum trade fechado ainda — aguardando primeiro sinal."]
    sug = []
    wr, pnl = cum["win_rate"], cum["total_pnl"]
    aw, al = cum["avg_win"], cum["avg_loss"]

    if wr < 50 and pnl < 0:
        sug.append(
            f"⚠️ Win-rate {wr:.0f}% + PnL ${pnl:.2f} = expectância negativa. "
            f"Subir `basket.entry_z` (atual 1.2 → testar 1.5) para filtrar sinais mais extremos."
        )
    elif wr >= 60 and pnl > 0:
        sug.append(
            f"✅ Win-rate {wr:.0f}% saudável, PnL ${pnl:+.2f}. "
            f"Considere experimentar baixar `basket.entry_z` para captar mais trades."
        )

    if aw and al and abs(al) > 2 * aw:
        sug.append(
            f"⚠️ Perda média ${al:.2f} é >2× ganho médio ${aw:+.2f}. "
            f"Reduzir `twin.loser_max_candles` (atual 3) ou apertar `twin.safety_stop` "
            f"(atual -5%) para cortar losers mais cedo."
        )
    if aw and al and aw > 2 * abs(al):
        sug.append(
            f"ℹ️ Ganho médio (${aw:.2f}) >2× perda média (${al:.2f}). "
            f"Reward/risk excelente — pode aumentar `twin.initial_leverage` ou `scale_stake`."
        )

    bad = sorted(
        [(p, n, v) for p, (n, v) in cum["per_pair"].items() if n >= 3 and v < 0],
        key=lambda x: x[2],
    )[:3]
    if bad:
        bp = ", ".join(f"{p} (${v:+.2f}/{n})" for p, n, v in bad)
        sug.append(f"⚠️ Pares persistindo negativos: {bp}. Avaliar remover do `basket.pairs`.")

    er = cum["exit_reasons"]
    loser_n = er.get("twin_loser_close", 0)
    winner_n = er.get("twin_winner_revert", 0)
    if loser_n and winner_n and loser_n > 2 * winner_n:
        sug.append(
            f"⚠️ {loser_n}× `twin_loser_close` vs {winner_n}× `twin_winner_revert`. "
            f"Mais saídas por perda que por reversão — filtro de entrada (`entry_z`) precisa apertar."
        )
    if winner_n and loser_n and winner_n > 3 * loser_n and cum["avg_win"] < 0.5:
        sug.append(
            f"ℹ️ {winner_n}× winner_revert mas avg_win ${cum['avg_win']:.2f} pequeno. "
            f"`winner_exit_z` (0.08) pode estar saindo cedo demais — testar 0.0 ou negativo."
        )

    if cum["avg_dur_s"] and cum["avg_dur_s"] < 600:
        sug.append(
            f"ℹ️ Duração média {fmt_dur(cum['avg_dur_s'])} — muito curto. "
            f"Pode estar pegando ruído; subir `zscore.zscore_window` (atual 288) ou `entry_z`."
        )
    if cum["avg_dur_s"] and cum["avg_dur_s"] > 7200:
        sug.append(
            f"ℹ️ Duração média {fmt_dur(cum['avg_dur_s'])} — trades longos. "
            f"`twin.max_candles` (30 × 5m = 2.5h) pode estar segurando demais."
        )

    if not sug:
        sug.append("✅ Sem alertas heurísticos — comportamento dentro do esperado.")
    return sug


def load_config_snapshot() -> dict:
    try:
        cfg = json.loads(CONFIG.read_text())
    except Exception as e:
        return {"_error": str(e)}
    keep = {
        "basket.entry_z": cfg.get("basket", {}).get("entry_z"),
        "basket.exit_z": cfg.get("basket", {}).get("exit_z"),
        "basket.zscore_method": cfg.get("basket", {}).get("zscore_method"),
        "zscore.zscore_window": cfg.get("zscore", {}).get("zscore_window"),
        "twin.winner_exit_z": cfg.get("twin", {}).get("winner_exit_z"),
        "twin.max_candles": cfg.get("twin", {}).get("max_candles"),
        "twin.loser_max_candles": cfg.get("twin", {}).get("loser_max_candles"),
        "twin.safety_stop": cfg.get("twin", {}).get("safety_stop"),
        "twin.initial_leverage": cfg.get("twin", {}).get("initial_leverage"),
        "twin.scale_stake": cfg.get("twin", {}).get("scale_stake"),
        "twin.max_scale_times": cfg.get("twin", {}).get("max_scale_times"),
        "twin.z_revert_min": cfg.get("twin", {}).get("z_revert_min"),
    }
    return {k: v for k, v in keep.items() if v is not None}


def render(open_t, cum, recent, sug, hold, cfg) -> str:
    out = [f"\n## {NOW.strftime('%Y-%m-%d %H:%M UTC')}\n"]
    out.append(f"**Open trades:** {len(open_t)}")
    if open_t:
        out.append("")
        out.append("| ID | Pair | Side | Stake | Lev | z→entry | profit | peak | tleft | exit_z |")
        out.append("|----|------|------|-------|-----|---------|--------|------|-------|--------|")
        for t in open_t:
            side = "S" if t["is_short"] else "L"
            h = hold.get(t["pair"], {})
            out.append(
                f"| {t['id']} | {t['pair']} | {side} | ${t['stake_amount']:.2f} | "
                f"{t['leverage']:.0f}x | {h.get('z','?')}→{h.get('entry_z','?')} | "
                f"{h.get('profit','?')}% | {h.get('peak','?')}% | "
                f"{h.get('tleft','?')}c | {h.get('exit_z','?')} |"
            )

    if cum:
        out.append("")
        out.append(
            f"**Cumulativo (n={cum['n']}):** PnL ${cum['total_pnl']:+.2f} | "
            f"WR {cum['win_rate']:.0f}% ({cum['wins']}W/{cum['losses']}L) | "
            f"avg ${cum['avg_pnl']:+.3f} | win ${cum['avg_win']:+.3f} | "
            f"loss ${cum['avg_loss']:+.3f} | dur {fmt_dur(cum['avg_dur_s'])}"
        )
        if recent:
            out.append(
                f"**Desde última run (n={recent['n']}):** PnL ${recent['total_pnl']:+.2f} | "
                f"WR {recent['win_rate']:.0f}% ({recent['wins']}W/{recent['losses']}L)"
            )
        else:
            out.append("**Desde última run:** nenhum trade novo.")

        out.append("")
        out.append("**Por par (cumulativo):**")
        for p, (n, pnl) in sorted(cum["per_pair"].items(), key=lambda x: x[1][1]):
            out.append(f"- `{p}`: ${pnl:+.2f} ({n} trades)")

        out.append("")
        out.append("**Exit reasons:**")
        for r, n in cum["exit_reasons"].most_common():
            out.append(f"- `{r}`: {n}")

    out.append("")
    out.append("**Tunables atuais:**")
    for k, v in cfg.items():
        out.append(f"- `{k}` = {v}")

    out.append("")
    out.append("**Sugestões heurísticas:**")
    for s in sug:
        out.append(f"- {s}")

    out.append("\n---")
    return "\n".join(out) + "\n"


def main():
    state = load_state()
    open_t, closed_t = fetch_trades()
    log_st = parse_log_tail()
    cum, recent = compute(closed_t, state.get("last_trade_id", 0))
    sug = suggestions(cum)
    cfg = load_config_snapshot()
    report = render(open_t, cum, recent, sug, log_st["hold_latest"], cfg)

    if not OUT.exists():
        OUT.write_text(
            "# TwinPennies V4 — Hourly Evaluation Log\n\n"
            "Auto-gerado por `scripts/twin_pennies_hourly_eval.py` (cron, horário).\n"
            "Cada seção = um snapshot. Lê de baixo (mais novo) pra cima.\n"
            "Para revisar sugestões e ajustar a estratégia, abra o Claude e peça "
            "para analisar este arquivo.\n\n---\n"
        )
    with OUT.open("a") as f:
        f.write(report)

    if closed_t:
        state["last_trade_id"] = max(t["id"] for t in closed_t)
    state["last_run"] = NOW.isoformat()
    save_state(state)

    print(f"[{NOW.isoformat()}] open={len(open_t)} closed={len(closed_t)} -> {OUT}")


if __name__ == "__main__":
    main()
