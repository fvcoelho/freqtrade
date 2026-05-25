#!/usr/bin/env python3
"""TwinPennies V4 live dashboard — full decision-pipeline view.

Shows EVERY variable that affects pair selection and trade decisions:

  1. BTC trend gate — pump/dump/high_vol/mom (blocks entries globally)
  2. Pair z-spectrum — basket_z per pair, vol_ok gate, signal status
  3. Twin matchmaker — current cross-product of opposite-direction candidates
  4. Open trades — full decision state: entry_z, current_z, delta, scale_count,
     distance to each exit trigger (winner_revert / time_stop / loser_close / safety)
  5. Recent events — last N EVAL/SCALE/CLOSE/ENTRY events from log
  6. Config snapshot — live values of every knob

Sources:
  * freqtrade REST API (open trades, profit, balance)
  * twin_pennies.log (TICK / HOLD / EVAL / SCALE / ENTRY / CLOSE lines)
  * twin_pennies_config.json (live config)

Usage:
    /root/freqtrade/scripts/monitor_twin_pennies.py
    /root/freqtrade/scripts/monitor_twin_pennies.py --refresh 3
    /root/freqtrade/scripts/monitor_twin_pennies.py --log /path/to/twin_pennies.log
"""
from __future__ import annotations

import argparse
import json
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
from rich.box import HEAVY, ROUNDED, SIMPLE
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ─── Config ───────────────────────────────────────────────────────────────
API_URL = "http://localhost:8083/api/v1"
AUTH = HTTPBasicAuth("freqtrader", "freqtrader")
DEFAULT_LOG = "/root/freqtrade/twin_pennies.log"
DEFAULT_CONFIG = "/root/freqtrade/user_data/strategies/twin_pennies_config.json"
DEFAULT_REFRESH = 5
EVENTS_KEEP = 12
LOG_TAIL_BYTES = 800_000  # ~800KB tail per refresh

console = Console()


# ─── Regex parsers ────────────────────────────────────────────────────────
TS_RX = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"

TICK_RX = re.compile(
    TS_RX + r".*?TICK z=\[(.*?)\] \| BTC mom=(-?[\d.]+) atr_z=(-?[\d.]+) "
    r"pump=(True|False) dump=(True|False) chaos=(True|False) \| "
    r"signals=(\S+) \| open=(\d+)/(\d+)"
)
TICK_Z_RX = re.compile(r"(\w+)=([+-][\d.]+)")

HOLD_RX = re.compile(
    TS_RX + r".*?HOLD (\S+) ([LS])\[([WL?])\+S(\d+)\] @(\d+)c \| "
    r"z=(-?[\d.]+) entry_z=(-?[\d.]+) delta=(-?[\d.]+) \| "
    r"profit=(-?[\d.]+)% peak=(-?[\d.]+)% \$(-?[\d.]+) \| "
    r"btc_mom=(-?[\d.]+) \| time_left=(-?[\d.]+)c exit_z=(-?[\d.]+)"
)

EVAL_RX = re.compile(
    TS_RX + r".*?EVAL (\S+) ([LS])\[([WL])\] profit=(-?[\d.]+)% z_entry=(-?[\d.]+)"
)

SCALE_RX = re.compile(
    TS_RX + r".*?SCALE\[(\d+)/(\d+)\] (\S+) \| z: (-?[\d.]+) -> (-?[\d.]+) "
    r"\(delta=(-?[\d.]+) >= ([\d.]+)\) \| profit=(-?[\d.]+)% \| \+\$([\d.]+)"
)

ENTRY_CONFIRM_RX = re.compile(
    TS_RX + r".*?ENTRY CONFIRM (\S+) (\w+) z=(-?[\d.]+) \| twin=(\S+) z=(-?[\d.]+)"
)

ENTRY_REJECT_RX = re.compile(
    TS_RX + r".*?ENTRY REJECT (\S+) (\w+).*?— (.+)$"
)

CLOSE_RX = re.compile(
    TS_RX + r".*?CLOSE (\S+) ([LS])\[([WL?])(?:\+S(\d+))?\] "
    r"profit=(-?[\d.]+)% \$([\d.]+) lev=(-?[\d.]+)x \| (\S+)"
)


