#!/usr/bin/env python3
"""BetaV54 live dashboard — rich ANSI art, freqtrade API + log parsing.

Combines three sources:
    * Freqtrade REST API (open trades, closed trades, profit summary, balance)
    * Strategy log (V54 CYCLE / GROUPS / GATE lines — per-cycle decision state)
    * Local SQLite (fallback if API unavailable)

Usage:
    /root/freqtrade/scripts/monitor_beta_v54.py
    /root/freqtrade/scripts/monitor_beta_v54.py --log /path/to/beta_v54.log --refresh 5
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth
from rich.align import Align
from rich.box import HEAVY, ROUNDED, SIMPLE
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ─── Config ───────────────────────────────────────────────────────────────
API_URL = "http://localhost:8083/api/v1"
AUTH = HTTPBasicAuth("freqtrader", "freqtrader")
DEFAULT_LOG = "/root/freqtrade/logs/beta_v54.log"
DEFAULT_REFRESH = 5

# Unicode blocks for sparklines (8 levels)
BLOCKS = "▁▂▃▄▅▆▇█"

# Z-score thresholds (mirror v54_config.json)
Z_ENTRY = 1.5  # spread z_entry
PAIR_Z = 0.9   # pair z_entry

console = Console()


# ─── Data fetchers ────────────────────────────────────────────────────────

def api(endpoint: str, **params) -> Optional[dict]:
    try:
        r = requests.get(f"{API_URL}/{endpoint}", auth=AUTH, params=params, timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@dataclass
class CycleRow:
    pair: str
    groups: str
    spread_a: float
    spread_b: float
    pair_z: float
    regime: str
    vok: int
    rok: int
    sok: int
    sig: str
    timestamp: str = ""


@dataclass
class GroupSnapshot:
    name: str
    open: int = 0
    cap: int = 1
    cooldown: str = "-"


@dataclass
class BotState:
    # Cycle data (from log)
    cycles: dict[str, CycleRow] = field(default_factory=dict)
    last_cycle_ts: str = ""
    btc_mom: float = 0.0
    btc_atrz: float = 0.0
    btc_flags: dict[str, int] = field(default_factory=dict)
    regime: str = "?"
    z_threshold: float = Z_ENTRY
    dd_pct: float = 0.0
    half_life: str = "-"
    spread_a: float = 0.0
    spread_b: float = 0.0
    # Group state (from log)
    groups: list[GroupSnapshot] = field(default_factory=list)
    total_open: int = 0
    total_max: int = 3
    # API data
    open_trades: list[dict] = field(default_factory=list)
    closed_trades: list[dict] = field(default_factory=list)
    profit: Optional[dict] = None
    balance: Optional[dict] = None
    bot_state: str = "?"
    # Recent events (from log)
    gate_events: list[str] = field(default_factory=list)
    close_events: list[str] = field(default_factory=list)


# ─── Log parser ───────────────────────────────────────────────────────────

CYCLE_RX = re.compile(
    r"V54 CYCLE (\S+) grp=(\S+) spread\[A=([+-]?[\d.]+) B=([+-]?[\d.]+)\] "
    r"pz=([+-]?[\d.]+) regime=(\w+) vok=(\d+) rok=(\d+) sok=(\d+) "
    r"btc\[mom=([+-]?[\d.]+) atrz=([+-]?[\d.]+) p=(\d) d=(\d) hv=(\d) ve=(\d)\]"
    r"(?: zth=([\d.]+))?(?: dd=([\d.]+)%)?(?: hl=(\d+))?(?: sig=(\w+))?"
)
GROUPS_RX = re.compile(
    r"V54 GROUPS open=(\d+)/(\d+)(.*?)$"
)
GROUP_PART_RX = re.compile(
    r"\[(\w+): (\d+)/(\d+) cd=([^\]]*)\]"
)


def parse_log(path: str, tail_n: int = 600) -> BotState:
    """Pull the most recent CYCLE/GROUPS/GATE/close events from the log file."""
    state = BotState()
    p = Path(path)
    if not p.exists():
        return state

    # Read tail efficiently
    with p.open("rb") as f:
        try:
            f.seek(0, 2)
            size = f.tell()
            block = min(size, 200 * 1024)
            f.seek(size - block)
            data = f.read().decode("utf-8", errors="replace")
        except Exception:
            data = p.read_text(errors="replace")

    lines = data.splitlines()[-tail_n:]

    cycles: dict[str, CycleRow] = {}
    last_ts = ""
    last_groups = None
    gates = deque(maxlen=6)
    closes = deque(maxlen=6)

    for line in lines:
        if "V54 CYCLE" in line:
            m = CYCLE_RX.search(line)
            if not m:
                continue
            ts = line.split(",")[0]
            last_ts = ts
            pair_full = m.group(1)
            pair = pair_full.replace("/USDC:USDC", "")
            cycles[pair] = CycleRow(
                pair=pair,
                groups=m.group(2),
                spread_a=float(m.group(3)),
                spread_b=float(m.group(4)),
                pair_z=float(m.group(5)),
                regime=m.group(6),
                vok=int(m.group(7)),
                rok=int(m.group(8)),
                sok=int(m.group(9)),
                sig=(m.group(19) or "none"),
                timestamp=ts,
            )
            # Take shared fields from any cycle (they're identical for the cycle)
            state.btc_mom = float(m.group(10))
            state.btc_atrz = float(m.group(11))
            state.btc_flags = {
                "pump": int(m.group(12)),
                "dump": int(m.group(13)),
                "hvol": int(m.group(14)),
                "ve": int(m.group(15)),
            }
            state.regime = m.group(6)
            if m.group(16):
                state.z_threshold = float(m.group(16))
            if m.group(17):
                state.dd_pct = float(m.group(17))
            if m.group(18):
                state.half_life = m.group(18)
            state.spread_a = float(m.group(3))
            state.spread_b = float(m.group(4))
        elif "V54 GROUPS" in line:
            last_groups = line
        elif "V54 GATE" in line:
            gates.append(line)
        elif "V54 LOSS" in line or "V54 COOLDOWN" in line:
            closes.append(line)
        elif "'profit_ratio'" in line and "'exit_reason'" in line:
            closes.append(line)

    state.cycles = cycles
    state.last_cycle_ts = last_ts
    state.gate_events = list(gates)
    state.close_events = list(closes)

    if last_groups:
        gm = GROUPS_RX.search(last_groups)
        if gm:
            state.total_open = int(gm.group(1))
            state.total_max = int(gm.group(2))
            for part in GROUP_PART_RX.finditer(gm.group(3)):
                state.groups.append(
                    GroupSnapshot(
                        name=part.group(1),
                        open=int(part.group(2)),
                        cap=int(part.group(3)),
                        cooldown=part.group(4),
                    )
                )

    return state


# ─── Rendering helpers ────────────────────────────────────────────────────

def sparkline(values: list[float], width: int = 50) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return BLOCKS[3] * min(len(values), width)
    if len(values) > width:
        step = len(values) / width
        vals = [values[int(i * step)] for i in range(width)]
    else:
        vals = values
    return "".join(BLOCKS[min(7, int((v - lo) / (hi - lo) * 7))] for v in vals)


def color_pnl(pct: float) -> str:
    if pct > 0:
        return "bright_green"
    if pct < 0:
        return "red"
    return "white"


def spread_bar(value: float, threshold: float, width: int = 36) -> Text:
    """Centered bar over [-3, +3] with markers at 0 and ±threshold."""
    lo, hi = -3.0, 3.0
    v = max(lo, min(hi, value))
    pos = int((v - lo) / (hi - lo) * (width - 1))
    zero = int((0 - lo) / (hi - lo) * (width - 1))
    tp = int((threshold - lo) / (hi - lo) * (width - 1))
    tn = int((-threshold - lo) / (hi - lo) * (width - 1))

    absv = abs(value)
    if absv >= threshold:
        marker_style = "bold red"
    elif absv >= 0.7 * threshold:
        marker_style = "bold yellow"
    else:
        marker_style = "dim"

    t = Text()
    t.append("[", style="dim")
    for i in range(width):
        if i == pos:
            t.append("█", style=marker_style)
        elif i == zero:
            t.append("│", style="bright_cyan")
        elif i == tp or i == tn:
            t.append("┊", style="magenta")
        else:
            t.append("─", style="dim")
    t.append("]", style="dim")
    return t


def pair_z_bar(value: float, threshold: float = PAIR_Z, width: int = 22) -> Text:
    lo, hi = -3.0, 3.0
    v = max(lo, min(hi, value))
    pos = int((v - lo) / (hi - lo) * (width - 1))
    zero = int((0 - lo) / (hi - lo) * (width - 1))
    tp = int((threshold - lo) / (hi - lo) * (width - 1))
    tn = int((-threshold - lo) / (hi - lo) * (width - 1))

    absv = abs(value)
    style = "dim"
    if absv >= threshold:
        style = "bright_green"
    elif absv >= 0.7 * threshold:
        style = "yellow"

    t = Text()
    t.append("[", style="dim")
    for i in range(width):
        if i == pos:
            t.append("▒", style=style)
        elif i == zero:
            t.append("│", style="bright_cyan")
        elif i == tp or i == tn:
            t.append("┊", style="magenta")
        else:
            t.append("─", style="dim")
    t.append("]", style="dim")
    return t


def fill_bar(filled: int, total: int, width: int = 12) -> Text:
    t = Text()
    f = min(filled, total)
    for _ in range(f):
        t.append("█", style="bright_green")
    for _ in range(total - f):
        t.append("░", style="dim")
    if total > width:
        return t  # avoid huge bars
    return t


# ─── Panels ───────────────────────────────────────────────────────────────

REGIME_STYLES = {
    "range": ("RANGE", "black on bright_green"),
    "trend": ("TREND", "black on yellow"),
    "consol": ("CONSOL", "white on red"),
}


def header_panel(state: BotState) -> Panel:
    rg = state.regime or "?"
    label, style = REGIME_STYLES.get(rg, ("???", "dim"))

    bot_status = state.bot_state
    bot_style = "bright_green" if bot_status == "running" else "yellow"

    bal_txt = "?"
    pnl_txt = "?"
    if state.balance:
        bal = state.balance.get("total", 0)
        start = state.balance.get("starting_capital", 0)
        pnl_abs = bal - start if start else 0
        pnl_pct = (pnl_abs / start * 100) if start else 0
        bal_txt = f"${bal:,.2f}  (start ${start:,.2f})"
        sign = "+" if pnl_abs >= 0 else ""
        pnl_style = color_pnl(pnl_abs)
        pnl_txt = f"[{pnl_style}]{sign}${pnl_abs:,.2f} ({sign}{pnl_pct:.2f}%)[/{pnl_style}]"

    t = Text()
    t.append(" Regime ", style="dim")
    t.append(f" {label} ", style=style)
    t.append(f"   BTC mom=", style="dim")
    t.append(f"{state.btc_mom:+.2f}", style="bold")
    t.append("  atrz=", style="dim")
    t.append(f"{state.btc_atrz:+.2f}", style="bold")
    flags = state.btc_flags
    t.append("   flags[", style="dim")
    for k in ("pump", "dump", "hvol", "ve"):
        v = flags.get(k, 0)
        s = "red" if v else "dim"
        t.append(f"{k[0]}=", style="dim")
        t.append(f"{v}", style=s)
        t.append(" ", style="dim")
    t.append("]\n", style="dim")
    t.append(" Open ", style="dim")
    t.append(f"{state.total_open}/{state.total_max}", style="bold")
    t.append("   z_entry=±", style="dim")
    t.append(f"{state.z_threshold:.2f}", style="bold")
    t.append("   DD=", style="dim")
    t.append(f"{state.dd_pct:.1f}%", style="bold")
    t.append("   half_life=", style="dim")
    t.append(f"{state.half_life}", style="bold")
    t.append("   Bot ", style="dim")
    t.append(bot_status, style=bot_style)
    t.append("\n Balance ", style="dim")
    t.append(bal_txt, style="bold bright_white")
    t.append("   P&L ", style="dim")
    t.append_text(Text.from_markup(pnl_txt))

    return Panel(
        t,
        title="[bold cyan]BetaV54 Monitor[/]",
        subtitle=f"[dim]{state.last_cycle_ts}[/]",
        box=HEAVY,
        border_style="cyan",
    )


def groups_panel(state: BotState) -> Panel:
    descriptions = {
        "A": "XRP vs SOL+LINK — LONG-only",
        "B": "BTC+SOL vs ETH — LONG+SHORT",
    }
    spreads = {"A": state.spread_a, "B": state.spread_b}

    rows = []
    for g in state.groups or [GroupSnapshot("A"), GroupSnapshot("B")]:
        desc = descriptions.get(g.name, "")
        sp = spreads.get(g.name, 0.0)

        header = Text()
        header.append("▣ GROUP ", style="bold blue")
        header.append(g.name, style="bold bright_white on blue")
        header.append(f"  {desc}\n", style="dim")

        body = Text()
        body.append("  trades  ", style="dim")
        body.append_text(fill_bar(g.open, g.cap))
        body.append(f"  {g.open}/{g.cap}", style="bold")
        body.append(f"    cooldown: ", style="dim")
        cd_style = "yellow" if g.cooldown != "-" else "dim"
        body.append(f"{g.cooldown}\n", style=cd_style)
        body.append("  spread_z = ", style="dim")
        body.append(f"{sp:+.2f}  ", style="bold")
        body.append_text(spread_bar(sp, state.z_threshold))
        body.append("   ", style="")
        body.append(f"-3 … 0 … +3 (┊=±{state.z_threshold:.2f})", style="dim")

        rows.append(Group(header, body))

    inner = Group(*[Group(r, Text("")) for r in rows]) if rows else Text("(no groups)")
    return Panel(inner, title="[bold blue]Groups[/]", box=ROUNDED, border_style="blue")


def pairs_panel(state: BotState) -> Panel:
    table = Table(box=SIMPLE, show_edge=False, padding=(0, 1), expand=False)
    table.add_column("Pair", style="bold", width=6)
    table.add_column("Grp", width=4)
    table.add_column("pair_z", justify="right", width=7)
    table.add_column("bar (±0.9)", width=24)
    table.add_column("vok", justify="center", width=3)
    table.add_column("rok", justify="center", width=3)
    table.add_column("sok", justify="center", width=3)
    table.add_column("regime", style="dim", width=7)
    table.add_column("sig", justify="center", width=7)

    if not state.cycles:
        table.add_row("[dim](waiting for cycle data…)[/]", "", "", "", "", "", "", "", "")
    else:
        order = ["BTC", "ETH", "SOL", "XRP", "LINK", "DOGE", "SUI", "ONDO", "TON"]
        sorted_pairs = sorted(state.cycles.keys(), key=lambda p: order.index(p) if p in order else 99)
        for pair in sorted_pairs:
            c = state.cycles[pair]
            sig_txt = Text(c.sig.center(5), style="dim")
            if c.sig == "LONG":
                sig_txt = Text(" LONG ", style="black on bright_green")
            elif c.sig == "SHORT":
                sig_txt = Text(" SHORT", style="white on red")
            else:
                sig_txt = Text("  -  ", style="dim")
            table.add_row(
                pair,
                c.groups,
                f"{c.pair_z:+.2f}",
                pair_z_bar(c.pair_z),
                Text("1", style="bright_green") if c.vok else Text("0", style="red"),
                Text("1", style="bright_green") if c.rok else Text("0", style="red"),
                Text("1", style="bright_green") if c.sok else Text("0", style="red"),
                c.regime,
                sig_txt,
            )

    return Panel(table, title="[bold cyan]Pairs[/]", box=ROUNDED, border_style="cyan")


def open_trades_panel(state: BotState) -> Panel:
    table = Table(box=SIMPLE, show_edge=False, padding=(0, 1), expand=False)
    table.add_column("ID", justify="right", width=3)
    table.add_column("Pair", style="bold", width=6)
    table.add_column("Side", width=5)
    table.add_column("Lev", justify="right", width=5)
    table.add_column("Stake$", justify="right", width=8)
    table.add_column("Entry", justify="right", width=9)
    table.add_column("Curr", justify="right", width=9)
    table.add_column("Profit%", justify="right", width=8)
    table.add_column("PnL$", justify="right", width=8)
    table.add_column("Age", justify="right", width=8)
    table.add_column("Tag", width=18)

    trades = state.open_trades
    if not trades:
        return Panel(
            Align.center(Text("(no open trades)", style="dim"), vertical="middle"),
            title="[bold green]Open Trades (0)[/]",
            box=ROUNDED, border_style="green", height=4,
        )
    if False:
        for t in trades:
            pair = t.get("pair", "?").replace("/USDC:USDC", "")
            side = "SHORT" if t.get("is_short") else "LONG"
            side_style = "red" if t.get("is_short") else "bright_green"
            pct = t.get("profit_pct", 0.0) or 0.0
            abs_pnl = t.get("profit_abs", 0.0) or 0.0
            pnl_style = color_pnl(abs_pnl)
            try:
                open_dt = datetime.fromisoformat(t["open_date"].replace("Z", "+00:00"))
                if open_dt.tzinfo is None:
                    open_dt = open_dt.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - open_dt
                hours = age.total_seconds() / 3600
                age_txt = f"{hours:.1f}h" if hours < 24 else f"{hours/24:.1f}d"
            except Exception:
                age_txt = "?"
            table.add_row(
                str(t.get("trade_id", "?")),
                pair,
                Text(side, style=side_style),
                f"{t.get('leverage', 1):.1f}x",
                f"${t.get('stake_amount', 0):.2f}",
                f"{t.get('open_rate', 0):.4f}",
                f"{t.get('current_rate', 0):.4f}",
                Text(f"{pct:+.2f}%", style=pnl_style),
                Text(f"${abs_pnl:+.2f}", style=pnl_style),
                age_txt,
                (t.get("enter_tag") or "")[:18],
            )

    return Panel(table, title=f"[bold green]Open Trades ({len(trades)})[/]",
                 box=ROUNDED, border_style="green")


def equity_curve_panel(state: BotState) -> Panel:
    """Cumulative profit_abs across closed trades → sparkline + summary."""
    trades = state.closed_trades or []
    closed = [t for t in trades if t.get("close_date")]
    closed.sort(key=lambda t: t.get("close_date") or "")

    if not closed:
        body = Align.center(Text("(no closed trades yet — equity curve will appear here)",
                                  style="dim"), vertical="middle")
        return Panel(body, title="[bold magenta]Equity Curve[/]",
                     box=ROUNDED, border_style="magenta", height=6)

    starting = (state.balance or {}).get("starting_capital", 100.0)
    cum = []
    bal = starting
    for t in closed:
        bal += t.get("profit_abs", 0.0) or 0.0
        cum.append(bal)

    spark = sparkline(cum, width=60)
    lo, hi = min(cum), max(cum)
    final = cum[-1]
    pnl_abs = final - starting
    pnl_pct = (pnl_abs / starting * 100) if starting > 0 else 0
    pnl_style = color_pnl(pnl_abs)
    sign = "+" if pnl_abs >= 0 else ""

    profit = state.profit or {}
    wins = profit.get("winning_trades", 0)
    losses = profit.get("losing_trades", 0)
    total = wins + losses
    win_rate = (wins / total * 100) if total else 0.0
    best = profit.get("best_pair_profit_ratio", 0) * 100
    worst = profit.get("worst_pair_profit_ratio", 0) * 100

    body = Text()
    body.append(f" ${starting:,.2f} ", style="dim")
    body.append(spark, style=pnl_style)
    body.append(f" ${final:,.2f}", style="bold bright_white")
    body.append(f"   range ${lo:,.2f}…${hi:,.2f}\n", style="dim")
    body.append(" P&L  ", style="dim")
    body.append(f"{sign}${pnl_abs:,.2f}  ({sign}{pnl_pct:.2f}%)", style=f"bold {pnl_style}")
    body.append("    trades ", style="dim")
    body.append(f"{total}", style="bold")
    body.append("    win-rate ", style="dim")
    wr_style = "bright_green" if win_rate >= 50 else "yellow" if win_rate >= 40 else "red"
    body.append(f"{win_rate:.1f}%", style=f"bold {wr_style}")
    body.append("    best/worst ", style="dim")
    body.append(f"+{best:.2f}% / {worst:.2f}%", style="dim")

    return Panel(body, title="[bold magenta]Equity Curve[/]",
                 box=ROUNDED, border_style="magenta")


def events_panel(state: BotState) -> Panel:
    """Recent GATE + close events, mixed chronologically."""
    table = Table(box=SIMPLE, show_edge=False, padding=(0, 1), expand=False)
    table.add_column("Time", style="dim", width=8)
    table.add_column("Type", width=8)
    table.add_column("Detail")

    events = []
    for line in state.gate_events:
        ts = ""
        m = re.search(r"(\d{2}:\d{2}:\d{2})", line)
        if m:
            ts = m.group(1)
        if "ACCEPT" in line:
            m2 = re.search(r"V54 GATE (\S+) side=(\S+).*ACCEPT (.*)", line)
            if m2:
                events.append((ts, "ACCEPT",
                               f"{m2.group(1).replace('/USDC:USDC', '')} {m2.group(2)} → {m2.group(3)}",
                               "bright_green"))
        else:
            m2 = re.search(r"V54 GATE (\S+) side=(\S+).*REJECT (.*)", line)
            if m2:
                events.append((ts, "REJECT",
                               f"{m2.group(1).replace('/USDC:USDC', '')} {m2.group(2)} ✗ {m2.group(3)}",
                               "red"))

    for line in state.close_events:
        ts = ""
        m = re.search(r"(\d{2}:\d{2}:\d{2})", line)
        if m:
            ts = m.group(1)
        if "V54 LOSS" in line:
            m2 = re.search(r"V54 LOSS: (\S+) ([+-]?[\d.]+)% \(([^)]+)\)", line)
            if m2:
                events.append((ts, "LOSS",
                               f"{m2.group(1).replace('/USDC:USDC', '')} {m2.group(2)}% ({m2.group(3)})",
                               "red"))
        elif "V54 COOLDOWN" in line:
            m2 = re.search(r"group (\w+) until (\S+)", line)
            if m2:
                events.append((ts, "COOLDOWN",
                               f"group {m2.group(1)} until {m2.group(2)}",
                               "yellow"))
        elif "'profit_ratio'" in line:
            mp = re.search(r"'profit_ratio': ([+-]?[\d.e-]+)", line)
            mr = re.search(r"'exit_reason': '([^']+)'", line)
            mb = re.search(r"'base_currency': '([^']+)'", line)
            fm = "[final]" if "'is_final_exit': True" in line else "[part]"
            if mp and mb:
                pct = float(mp.group(1)) * 100
                style = "bright_green" if pct > 0 else "red"
                events.append((ts, "CLOSE",
                               f"{mb.group(1)} {pct:+.2f}% {fm} reason={mr.group(1) if mr else '?'}",
                               style))

    events.sort(key=lambda e: e[0])
    events = events[-8:]

    if not events:
        return Panel(
            Align.center(Text("(no events yet — waiting for first GATE / close)",
                              style="dim"), vertical="middle"),
            title="[bold yellow]Recent Events[/]",
            box=ROUNDED, border_style="yellow", height=4,
        )
    if False:
        for ts, kind, detail, style in events:
            table.add_row(ts, Text(kind, style=style), detail)

    return Panel(table, title="[bold yellow]Recent Events[/]",
                 box=ROUNDED, border_style="yellow")


# ─── Layout ───────────────────────────────────────────────────────────────

def footer_panel(state: BotState) -> Panel:
    now = datetime.now().strftime("%H:%M:%S")
    next_cycle = "?"
    if state.last_cycle_ts:
        try:
            last = datetime.strptime(state.last_cycle_ts, "%Y-%m-%d %H:%M:%S")
            nxt = last.replace(minute=(last.minute // 5 + 1) * 5 % 60, second=1)
            if nxt < last:
                nxt = nxt.replace(hour=(last.hour + 1) % 24)
            next_cycle = nxt.strftime("%H:%M:%S")
        except Exception:
            pass
    t = Text()
    t.append("⏱  refresh: ", style="dim")
    t.append(now, style="bold bright_white")
    t.append("   last cycle: ", style="dim")
    t.append(state.last_cycle_ts.split(" ")[-1] if state.last_cycle_ts else "?",
             style="bold bright_white")
    t.append("   next cycle ~", style="dim")
    t.append(next_cycle, style="bold yellow")
    t.append("   (CYCLE fires every 5min; dashboard re-polls API every 5s)",
             style="dim italic")
    return Panel(t, box=ROUNDED, border_style="dim")


def build_layout(state: BotState) -> Layout:
    layout = Layout()
    n_trades = len(state.open_trades)
    n_events = len(state.gate_events) + len(state.close_events)

    trades_size = 4 if n_trades == 0 else min(4 + n_trades, 8)
    events_size = 4 if n_events == 0 else min(4 + n_events, 12)

    layout.split_column(
        Layout(header_panel(state), name="header", size=6),
        Layout(groups_panel(state), name="groups", size=13),
        Layout(pairs_panel(state), name="pairs", size=10),
        Layout(open_trades_panel(state), name="trades", size=trades_size),
        Layout(equity_curve_panel(state), name="equity", size=5),
        Layout(events_panel(state), name="events", size=events_size),
        Layout(footer_panel(state), name="footer", size=3),
    )
    return layout


# ─── Main loop ────────────────────────────────────────────────────────────

def fetch_state(log_path: str) -> BotState:
    state = parse_log(log_path)
    state.open_trades = api("status") or []
    state.profit = api("profit")
    state.closed_trades = api("trades", limit=200) or {}
    if isinstance(state.closed_trades, dict):
        state.closed_trades = state.closed_trades.get("trades", [])
    bal = api("balance")
    state.balance = bal
    show = api("show_config")
    if show:
        state.bot_state = show.get("state", "?").lower()
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--refresh", type=int, default=DEFAULT_REFRESH)
    ap.add_argument("--once", action="store_true", help="Render once and exit")
    args = ap.parse_args()

    if args.once:
        state = fetch_state(args.log)
        console.print(build_layout(state))
        return

    with Live(refresh_per_second=2, screen=True) as live:
        while True:
            try:
                state = fetch_state(args.log)
                live.update(build_layout(state))
            except KeyboardInterrupt:
                break
            except Exception as e:
                live.update(Panel(f"[red]Error: {e}[/]"))
            time.sleep(args.refresh)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
