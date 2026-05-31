# /loop 5m — TwoQueueBaseline LLM-in-loop

Run every 5 min while the dry-run/live bot is up. The bot writes
`user_data/two_queue_state.json` each candle close. You write decisions to
`user_data/llm_decisions.json` which the strategy reads on the next candle.

**Auditability is mandatory.** Every decision tick must be appended to
`user_data/llm_decisions_log.jsonl` (one JSON object per line, append-only)
so future runs can replay exactly what you saw and what you decided.

## Inputs to read each tick

1. `user_data/two_queue_state.json` — latest queue snapshot per pair. Per-pair fields:
   - `long_score`, `short_score` — deterministic scores (you boost via flags)
   - `rsi`, `mom_1h`, `vol_ratio` — legacy features used by deterministic formula
   - **Multi-window z-scores (USDC-denominated close):**
     - `z_2h` — over-extension in last 2h (mean ± std of last 24 candles)
     - `z_8h` — medium horizon (96 candles)
     - `z_24h` — daily (288 candles)
     - `z_3d` — multi-day (864 candles); structural over/under-valuation
   - `ret_z_1h` — z-score of 1h return vs 7d distribution (returns ≠ price level)
   - `vol_z` — volume z-score over 1d
   - `close`, `volume`, `thresholds`, `ts`

   **Reading the z-stack:** if `z_2h` is extreme (>+2 or <-2) but `z_24h` is mild
   (within ±1), the move is short-term over-extension → MR setup. If both `z_24h`
   and `z_3d` are extreme in the same direction → regime change / breakout, not
   MR. Cross-check with `ret_z_1h` — a high |ret_z_1h| means the move is unusually
   fast even for this pair's distribution (event-driven).
2. Open positions via API:
   `curl -s -u freqtrader:freqtrader http://127.0.0.1:8085/api/v1/status`
3. Recent trades:
   `curl -s -u freqtrader:freqtrader http://127.0.0.1:8085/api/v1/trades?limit=20`
4. PnL:
   `curl -s -u freqtrader:freqtrader http://127.0.0.1:8085/api/v1/profit`

## Two control surfaces

You have TWO files to influence the bot:

1. **`llm_flags.json`** — **SOFT entry boost.** Per-pair additive boost (0–1) to the
   deterministic score. Strategy applies this to NEXT candle's score BEFORE the gate
   fires. Use this to express conviction without overriding the gate logic.
   `final_long_score = deterministic_long_score + long_flag`. Entry threshold is 0.55
   on the combined score.
2. **`llm_decisions.json`** — **HARD override.** Forces an action: `side: "exit"`
   to force-close a position, or `side: "long"/"short"` to bypass scoring entirely
   when `confirm_trade_entry` runs. Use sparingly for emergencies.

## Decision policy (initial)

**Soft flag (preferred for entries):**
- Set `long_flag` 0.20–0.40 on a pair when you see strong conviction (RSI deeply
  oversold + z-score deeply negative + mom turning up). Combined with a baseline
  score of ~0.3, this pushes total to 0.5–0.7 → enters on next candle.
- Set `short_flag` symmetrically.
- Keep total active flagged pairs ≤ 3.

**Hard exit (for emergencies):**
- Force exit if loss approaching -2% AND opposite-side score rising.
- Force halt (`{"halt": true}` in decisions) on DD > 5% from session start.

Thresholds are a starting point — refine based on observed PnL across ticks.
Always include rationale.

## Output 1 — `user_data/llm_flags.json` (overwritten each tick, soft boost)

```json
{
  "ts": "<UTC ISO>",
  "flags": {
    "<PAIR>": {
      "long_flag": 0.0..1.0,
      "short_flag": 0.0..1.0,
      "expires_at": "<UTC ISO, ≤ 30 min ahead>",
      "reason": "<short rationale>"
    }
  }
}
```

The strategy reads this on the NEXT candle close, adds `long_flag` to that pair's
deterministic `long_score` (and same for short), then runs the entry gate against the
combined score. Omit pairs you want untouched. File fully replaced each tick.

## Output 2 — `user_data/llm_decisions.json` (overwritten, hard override)

Only when you need to bypass scoring entirely:

```json
{
  "ts": "<UTC ISO>",
  "decisions": {
    "<PAIR>": {
      "side": "long" | "short" | "exit",
      "expires_at": "<UTC ISO, ≤ 30 min ahead>",
      "reason": "<short rationale>"
    }
  }
}
```

Use for force-exits or emergency halts. Omit when not needed.

## Output 3 — `user_data/llm_decisions_log.jsonl` (APPEND-ONLY, mandatory)

After writing the decision file, **append a single JSON line** capturing the
full context of this tick so it can be replayed offline:

```json
{
  "ts": "<UTC ISO>",
  "tick_n": <integer>,
  "input": {
    "queue_state": { ... full contents of two_queue_state.json ... },
    "open_positions": [ ... raw API /status response ... ],
    "recent_trades_summary": { "n": 20, "last_5_pnl": [...], "win_rate_recent": 0.6 },
    "profit_pct_since_start": <float>
  },
  "thresholds_used": {
    "enter_long_score": 0.65,
    "enter_short_score": 0.65,
    "dominance": 0.20,
    "exit_opposite_score": 0.55,
    "tp_pct": 0.015,
    "sl_pct": -0.02
  },
  "flags_written": { ...same as flags file... },
  "decisions_written": { ...same as decisions file... },
  "rationale": "<2-3 sentence summary of why these choices>",
  "stop_flags_triggered": []
}
```

Use:
```bash
echo '{"ts":"...","tick_n":...,"input":...,...}' >> user_data/llm_decisions_log.jsonl
```

or in Python:
```python
import json
with open("user_data/llm_decisions_log.jsonl","a") as f:
    f.write(json.dumps(record, default=str) + "\n")
```

## Safety rails

- **HALT** (write `{"halt": true}` in decisions file + ping user) if any of:
  - cumulative dry-run drawdown > 5% from session start
  - 3 consecutive losing trades
  - `two_queue_state.json` older than 8 min (bot stuck)
- Never set `expires_at` more than 30 min ahead.
- Never emit > 2 entry decisions in a single tick.
- If thresholds are changed, log the change in `stop_flags_triggered` so the
  replay can mark a regime shift.

## Tick procedure

1. Read the 4 inputs.
2. One-sentence summary: "X long-qualified, Y short-qualified; max long=Z on PAIR".
3. Open positions vs current scores → emit any HARD exits in `llm_decisions.json`.
4. For potential entries → write `llm_flags.json` boosting promising pairs.
5. Append the full audit record to `llm_decisions_log.jsonl`.
6. Brief reply: "Tick HH:MM — flagged N, exits M, held K (DD=X%)".