# ─── Data classes ─────────────────────────────────────────────────────────
@dataclass
class BTCState:
    mom: float = 0.0
    atr_z: float = 0.0
    pump: bool = False
    dump: bool = False
    high_vol: bool = False
    ts: str = "-"


@dataclass
class PairState:
    pair: str
    z: float = 0.0
    in_position: bool = False
    in_position_side: str = ""  # "long" or "short"
    ts: str = "-"
    # vol_ok per pair isn't in TICK; inferred from signals list
    in_signals: bool = False


@dataclass
class TradeDecision:
    trade_id: int
    pair: str
    side: str  # "long" or "short"
    age_min: int
    age_candles: float
    stake: float
    profit_pct: float
    peak_pct: float
    entry_z: float
    current_z: float
    z_delta: float
    scale_count: int
    max_scales: int
    is_winner: Optional[bool]
    evaluated: bool
    btc_mom: float
    time_left_candles: float
    winner_exit_z: float


@dataclass
class LogEvent:
    ts: str
    kind: str  # EVAL/SCALE/ENTRY-CONFIRM/ENTRY-REJECT/CLOSE
    summary: str
    color: str = "white"


@dataclass
class State:
    btc: BTCState = field(default_factory=BTCState)
    pairs: dict[str, PairState] = field(default_factory=dict)
    last_tick_ts: str = "-"
    last_tick_open: tuple = (0, 0)  # (open, max)
    last_signals: list = field(default_factory=list)
    trades: list[TradeDecision] = field(default_factory=list)
    events: deque = field(default_factory=lambda: deque(maxlen=EVENTS_KEEP))
    api_status: list = field(default_factory=list)
    api_count: dict = field(default_factory=dict)
    api_profit: dict = field(default_factory=dict)
    api_balance: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    api_ok: bool = True


# ─── API + log + config fetchers ──────────────────────────────────────────
def api(endpoint: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_URL}/{endpoint}", auth=AUTH, timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def load_config(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def tail_log(path: str, n_bytes: int = LOG_TAIL_BYTES) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > n_bytes:
            f.seek(size - n_bytes)
            f.readline()  # drop partial line
        data = f.read()
    return data.decode("utf-8", errors="replace").splitlines()


def parse_logs(lines: list[str], state: State, basket_pairs: list[str], entry_z: float):
    """Walk log lines and rebuild state from TICK/HOLD/EVAL/SCALE/CLOSE/ENTRY."""
    latest_tick = None
    hold_by_pair: dict[str, dict] = {}
    events: list[LogEvent] = []

    for line in lines:
        # Recent events worth showing (newest last)
        m = EVAL_RX.search(line)
        if m:
            ts, pair, side, lbl, profit, z_entry = m.groups()
            color = "green" if lbl == "W" else "red"
            sym = pair.split("/")[0]
            events.append(LogEvent(
                ts=ts[-8:], kind="EVAL",
                summary=f"{sym} {side}[{lbl}] {profit}% z_e={z_entry}",
                color=color,
            ))
            continue
        m = SCALE_RX.search(line)
        if m:
            ts, n, mx, pair, z0, z1, delta, thr, profit, add = m.groups()
            sym = pair.split("/")[0]
            events.append(LogEvent(
                ts=ts[-8:], kind="SCALE",
                summary=f"{sym} [{n}/{mx}] z {z0}→{z1} (Δ{delta}) +${add}",
                color="cyan",
            ))
            continue
        m = ENTRY_CONFIRM_RX.search(line)
        if m:
            ts, pair, side, z, twin, twin_z = m.groups()
            sym = pair.split("/")[0]
            twin_sym = twin.split("/")[0]
            events.append(LogEvent(
                ts=ts[-8:], kind="ENTER",
                summary=f"{sym} {side[:1].upper()} z={z} ⇆ {twin_sym} z={twin_z}",
                color="bright_green" if side == "long" else "bright_red",
            ))
            continue
        m = ENTRY_REJECT_RX.search(line)
        if m:
            ts, pair, side, reason = m.groups()
            sym = pair.split("/")[0]
            # Short reason — strip trailing details
            short_reason = reason.split("—")[0].strip()[:35]
            events.append(LogEvent(
                ts=ts[-8:], kind="REJECT",
                summary=f"{sym} {side[:1].upper()} — {short_reason}",
                color="dim yellow",
            ))
            continue
        m = CLOSE_RX.search(line)
        if m:
            ts, pair, side, lbl, sc, profit, stake, lev, reason = m.groups()
            sym = pair.split("/")[0]
            color = "bold green" if float(profit) > 0 else "bold red"
            sc_str = f"+S{sc}" if sc else ""
            events.append(LogEvent(
                ts=ts[-8:], kind="CLOSE",
                summary=f"{sym} {side}[{lbl}{sc_str}] {profit}% ${stake} | {reason}",
                color=color,
            ))
            continue

        # Per-cycle state (overwrites previous)
        m = TICK_RX.search(line)
        if m:
            latest_tick = m
            continue
        m = HOLD_RX.search(line)
        if m:
            (ts, pair, side, lbl, sc, age, z, ez, dz,
             profit, peak, stake, btc_mom, t_left, wez) = m.groups()
            hold_by_pair[pair] = {
                "ts": ts,
                "pair": pair,
                "side": "short" if side == "S" else "long",
                "lbl": lbl,
                "sc": int(sc),
                "age": float(age),
                "z": float(z),
                "entry_z": float(ez),
                "delta": float(dz),
                "profit": float(profit),
                "peak": float(peak),
                "stake": float(stake),
                "btc_mom": float(btc_mom),
                "t_left": float(t_left),
                "wez": float(wez),
            }
            continue

    # Keep newest events (already in chronological order)
    state.events = deque(events[-EVENTS_KEEP:], maxlen=EVENTS_KEEP)

    # Apply latest TICK
    state.pairs = {}
    if latest_tick:
        (ts, z_str, btc_mom, btc_atrz, pump, dump, chaos,
         signals, n_open, n_max) = latest_tick.groups()
        state.btc = BTCState(
            mom=float(btc_mom),
            atr_z=float(btc_atrz),
            pump=pump == "True",
            dump=dump == "True",
            high_vol=chaos == "True",
            ts=ts[-8:],
        )
        state.last_tick_ts = ts
        state.last_tick_open = (int(n_open), int(n_max))
        signal_set = set(signals.split(",")) if signals != "none" else set()
        state.last_signals = list(signal_set)
        # Parse z list
        z_map = {}
        for m in TICK_Z_RX.finditer(z_str):
            sym, val = m.group(1), float(m.group(2))
            z_map[sym] = val
        # Build PairState for every tradeable basket pair
        for p in basket_pairs:
            sym = p.split("/")[0]
            if sym == "BTC":  # BTC is btc_ref, not tradeable
                continue
            state.pairs[p] = PairState(
                pair=p,
                z=z_map.get(sym, 0.0),
                ts=ts[-8:],
                in_signals=sym in signal_set,
            )

    # Attach HOLD data to TradeDecision state
    trades: list[TradeDecision] = []
    for tid, h in enumerate(hold_by_pair.values()):
        # Find matching API trade for trade_id, max_scales, etc.
        api_match = next((t for t in state.api_status if t["pair"] == h["pair"]), None)
        if not api_match:
            continue
        trades.append(TradeDecision(
            trade_id=api_match["trade_id"],
            pair=h["pair"],
            side=h["side"],
            age_min=int(h["age"] * 5),
            age_candles=h["age"],
            stake=h["stake"],
            profit_pct=h["profit"],
            peak_pct=h["peak"],
            entry_z=h["entry_z"],
            current_z=h["z"],
            z_delta=h["delta"],
            scale_count=h["sc"],
            max_scales=int(state.config.get("twin", {}).get("max_scale_times", 1)),
            is_winner=(h["lbl"] == "W") if h["lbl"] != "?" else None,
            evaluated=h["lbl"] != "?",
            btc_mom=h["btc_mom"],
            time_left_candles=h["t_left"],
            winner_exit_z=h["wez"],
        ))
    state.trades = trades

    # Mark which pairs are in positions
    for t in state.trades:
        if t.pair in state.pairs:
            state.pairs[t.pair].in_position = True
            state.pairs[t.pair].in_position_side = t.side


# ─── Visual helpers ───────────────────────────────────────────────────────
def z_bar(z: float, threshold: float, width: int = 21) -> Text:
    """Visual -3 ... 0 ... +3 bar with marker at z and threshold lines at ±threshold."""
    half = width // 2
    pos = max(-3.0, min(3.0, z))
    idx = int(round(pos / 3.0 * half)) + half
    th_idx_pos = int(round(threshold / 3.0 * half)) + half
    th_idx_neg = int(round(-threshold / 3.0 * half)) + half

    t = Text()
    for i in range(width):
        if i == idx:
            if z > threshold:
                t.append("●", style="bold red")
            elif z < -threshold:
                t.append("●", style="bold green")
            else:
                t.append("●", style="bold white")
        elif i == half:
            t.append("│", style="dim")
        elif i == th_idx_pos or i == th_idx_neg:
            t.append("┊", style="dim yellow")
        elif (th_idx_neg < i < th_idx_pos):
            t.append("·", style="dim")
        else:
            t.append("·", style="dim")
    return t


def flag(value: bool, true_label: str = "ON", false_label: str = "off",
         true_style: str = "bold red", false_style: str = "dim green") -> Text:
    if value:
        return Text(f"  {true_label}  ", style=true_style)
    return Text(f"  {false_label}  ", style=false_style)


def percent_text(p: float, decimals: int = 2) -> Text:
    if p > 0:
        return Text(f"+{p:.{decimals}f}%", style="bold green")
    if p < 0:
        return Text(f"{p:.{decimals}f}%", style="bold red")
    return Text(f"{p:.{decimals}f}%", style="dim")


# ─── Panel builders ───────────────────────────────────────────────────────
def header_panel(state: State) -> Panel:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    n_open, n_max = state.last_tick_open
    api_ok = "●" if state.api_ok else "○"

    balance = state.api_balance.get("total", 0)
    free = state.api_balance.get("free", 0)
    profit_total = state.api_profit.get("profit_closed_coin", 0)
    profit_pct = state.api_profit.get("profit_closed_percent_mean", 0)
    closed = state.api_profit.get("closed_trade_count", 0)
    wins = state.api_profit.get("winning_trades", 0)
    losses = state.api_profit.get("losing_trades", 0)
    win_rate = (wins / closed * 100) if closed else 0

    t = Table.grid(padding=(0, 2), expand=True)
    t.add_column(ratio=1)
    t.add_column(ratio=1)
    t.add_column(ratio=1)
    t.add_column(ratio=1)
    t.add_row(
        Text(f"{api_ok} API"),
        Text(f"now {now}"),
        Text(f"tick {state.last_tick_ts}", style="dim"),
        Text(f"open {n_open}/{n_max}", style="bold"),
    )
    profit_style = "bold green" if profit_total >= 0 else "bold red"
    t.add_row(
        Text(f"balance ${balance:.2f}", style="bold"),
        Text(f"free ${free:.2f}", style="dim"),
        Text(f"closed {closed} | W/L {wins}/{losses} ({win_rate:.0f}%)"),
        Text(f"PnL ${profit_total:+.2f} ({profit_pct:+.2f}%)", style=profit_style),
    )
    return Panel(t, title="[bold cyan]TwinPennies V4 LIVE[/]", box=HEAVY, border_style="cyan")


def btc_gate_panel(state: State) -> Panel:
    btc = state.btc
    t = Table.grid(padding=(0, 1), expand=False)
    t.add_column(style="dim", width=14)
    t.add_column()

    t.add_row("BTC mom (4p):", Text(f"{btc.mom:+.2f}",
              style="bold red" if abs(btc.mom) > 3.5 else "white"))
    t.add_row("BTC atr_z:", Text(f"{btc.atr_z:+.2f}", style="white"))
    t.add_row("", Text(""))
    t.add_row(Text("pump", style="dim"), flag(btc.pump, "PUMP", "off",
              true_style="bold black on red", false_style="dim green"))
    t.add_row(Text("dump", style="dim"), flag(btc.dump, "DUMP", "off",
              true_style="bold black on red", false_style="dim green"))
    t.add_row(Text("high_vol", style="dim"), flag(btc.high_vol, "CHAOS", "off",
              true_style="bold black on red", false_style="dim green"))
    t.add_row("", Text(""))

    # Show what's currently blocked
    blocked = []
    if btc.high_vol:
        blocked.append("ALL entries")
    else:
        if btc.pump:
            blocked.append("SHORT entries")
        if btc.dump:
            blocked.append("LONG entries")
    if blocked:
        t.add_row("blocking:", Text(" + ".join(blocked), style="bold red"))
    else:
        t.add_row("blocking:", Text("nothing", style="dim green"))

    cfg_bt = state.config.get("btc_trend", {})
    t.add_row("pump thr:", Text(f"+{cfg_bt.get('pump_threshold', '?')}", style="dim"))
    t.add_row("dump thr:", Text(f"{cfg_bt.get('dump_threshold', '?')}", style="dim"))
    t.add_row("chaos thr:", Text(f"+{cfg_bt.get('high_vol_threshold', '?')}", style="dim"))

    return Panel(t, title="[bold yellow]BTC TREND GATE[/]", box=ROUNDED, border_style="yellow")


def pair_spectrum_panel(state: State) -> Panel:
    entry_z = state.config.get("basket", {}).get("entry_z", 1.2)
    btc = state.btc

    table = Table(box=SIMPLE, show_edge=False, padding=(0, 1), expand=True)
    table.add_column("Pair", style="bold", width=5)
    table.add_column("z", justify="right", width=7)
    table.add_column(f"-3 ... 0 ... +3 (┊=±{entry_z:.1f})", width=23)
    table.add_column("Signal", justify="center", width=10)
    table.add_column("Gate", justify="center", width=12)
    table.add_column("Twin?", justify="center", width=7)
    table.add_column("Pos", justify="center", width=6)

    if not state.pairs:
        table.add_row("[dim](waiting for first TICK…)[/]", "", "", "", "", "", "")
        return Panel(table, title="[bold cyan]PAIR Z-SPECTRUM[/]",
                     box=ROUNDED, border_style="cyan")

    order = ["ETH", "SOL", "XRP", "DOGE", "SUI", "ONDO", "TON"]
    sorted_pairs = sorted(
        state.pairs.values(),
        key=lambda p: order.index(p.pair.split("/")[0])
            if p.pair.split("/")[0] in order else 99,
    )

    # Pre-compute: do we have at least one strong long-cand and short-cand?
    long_cands = [p for p in sorted_pairs
                  if p.z < -entry_z and not p.in_position]
    short_cands = [p for p in sorted_pairs
                   if p.z > entry_z and not p.in_position]

    for p in sorted_pairs:
        sym = p.pair.split("/")[0]
        z_style = "bold red" if p.z > entry_z else (
            "bold green" if p.z < -entry_z else "white")

        # Determine signal class
        if p.z > entry_z:
            signal = Text(" SHORT ", style="black on bright_red")
        elif p.z < -entry_z:
            signal = Text("  LONG ", style="black on bright_green")
        else:
            signal = Text("  -   ", style="dim")

        # Gate status (what would block this entry)
        gate_parts = []
        if p.in_position:
            gate = Text(" in-pos ", style="dim yellow")
        elif btc.high_vol:
            gate = Text(" CHAOS ", style="bold red")
        elif p.z > entry_z and btc.pump:
            gate = Text(" PUMP-blk", style="bold red")
        elif p.z < -entry_z and btc.dump:
            gate = Text(" DUMP-blk", style="bold red")
        elif abs(p.z) > entry_z:
            gate = Text(" pass ", style="bold green")
        else:
            gate = Text("  -   ", style="dim")

        # Twin availability
        if p.z > entry_z:
            twin_ok = len(long_cands) > 0
        elif p.z < -entry_z:
            twin_ok = len(short_cands) > 0
        else:
            twin_ok = False
        twin_txt = Text(" ✓ ", style="bold green") if twin_ok else (
            Text(" ✗ ", style="dim red") if abs(p.z) > entry_z else Text("  -", style="dim"))

        # In position
        if p.in_position:
            pos_txt = Text(f" {p.in_position_side[:1].upper()} ", style="bold magenta")
        else:
            pos_txt = Text(" - ", style="dim")

        table.add_row(
            sym,
            Text(f"{p.z:+.2f}", style=z_style),
            z_bar(p.z, entry_z),
            signal,
            gate,
            twin_txt,
            pos_txt,
        )

    return Panel(table, title="[bold cyan]PAIR Z-SPECTRUM[/]",
                 box=ROUNDED, border_style="cyan")


def matchmaker_panel(state: State) -> Panel:
    """Show what twin pairings would currently fire."""
    entry_z = state.config.get("basket", {}).get("entry_z", 1.2)
    pairs = sorted(state.pairs.values(),
                   key=lambda p: p.pair.split("/")[0])
    long_cands = [p for p in pairs if p.z < -entry_z and not p.in_position]
    short_cands = [p for p in pairs if p.z > entry_z and not p.in_position]

    btc = state.btc
    blocked = btc.high_vol

    inner: Group
    if not long_cands and not short_cands:
        inner = Group(Text("No |z| > entry_z threshold on any pair.", style="dim"))
    else:
        bits: list = []
        if long_cands and not (btc.dump or blocked):
            bits.append(Text("LONG candidates:", style="bold bright_green"))
            for p in long_cands:
                sym = p.pair.split("/")[0]
                bits.append(Text(f"  {sym}  z={p.z:+.2f}", style="green"))
        elif long_cands:
            why = "DUMP" if btc.dump else "CHAOS"
            bits.append(Text(f"LONG cands present but blocked by BTC {why}",
                             style="dim red"))

        if short_cands and not (btc.pump or blocked):
            bits.append(Text("SHORT candidates:", style="bold bright_red"))
            for p in short_cands:
                sym = p.pair.split("/")[0]
                bits.append(Text(f"  {sym}  z={p.z:+.2f}", style="red"))
        elif short_cands:
            why = "PUMP" if btc.pump else "CHAOS"
            bits.append(Text(f"SHORT cands present but blocked by BTC {why}",
                             style="dim red"))

        if long_cands and short_cands and not blocked \
                and not (btc.pump and not btc.dump):
            bits.append(Text(""))
            bits.append(Text("→ Possible twin matches THIS cycle:",
                             style="bold yellow"))
            for lc in long_cands:
                ls = lc.pair.split("/")[0]
                for sc in short_cands:
                    ss = sc.pair.split("/")[0]
                    bits.append(Text(
                        f"  {ls}(L) ⇆ {ss}(S)  "
                        f"|z|sum={abs(lc.z)+abs(sc.z):.2f}",
                        style="yellow"))
        elif (long_cands or short_cands) and not blocked:
            bits.append(Text(""))
            bits.append(Text("→ No twin available (need both sides).",
                             style="dim"))
        inner = Group(*bits)

    return Panel(inner, title="[bold yellow]TWIN MATCHMAKER (this cycle)[/]",
                 box=ROUNDED, border_style="yellow")


def open_trades_panel(state: State) -> Panel:
    twin_cfg = state.config.get("twin", {})
    safety = twin_cfg.get("safety_stop", -0.05)
    loser_max = twin_cfg.get("loser_max_candles", 3)
    max_cand = twin_cfg.get("max_candles", 30)

    if not state.api_status:
        return Panel(
            Text("No open trades.", style="dim"),
            title="[bold magenta]OPEN TRADES — DECISION STATE[/]",
            box=ROUNDED, border_style="magenta",
        )

    # If we have HOLD-parsed decision state for any trade, use it; otherwise
    # fall back to API-only fields (older trade with no HOLD log yet).
    rows = []
    for api_t in state.api_status:
        dec = next((d for d in state.trades if d.pair == api_t["pair"]), None)
        sym = api_t["pair"].split("/")[0]
        side = "SHORT" if api_t["is_short"] else "LONG"
        side_style = "bold red" if api_t["is_short"] else "bold green"

        if dec is None:
            rows.append(Text(
                f"{api_t['trade_id']:>3}  {sym:<5} {side:<6}  "
                f"${api_t['stake_amount']:>6.2f}  "
                f"p={api_t.get('profit_pct', 0):+.2f}%  "
                f"(awaiting HOLD log)",
                style="dim"
            ))
            continue

        # Detail block per trade
        eval_lbl = "W" if dec.is_winner else ("L" if dec.is_winner is False else "?")
        eval_style = "bright_green" if eval_lbl == "W" else (
            "bright_red" if eval_lbl == "L" else "dim")

        header = Text()
        header.append(f"#{dec.trade_id:<3} ", style="dim")
        header.append(f"{sym:<5} ", style="bold")
        header.append(f"{side:<6} ", style=side_style)
        header.append(f"age={int(dec.age_candles)}c  ", style="dim")
        header.append(f"stake=${dec.stake:.0f}  ", style="white")
        header.append(f"[", style="dim")
        header.append(f"{eval_lbl}", style=eval_style)
        header.append(f"+S{dec.scale_count}/{dec.max_scales}", style="cyan")
        header.append(f"]  ", style="dim")
        # profit
        p_style = "bold green" if dec.profit_pct > 0 else (
            "bold red" if dec.profit_pct < 0 else "white")
        header.append(f"p={dec.profit_pct:+.2f}%", style=p_style)
        header.append(f" peak={dec.peak_pct:+.2f}%", style="dim")

        # decision-distance line
        dist = Text("    ")
        # z info
        dist.append(f"z={dec.current_z:+.2f} ", style="white")
        dist.append(f"entry_z={dec.entry_z:+.2f} ", style="dim")
        dist.append(f"Δ={dec.z_delta:+.2f}", style="cyan" if dec.z_delta > 0 else "dim")

        # exit triggers
        triggers = Text("    ")
        # safety stop distance
        safety_dist = dec.profit_pct - safety * 100
        triggers.append(f"to_safety {safety_dist:+.2f}pp  ", style="dim")

        if dec.is_winner is True:
            # distance to winner_revert: need z to reach -wez (long) or +wez (short)
            if dec.side == "long":
                z_needed = -dec.winner_exit_z
                gap = dec.current_z - z_needed  # negative means we passed
                triggers.append(f"to_revert z {gap:+.2f}  ", style="green")
            else:
                z_needed = dec.winner_exit_z
                gap = z_needed - dec.current_z
                triggers.append(f"to_revert z {gap:+.2f}  ", style="green")
            triggers.append(f"time_left {int(dec.time_left_candles)}c", style="dim")
        elif dec.is_winner is False:
            cand_left = max(0, loser_max - int(dec.age_candles))
            triggers.append(f"loser_close in {cand_left}c", style="bold red")
        else:
            triggers.append(f"awaiting EVAL ({2 - int(dec.age_candles)}c left)", style="dim")

        # btc_mom reverse trigger (only for scaled winners)
        if dec.is_winner and dec.scale_count > 0:
            triggers.append(f"  btc_mom={dec.btc_mom:+.2f}",
                            style="bold red" if abs(dec.btc_mom) > 3.0 else "dim")

        rows.append(Group(header, dist, triggers, Text("")))

    return Panel(Group(*rows),
                 title="[bold magenta]OPEN TRADES — DECISION STATE[/]",
                 box=ROUNDED, border_style="magenta")


def events_panel(state: State) -> Panel:
    if not state.events:
        return Panel(Text("(no events yet)", style="dim"),
                     title="[bold blue]RECENT EVENTS[/]", box=ROUNDED,
                     border_style="blue")
    t = Table(box=SIMPLE, show_edge=False, padding=(0, 1), expand=True)
    t.add_column("time", style="dim", width=8)
    t.add_column("kind", width=8)
    t.add_column("summary")
    # Newest at top
    for ev in list(state.events)[::-1]:
        t.add_row(ev.ts, Text(ev.kind, style=ev.color), Text(ev.summary, style=ev.color))
    return Panel(t, title="[bold blue]RECENT EVENTS[/]", box=ROUNDED,
                 border_style="blue")


def config_panel(state: State) -> Panel:
    tw = state.config.get("twin", {})
    bk = state.config.get("basket", {})
    bt = state.config.get("btc_trend", {})
    vol = state.config.get("volume", {})

    t = Table.grid(padding=(0, 2), expand=False)
    t.add_column(style="dim", width=22)
    t.add_column()
    # basket
    t.add_row("entry_z", str(bk.get("entry_z", "?")))
    t.add_row("zscore_method", str(bk.get("zscore_method", "?")))
    t.add_row("kalman_gain", str(bk.get("kalman_gain", "?")))
    t.add_row("---", "")
    # twin core
    t.add_row("eval_candles", str(tw.get("eval_candles")))
    t.add_row("max_positions", str(tw.get("max_positions")))
    t.add_row("initial_leverage", f"{tw.get('initial_leverage')}x")
    t.add_row("min_winner_profit", f"{float(tw.get('min_winner_profit', 0))*100:.2f}%")
    t.add_row("---", "")
    # scale
    t.add_row("max_scale_times", Text(str(tw.get("max_scale_times")),
              style="bold cyan"))
    t.add_row("scale_stake", f"${tw.get('scale_stake')}")
    t.add_row("z_revert_min", str(tw.get("z_revert_min")))
    t.add_row("scale_min_profit", f"{float(tw.get('scale_min_profit', 0))*100:.2f}%")
    t.add_row("---", "")
    # exits
    t.add_row("winner_exit_z", str(tw.get("winner_exit_z")))
    t.add_row("max_candles", f"{tw.get('max_candles')}c")
    t.add_row("loser_max_candles", f"{tw.get('loser_max_candles')}c")
    t.add_row("safety_stop", f"{float(tw.get('safety_stop', 0))*100:.1f}%")
    t.add_row("---", "")
    # new knobs
    t.add_row("cooldown_after_winner",
              f"{tw.get('cooldown_after_winner_minutes')}min"
              if tw.get('cooldown_after_winner_minutes') else "off")
    t.add_row("min_entry_notional",
              f"${tw.get('min_entry_notional')}" if tw.get('min_entry_notional') else "off")
    t.add_row("---", "")
    # btc_trend
    t.add_row("btc pump/dump/chaos",
              f"+{bt.get('pump_threshold')} / {bt.get('dump_threshold')} / "
              f"+{bt.get('high_vol_threshold')}")
    t.add_row("vol_ok threshold", str(vol.get("vol_ok_threshold")))

    return Panel(t, title="[bold green]CONFIG SNAPSHOT[/]", box=ROUNDED,
                 border_style="green")


# ─── Layout & main ────────────────────────────────────────────────────────
def make_layout(state: State) -> Layout:
    root = Layout()
    root.split_column(
        Layout(header_panel(state), size=4, name="head"),
        Layout(name="body"),
    )

    body = root["body"]
    body.split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=3),
    )

    body["left"].split_column(
        Layout(btc_gate_panel(state), ratio=1),
        Layout(config_panel(state), ratio=2),
    )

    body["right"].split_column(
        Layout(pair_spectrum_panel(state), ratio=2),
        Layout(matchmaker_panel(state), ratio=1),
        Layout(open_trades_panel(state), ratio=2),
        Layout(events_panel(state), ratio=2),
    )
    return root


def build_state(args) -> State:
    state = State()
    state.config = load_config(args.config)

    # API calls (may fail)
    status = api("status")
    state.api_status = status if isinstance(status, list) else []
    state.api_count = api("count") or {}
    state.api_profit = api("profit") or {}
    state.api_balance = api("balance") or {}
    state.api_ok = bool(status is not None or state.api_count)

    # Parse log
    basket_pairs = state.config.get("basket", {}).get("pairs", [])
    entry_z = state.config.get("basket", {}).get("entry_z", 1.2)
    lines = tail_log(args.log)
    parse_logs(lines, state, basket_pairs, entry_z)
    return state


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--refresh", type=float, default=DEFAULT_REFRESH)
    ap.add_argument("--once", action="store_true",
                    help="Render once and exit (for snapshots/testing)")
    args = ap.parse_args()

    if args.once:
        state = build_state(args)
        console.print(make_layout(state))
        return

    with Live(make_layout(build_state(args)),
              refresh_per_second=1, screen=True) as live:
        try:
            while True:
                state = build_state(args)
                live.update(make_layout(state))
                time.sleep(args.refresh)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
