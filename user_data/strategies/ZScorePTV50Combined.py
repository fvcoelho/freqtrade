"""
ZScorePTV50Combined — Z-Score Pairs Trading Strategy (Single File, Config-Driven)
==================================================================================

WHAT IT DOES:
    Mean-reversion strategy on Hyperliquid futures (15m timeframe).
    Trades 4 altcoin pairs split into 2 groups. Uses BTC as regime reference.
    When the z-score spread between groups diverges, enters expecting reversion.

PERFORMANCE (Backtest Feb-Apr 2026, $100 wallet):
    - 128 trades, +102.93% profit ($100 → $202.93)
    - 86.7% win rate (111 wins, 17 losses)
    - 16.26% max drawdown
    - Sharpe 5.13, avg +0.63% per trade
    - Best month: Mar +70.63%, Worst month: Feb +12.62%

GROUPS (default):
    Group A: XRP/USDC, ADA/USDC  → LONG only (mean-reversion buy)
    Group B: SOL/USDC, LINK/USDC → LONG + SHORT (both directions)
    BTC/USDC: Reference only (regime detection, not traded)

4 ENTRY SIGNALS:
    - mr_long_a:    Group A long when spread_z < -1.8 AND pair_z < -1.0
    - mr_short_b:   Group B short when spread_z < -1.8 AND pair_z > +1.0
    - mr_long_b:    Group B long when spread_z > +1.8 AND pair_z < -1.0
    - consol_long_a: Group A long during consolidation regime (relaxed thresholds)

EXIT PRIORITY (checked every candle):
    1. Fast exit (5m data): profit lock at 50% of peak, rapid drop detection
    2. Consolidation time stop: 4h max for consol_long_a trades
    3. Dynamic ROI: high-z entries get bonus profit targets
    4. Z-score scalp: exit when pair_z reverts past +0.2 (long) or -0.2 (short)
    5. Market-aware stops: BTC chaos/dump/pump → immediate exit
    6. Trailing stop: 0.8% trail activates at 1.6% profit
    7. Minimal ROI: 0m→3%, 15m→2%, 45m→1.2%, 90m→0.5%
    8. Stoploss: -10% (safety net, rarely hit)

EXIT RESULTS (Feb-Apr 2026):
    - ROI:           112 trades, +211.47 USDC, avg +1.54% (100% win) ← main profit source
    - Trailing:       11 trades,   +9.83 USDC, avg +0.66% (81.8% win)
    - Scalp:           2 trades,   +3.81 USDC, avg +1.56% (100% win)
    - mkt_stop_dump:   7 trades,  -57.51 USDC, avg -6.71% ← biggest loss source
    - stop_loss:       4 trades,  -52.64 USDC, avg -10.37% ← catastrophic losses

LEVERAGE:
    Base 3x, exponential scaling with signal strength (3-5x range).
    Reduced during BTC stress (high vol → max 2x, pump/dump → ×0.6).
    Consolidation trades capped at 3x.

DCA (Progressive Scaling):
    Only adds to WINNING positions (never averages down):
    +0.3% profit → add 1× stake
    +0.6% profit → add 2× stake
    +1.0% profit → add 3× stake

RISK CONTROLS:
    - Loss cooldown: 24h pause after catastrophic loss (< -5% or stop_loss)
    - Group balance: max 2 trades imbalance between groups
    - Wait all closed: optionally wait for all positions to close before new entry
    - BTC regime filter: no trades during TRENDING regime
    - Correlation regime: trades only when group correlation > 0.4

ALL PARAMETERS loaded from v50_config.json — edit that file to tune.
No inheritance chain — everything in one class for clarity.
"""
import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "v50_config.json"


def _load_config() -> dict:
    """Load strategy parameters from external JSON config file."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


class ZScorePTV50Combined(IStrategy):
    """
    Z-Score Pairs Trading Strategy — single-file, config-driven.

    Uses z-score statistical divergence between correlated crypto pairs
    to identify mean-reversion opportunities on Hyperliquid futures.
    """

    # =========================================================================
    # FREQTRADE INTERFACE — class-level defaults (overridden by config in __init__)
    # =========================================================================
    INTERFACE_VERSION = 3
    can_short = True                    # Strategy can open short positions
    process_only_new_candles = True     # Only run on new candle (not every tick)
    timeframe = "15m"                   # Main analysis timeframe
    startup_candle_count = 300          # Candles needed before first signal (300 × 15m = 75h)
    stoploss = -0.10                    # Safety net: -10% (rarely hit, trailing acts first)
    minimal_roi = {                     # Take-profit schedule (minutes → min profit)
        "0": 0.030,                     #   0m: exit if profit ≥ 3.0%
        "15": 0.020,                    #  15m: exit if profit ≥ 2.0%
        "45": 0.012,                    #  45m: exit if profit ≥ 1.2%
        "90": 0.005,                    #  90m: exit if profit ≥ 0.5%
    }
    trailing_stop = True                # Enable trailing stop
    trailing_stop_positive = 0.008      # Trail 0.8% below peak
    trailing_stop_positive_offset = 0.016  # Activate trailing at +1.6% profit
    trailing_only_offset_is_reached = True  # Only trail after offset is reached
    use_custom_stoploss = False         # Dynamic stoploss (set in __init__ if enabled)
    position_adjustment_enable = True   # Enable DCA (adding to winning positions)
    max_entry_position_adjustment = 3   # Max 3 adds (entry + 3 = 4 total)

    # =========================================================================
    # __init__ — Load all parameters from v50_config.json
    # =========================================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        c = _load_config()
        self._cfg = c

        # --- PAIR GROUPS ---
        # Group A: pairs that go LONG when spread diverges negatively
        # Group B: pairs that go SHORT (and LONG on positive divergence)
        # BTC: regime reference only, never traded
        g = c["groups"]
        self.group_a: list[str] = g["group_a"]   # e.g. ["XRP/USDC:USDC", "ADA/USDC:USDC"]
        self.group_b: list[str] = g["group_b"]   # e.g. ["SOL/USDC:USDC", "LINK/USDC:USDC"]
        self.BTC_REF: str = g["btc_ref"]          # e.g. "BTC/USDC:USDC"
        self._groups_initialized = True

        # --- TIMEFRAME & STAKE ---
        self.timeframe = c.get("timeframe", "15m")
        self.startup_candle_count = c.get("startup_candle_count", 300)
        self.stake_per_position: float = c.get("stake_per_position", 400.0)

        # --- RISK MANAGEMENT ---
        # Stoploss: -10% safety net. In practice, trailing stop (0.8%/1.6%) and
        # market-aware stops exit much earlier. Only 4 of 153 trades hit stoploss.
        r = c["risk"]
        self.stoploss = r["stoploss"]
        self.minimal_roi = {str(k): v for k, v in r["minimal_roi"].items()}
        self.trailing_stop_positive = r["trailing_stop_positive"]
        self.trailing_stop_positive_offset = r["trailing_stop_positive_offset"]

        # Dynamic stoploss (disabled by default — trailing dominates)
        # Tested: no impact because trailing stop acts before stoploss in 95% of cases
        ds = r.get("dynamic_stoploss", {})
        self._dynamic_sl_enabled = ds.get("enabled", False)
        self._dynamic_sl_strong_z = ds.get("strong_z", 3.0)
        self._dynamic_sl_strong_stop = ds.get("strong_stop", -0.10)
        self._dynamic_sl_medium_z = ds.get("medium_z", 2.0)
        self._dynamic_sl_medium_stop = ds.get("medium_stop", -0.05)
        self._dynamic_sl_weak_stop = ds.get("weak_stop", -0.03)

        # Progressive stop (disabled — too tight for 15m, destroys win rate)
        ps = r.get("progressive_stop", {})
        self._progressive_stop_enabled = ps.get("enabled", False)
        self._progressive_stop_levels = ps.get("levels", [])
        if self._progressive_stop_enabled:
            self.use_custom_stoploss = True
            self.trailing_stop = False
        if self._dynamic_sl_enabled:
            self.use_custom_stoploss = True

        # --- Z-SCORE PARAMETERS ---
        # zscore_window (96): rolling window for z-score mean/std (96 × 15m = 24h)
        # cum_return_window (8): cumulative return period (8 × 15m = 2h)
        # zscore_entry (1.8): spread must diverge > 1.8σ to enter
        #   Tested: 2.5 → fewer trades. 1.5 → too many bad trades. 1.8 = sweet spot.
        # pair_z_entry (1.0): individual pair must also be > 1.0σ from mean
        #   Optimized from 0.5 → 1.0: filters weak signals, +20% profit improvement
        # zscore_scalp_min_profit (0.012): minimum profit before scalp exit (1.2%)
        #   Raised from 0.4% → 1.2%: lets winners run longer
        # zscore_scalp_exit_threshold (0.2): exit when z passes 0.2 past zero
        #   Instead of exiting at z=0, waits for z=+0.2 (long) — captures extra move
        zs = c["zscore"]
        self._zscore_window = zs["zscore_window"]
        self._cum_return_window = zs["cum_return_window"]
        self._zscore_entry = zs["zscore_entry"]
        self._pair_z_entry = zs["pair_z_entry"]
        self._zscore_scalp_min_profit = zs["zscore_scalp_min_profit"]
        self._zscore_scalp_exit_threshold = zs.get("zscore_scalp_exit_threshold", 0.0)

        # --- REGIME DETECTION ---
        # 3 regimes based on BTC behavior:
        #   TRENDING:      |btc_mom| > 1.5% OR btc_atr_z > 1.5 → NO trades
        #   CONSOLIDATION: btc_atr_z < -0.5 AND |spread| < 1.5 AND |mom| < 0.8 → consol_long_a only
        #   RANGING:       everything else → all mean-reversion trades
        rg = c["regime"]
        self._regime_window = rg["regime_window"]           # Rolling correlation window
        self._regime_corr_min = rg["regime_corr_min"]       # Min correlation for regime_ok (0.4)
        self._use_ewm_corr = rg.get("use_ewm_corr", False)  # EWM correlation (weights recent data more)
        self._ewm_span = rg.get("ewm_span", 48)             # EWM half-life in candles
        self._consolidation_atr_z = rg["consolidation_atr_z"]
        self._consolidation_spread_max = rg["consolidation_spread_max"]
        self._consolidation_btc_mom_max = rg["consolidation_btc_mom_max"]
        self._trending_btc_mom = rg["trending_btc_mom"]
        self._trending_atr_z = rg["trending_atr_z"]
        # Spread volatility filter: block trades when spread is too volatile
        # High spread vol = spread not mean-reverting reliably
        self._spread_vol_filter = rg.get("spread_vol_filter", False)
        self._spread_vol_window = rg.get("spread_vol_window", 48)
        self._spread_vol_max_z = rg.get("spread_vol_max_z", 2.0)

        # --- CONSOLIDATION TRADES ---
        # Special entry during low-volatility periods. Only Group A longs.
        # Relaxed thresholds: spread > 1.2σ (vs 1.8), pair_z > 0.5.
        # Time-limited: exits after 16 candles (4h) to avoid getting stuck.
        co = c["consolidation"]
        self._consol_zscore_entry = co["consol_zscore_entry"]
        self._consol_pair_z_entry = co["consol_pair_z_entry"]
        self._consol_time_stop_candles = co["consol_time_stop_candles"]
        self._loss_cooldown_hours = co["loss_cooldown_hours"]

        # --- BTC TREND DETECTION ---
        # Computed from BTC/USDC 1h candles:
        #   mom_4h: 4-period close pct_change (×100 = %)
        #   ATR(14) → atr_pct → atr_z (z-score of ATR)
        #   pump: mom > +1.5% → blocks longs
        #   dump: mom < -1.5% → blocks shorts
        #   high_vol: atr_z > 2.0 → blocks ALL trades
        #   vol_ended: atr_z was >1.5, now ≤1.5 → entry opportunity
        bt = c["btc_trend"]
        self._btc_pump_threshold = bt["pump_threshold"]
        self._btc_dump_threshold = bt["dump_threshold"]
        self._btc_high_vol_threshold = bt["high_vol_threshold"]
        self._btc_vol_ended_threshold = bt["vol_ended_threshold"]
        self._btc_vol_bounce_spread_min = bt["vol_bounce_spread_min"]
        self._btc_mom_period = bt["mom_period"]
        self._btc_atr_period = bt["atr_period"]
        self._btc_atr_z_window = bt["atr_z_window"]

        # --- VOLUME FILTER ---
        # vol_ratio = current_volume / SMA(48).
        # Only enter when vol_ratio > 1.0 (above-average volume).
        vo = c["volume"]
        self._vol_ma_window = vo["vol_ma_window"]
        self._vol_ok_threshold = vo["vol_ok_threshold"]

        # --- LEVERAGE ---
        # Exponential: lev = base × e^(signal_strength × aggression / divisor)
        # Example: z=1.8 → 3.0 × e^(1.8×1.5/10) = 3.0 × 1.31 = 3.93x
        # Capped at 3-5x range. Consolidation max 3x. BTC stress reduces further.
        lv = c["leverage"]
        self._lev_base = lv["base_multiplier"]       # 3.0
        self._lev_aggression = lv["signal_aggression"]  # 1.5
        self._lev_divisor = lv["signal_divisor"]     # 10.0
        self._lev_min = lv["min"]                    # 3.0
        self._lev_max = lv["max"]                    # 5.0
        self._lev_consol_max = lv["consol_max"]      # 3.0
        self._lev_btc_hv_max = lv["btc_high_vol_max"]  # 2.0
        self._lev_btc_pd_mult = lv["btc_pump_dump_multiplier"]  # 0.6
        self._lev_floor = lv["floor"]                # 2.0

        # --- ENTRY MODES ---
        # Tested alternatives (all worse than current):
        #   A long+short: -16.76 USDC from short_a trades (75% → destroyed)
        #   Hedge (A↔B opposite): -31.86% over 3 months
        #   Intra-group hedge (XRP↔ADA opposite): -42.16%
        #   Duo same direction: -31.86%
        # Current is best: A=long only, B=long+short
        em = c.get("entry_modes", {})
        self._group_a_long = em.get("group_a_long", True)
        self._group_a_short = em.get("group_a_short", False)
        self._group_b_long = em.get("group_b_long", True)
        self._group_b_short = em.get("group_b_short", True)
        self._hedge_pairs = em.get("hedge_pairs", False)

        # --- BALANCE / POSITION LIMITS ---
        bal = c.get("balance", {})
        self._max_group_imbalance = bal.get("max_group_imbalance", 1)
        self._wait_all_closed = bal.get("wait_all_closed", False)

        # --- DCA (Progressive Scaling) ---
        # Only adds to winners. Never averages down.
        # Example with $40 stake: entry at $40, +0.3% → add $40 (total $80),
        # +0.6% → add $80, +1.0% → add $120. Max 4 positions.
        dc = c["dca"]
        self.max_entry_position_adjustment = dc["max_adds"]
        self._dca_thresholds = dc["thresholds"]     # [0.003, 0.006, 0.010]
        self._dca_multipliers = dc["multipliers"]   # [1.0, 2.0, 3.0]

        # --- EXIT PARAMETERS ---
        ex = c["exits"]
        self._mkt_stop_loss = ex["mkt_stop_loss_threshold"]       # -0.5% to activate market stops
        self._mkt_stop_regime_loss = ex["mkt_stop_regime_loss"]   # -1.5% for regime stop
        self._catastrophic_loss = ex["catastrophic_loss_threshold"]  # -5% triggers 24h cooldown
        self._dyn_roi_high_z_min = ex["dyn_roi_high_z_min"]       # z ≥ 3.0 gets bonus target
        self._dyn_roi_high_z_profit = ex["dyn_roi_high_z_profit"] # 1.5% within 90m
        self._dyn_roi_high_z_minutes = ex["dyn_roi_high_z_minutes"]
        self._dyn_roi_mid_z_min = ex["dyn_roi_mid_z_min"]         # z ≥ 2.7
        self._dyn_roi_mid_z_profit = ex["dyn_roi_mid_z_profit"]   # 1.3% within 60m
        self._dyn_roi_mid_z_minutes = ex["dyn_roi_mid_z_minutes"]
        self._roi_gate_high_z_min = ex["roi_gate_high_z_minutes"]
        self._roi_gate_high_z_profit = ex["roi_gate_high_z_profit"]
        self._roi_gate_mid_z_min = ex["roi_gate_mid_z_minutes"]
        self._roi_gate_mid_z_profit = ex["roi_gate_mid_z_profit"]

        # --- INTERNAL STATE ---
        self._pair_zscores: dict[str, DataFrame] = {}  # Cache of per-pair z-scores
        self._df_cache: dict[str, DataFrame] = {}       # Cache of dp.get_pair_dataframe per cycle
        self._df_cache_cycle: int = 0                    # Invalidate cache each new cycle
        self._btc_trend: dict = {}                      # BTC trend signals (computed once)
        self._trade_history: list[dict] = []            # Closed trade features for scoring
        self._pending_features: dict[str, list] = {}    # Features awaiting trade assignment
        self._loss_cooldown_until: Optional[datetime] = None  # Cooldown timer after big loss

        # --- FAST EXIT (5m data) ---
        # Checks 5m candles between 15m candles for rapid reaction.
        # Profit lock: if profit hits 0.8%, locks 50%. If drops to 0.4% → exit.
        # Rapid drop: if 5m price drops 3% in 3 candles while losing → exit.
        # Note: only effective in live/dry_run (backtester simulates per 15m candle)
        fe = c.get("fast_exit", {})
        self._fast_exit_enabled = fe.get("enabled", False)
        self._fast_exit_tf = fe.get("timeframe", "5m")
        self._fast_exit_lock_pct = fe.get("profit_lock_pct", 0.5)
        self._fast_exit_lock_activation = fe.get("profit_lock_activation", 0.008)
        self._fast_exit_rapid_loss = fe.get("rapid_loss_threshold", -0.03)
        self._fast_exit_rapid_candles = fe.get("rapid_loss_candles", 3)
        self._peak_profit: dict[str, float] = {}

        # --- COMBO CONFIG (optional hot-reload of pair groups) ---
        self.COMBO_CONFIG = Path(__file__).parent.parent / "scanner" / "pair_combos.json"
        self._combo_mtime: float = 0
        self._load_combo_config()

        logger.info(f"V50 Combined loaded — A={self.group_a} B={self.group_b} BTC={self.BTC_REF}")

    # =========================================================================
    # DATAFRAME CACHE — avoid repeated dp.get_pair_dataframe calls per cycle
    # =========================================================================

    def _get_pair_df(self, pair: str, timeframe: str | None = None) -> DataFrame | None:
        """
        Cached wrapper around dp.get_pair_dataframe.
        Cache is valid for one cycle (invalidated at start of populate_indicators).
        In backtest with 5 pairs: reduces 20+ dp calls per cycle to 5.
        """
        tf = timeframe or self.timeframe
        key = f"{pair}__{tf}"
        if key in self._df_cache:
            return self._df_cache[key]
        if not self.dp:
            return None
        df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
        if df is not None:
            self._df_cache[key] = df
        return df

    # =========================================================================
    # COMBO CONFIG — hot-reload pair groups from external JSON
    # =========================================================================

    def _load_combo_config(self) -> bool:
        if not self.COMBO_CONFIG.is_file():
            return False
        mtime = self.COMBO_CONFIG.stat().st_mtime
        if mtime == self._combo_mtime and self._groups_initialized:
            return True
        try:
            with open(self.COMBO_CONFIG) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
        if config.get("auto_cluster", False):
            self._combo_mtime = mtime
            return False
        active = config.get("active_combo", "")
        combos = config.get("combos", {})
        if active not in combos:
            return False
        combo = combos[active]
        new_a = combo.get("group_a", [])
        new_b = combo.get("group_b", [])
        if new_a != self.group_a or new_b != self.group_b:
            self.group_a = new_a
            self.group_b = new_b
            self._pair_zscores = {}
            logger.info(f"V50 COMBO: '{active}' A={self.group_a} B={self.group_b}")
        self._combo_mtime = mtime
        return True

    # =========================================================================
    # INFORMATIVE PAIRS — data the strategy needs from the exchange
    # =========================================================================

    def informative_pairs(self):
        """
        Declare additional data needed:
        - 1d for all pairs: used by regime correlation filter (not actively used in V50)
        - 1h for BTC: momentum, ATR, pump/dump detection
        - 5m for all pairs: fast exit rapid drop detection (if enabled)
        """
        pairs = self.dp.current_whitelist() if self.dp else []
        inf = [(pair, "1d") for pair in pairs] + [(self.BTC_REF, "1h")]
        if self._fast_exit_enabled:
            inf += [(pair, self._fast_exit_tf) for pair in pairs]
            inf.append((self.BTC_REF, self._fast_exit_tf))
        return inf

    # =========================================================================
    # BTC TREND — regime detection from Bitcoin 1h candles
    # =========================================================================

    def _compute_btc_trend(self) -> None:
        """
        Compute BTC trend signals from 1h candles (runs once per cycle).

        Signals:
        - pump: 4h momentum > +1.5% (BTC rallying → blocks new shorts)
        - dump: 4h momentum < -1.5% (BTC crashing → blocks new longs)
        - high_vol: ATR z-score > 2.0 (extreme volatility → blocks ALL)
        - vol_just_ended: ATR z-score was >1.5, now ≤1.5 (volatility cooling → entry chance)
        """
        if self._btc_trend or not self.dp:
            return
        btc_1h = self._get_pair_df(self.BTC_REF, "1h")
        if btc_1h is None or len(btc_1h) < 50:
            return

        # 4-period momentum (4h in 1h candles) as percentage
        mom = btc_1h["close"].pct_change(self._btc_mom_period) * 100

        # True Range → ATR(14) → normalize as % of price → z-score
        tr = np.maximum(
            btc_1h["high"] - btc_1h["low"],
            np.maximum(
                abs(btc_1h["high"] - btc_1h["close"].shift(1)),
                abs(btc_1h["low"] - btc_1h["close"].shift(1)),
            ),
        )
        atr = tr.rolling(self._btc_atr_period).mean()
        atr_pct = atr / btc_1h["close"] * 100
        w = self._btc_atr_z_window
        atr_z = ((atr_pct - atr_pct.rolling(w).mean()) /
                 atr_pct.rolling(w).std().replace(0, np.nan)).fillna(0)
        ve = self._btc_vol_ended_threshold

        self._btc_trend = {
            "dates": btc_1h["date"].values,
            "pump": (mom > self._btc_pump_threshold).values,
            "dump": (mom < self._btc_dump_threshold).values,
            "high_vol": (atr_z > self._btc_high_vol_threshold).values,
            "vol_just_ended": ((atr_z.shift(1) > ve) & (atr_z <= ve)).values,
            "btc_mom": mom.fillna(0.0).values,
            "btc_atr_z": atr_z.fillna(0.0).values,
        }

    def _get_btc_signal(self, dataframe: DataFrame, signal: str, numeric: bool = False):
        """Map BTC 1h signal to the pair's 15m timeframe via forward-fill."""
        if not self._btc_trend:
            return pd.Series(0.0 if numeric else False, index=dataframe.index)
        btc_df = pd.DataFrame({
            "date": pd.to_datetime(self._btc_trend["dates"], utc=True),
            signal: self._btc_trend[signal],
        }).set_index("date")
        pair_dates = pd.to_datetime(dataframe["date"], utc=True)
        merged = btc_df.reindex(pair_dates, method="ffill")
        return merged[signal].fillna(0.0 if numeric else False).values

    # =========================================================================
    # REGIME FILTER — correlation between groups must be positive
    # =========================================================================

    def _compute_regime(self, pair: str, dataframe: DataFrame) -> DataFrame:
        """
        Regime filter: rolling correlation between Group A[0] and Group B[0] returns.
        If |correlation| > 0.4, regime_ok = 1 (pairs are correlated → spread will revert).
        If correlation is low, spread may not revert → skip trades.
        """
        if not self.group_a or not self.group_b or not self.dp:
            dataframe["regime_ok"] = 1
            return dataframe
        ret_a = self._get_returns(self.group_a[0], pair, dataframe)
        ret_b = self._get_returns(self.group_b[0], pair, dataframe)
        if ret_a is not None and ret_b is not None:
            if self._use_ewm_corr:
                # EWM correlation: recent candles weighted more heavily
                # Reacts faster to correlation breakdown than simple rolling
                ewm_cov = ret_a.ewm(span=self._ewm_span).cov(ret_b)
                ewm_std_a = ret_a.ewm(span=self._ewm_span).std()
                ewm_std_b = ret_b.ewm(span=self._ewm_span).std()
                rolling_corr = (ewm_cov / (ewm_std_a * ewm_std_b).replace(0, np.nan)).fillna(0.0)
            else:
                rolling_corr = ret_a.rolling(window=self._regime_window).corr(ret_b)
            dataframe["rolling_corr"] = rolling_corr.fillna(0.0)
            dataframe["regime_ok"] = (rolling_corr.abs() > self._regime_corr_min).astype(int).fillna(0)
        else:
            dataframe["rolling_corr"] = 0.0
            dataframe["regime_ok"] = 1
        return dataframe

    def _get_returns(self, target_pair: str, current_pair: str, dataframe: DataFrame):
        """Get log returns for a pair, aligned to the current dataframe length."""
        if target_pair == current_pair:
            return dataframe["log_return"]
        if not self.dp:
            return None
        other_df = self._get_pair_df(target_pair)
        if other_df is None or len(other_df) < 50:
            return None
        ret = np.log(other_df["close"] / other_df["close"].shift(1))
        return ret.iloc[-len(dataframe):].reset_index(drop=True)

    # =========================================================================
    # Z-SCORE CALCULATION — core signal computation
    # =========================================================================

    def _compute_spread(self, pair: str, dataframe: DataFrame):
        """
        Spread Z-Score = (mean_A_zscores - mean_B_zscores), then z-scored.

        Optimized: uses _pair_zscores cache populated during populate_indicators.
        Each pair's z-score is computed once and cached — no redundant recalculation.
        Only falls back to _compute_pair_zscore if cache miss.

        Example: If XRP_z=+0.5, ADA_z=+0.3, SOL_z=-0.8, LINK_z=-0.6:
          spread = (0.5+0.3)/2 - (-0.8-0.6)/2 = 0.4 - (-0.7) = 1.1
          spread_z = z-score of spread over rolling window.
        """
        if not self.group_a or not self.group_b or not self.dp:
            return 0.0

        n = len(dataframe)
        group_a_z, group_b_z = [], []

        for p in self.group_a:
            z = self._get_cached_zscore(p, pair, dataframe, n)
            if z is not None:
                group_a_z.append(z)
        for p in self.group_b:
            z = self._get_cached_zscore(p, pair, dataframe, n)
            if z is not None:
                group_b_z.append(z)

        if not group_a_z or not group_b_z:
            return 0.0

        # Align all arrays to the same length (shortest) before stacking
        # Different pairs may have different data lengths (gaps in historical data)
        n = len(dataframe)
        group_a_z = [z[-n:] if len(z) > n else z for z in group_a_z]
        group_b_z = [z[-n:] if len(z) > n else z for z in group_b_z]
        min_len = min(min(len(z) for z in group_a_z), min(len(z) for z in group_b_z))
        group_a_z = [z[-min_len:] for z in group_a_z]
        group_b_z = [z[-min_len:] for z in group_b_z]

        # Vectorized mean: stack arrays and mean along axis 0
        if len(group_a_z) == 1:
            mean_a = group_a_z[0]
        else:
            mean_a = np.column_stack(group_a_z).mean(axis=1)

        if len(group_b_z) == 1:
            mean_b = group_b_z[0]
        else:
            mean_b = np.column_stack(group_b_z).mean(axis=1)

        # Pad to dataframe length if shorter (NaN-filled at start)
        if len(mean_a) < n:
            pad = n - len(mean_a)
            mean_a = np.concatenate([np.full(pad, 0.0), mean_a])
            mean_b = np.concatenate([np.full(pad, 0.0), mean_b])

        spread = pd.Series(mean_a - mean_b, index=dataframe.index)
        spread_mean = spread.rolling(window=self._zscore_window).mean()
        spread_std = spread.rolling(window=self._zscore_window).std()
        return ((spread - spread_mean) / spread_std.replace(0, np.nan)).fillna(0.0)

    def _get_cached_zscore(self, target_pair: str, current_pair: str,
                           dataframe: DataFrame, n: int):
        """
        Get z-score from cache (fast path) or compute on cache miss.
        Cache is populated by populate_indicators for each pair.
        """
        # Fast path: current pair already has z-score in dataframe
        if target_pair == current_pair:
            return dataframe["pair_zscore"].values

        # Cache hit: use pre-computed z-score
        if target_pair in self._pair_zscores:
            cached = self._pair_zscores[target_pair]["pair_zscore"].values
            return cached[-n:] if len(cached) > n else cached

        # Cache miss: compute and cache
        return self._compute_pair_zscore(target_pair, n)

    def _compute_pair_zscore(self, target_pair: str, n: int):
        """
        Compute z-score for a pair not yet cached.
        Only called on first cycle before all pairs are processed.
        """
        if not self.dp:
            return None
        other_df = self._get_pair_df(target_pair)
        if other_df is None or len(other_df) < self._zscore_window + self._cum_return_window:
            return None
        close = other_df["close"].values
        log_ret = np.log(close[1:] / close[:-1])
        log_ret = np.concatenate([[0.0], log_ret])

        # Cumulative return with numpy (faster than pandas rolling for fixed window)
        cum_ret = pd.Series(log_ret).rolling(window=self._cum_return_window).sum()
        cum_mean = cum_ret.rolling(window=self._zscore_window).mean()
        cum_std = cum_ret.rolling(window=self._zscore_window).std()
        z = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0).values
        return z[-n:] if len(z) > n else z

    # =========================================================================
    # TRADE SCORING — feature snapshot for post-trade analysis
    # =========================================================================

    def _snapshot_features(self, last) -> list[float]:
        """Capture market state at entry for later analysis and ROI gating."""
        return [
            abs(float(last.get("spread_zscore", 0.0))),  # [0] entry spread z-score
            float(last.get("rolling_corr", 0.0)),          # [1] correlation at entry
            float(last.get("vol_ratio", 1.0)),             # [2] volume ratio at entry
            float(last.get("btc_mom", 0.0)),               # [3] BTC momentum at entry
            float(last.get("btc_atr_z", 0.0)),             # [4] BTC ATR z-score at entry
        ]

    def _record_trade_outcome(self, trade: Trade, features: list[float], profit: float) -> None:
        """Store trade result for potential future scoring/learning."""
        self._trade_history.append({
            "vector": features, "outcome": 1 if profit > 0 else -1,
            "profit_pct": profit, "pair": trade.pair,
            "side": "long" if trade.is_short is False else "short",
        })

    # =========================================================================
    # INDICATORS — computed every 15m candle for each pair
    # =========================================================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Main indicator computation. Runs once per new 15m candle per pair.

        Computes:
        1. BTC trend signals (pump/dump/high_vol/mom/atr_z)
        2. Per-pair z-score (pair_zscore)
        3. Spread z-score between groups (spread_zscore)
        4. Regime filter (rolling correlation → regime_ok)
        5. Volume filter (vol_ratio → vol_ok)
        6. Z-score cross signals (pair_z_cross_up/down)
        """
        pair = metadata["pair"]
        self._load_combo_config()

        # Invalidate dataframe cache on first pair of each cycle
        cycle_id = id(dataframe)  # Different object each cycle
        if cycle_id != self._df_cache_cycle:
            self._df_cache.clear()
            self._df_cache_cycle = cycle_id

        self._compute_btc_trend()

        # BTC signals mapped to this pair's timeframe
        dataframe["btc_pump"] = self._get_btc_signal(dataframe, "pump")
        dataframe["btc_dump"] = self._get_btc_signal(dataframe, "dump")
        dataframe["btc_high_vol"] = self._get_btc_signal(dataframe, "high_vol")
        dataframe["btc_vol_ended"] = self._get_btc_signal(dataframe, "vol_just_ended")
        dataframe["btc_mom"] = self._get_btc_signal(dataframe, "btc_mom", numeric=True)
        dataframe["btc_atr_z"] = self._get_btc_signal(dataframe, "btc_atr_z", numeric=True)

        # Per-pair z-score
        dataframe["log_return"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        cum_ret = dataframe["log_return"].rolling(window=self._cum_return_window).sum()
        cum_mean = cum_ret.rolling(window=self._zscore_window).mean()
        cum_std = cum_ret.rolling(window=self._zscore_window).std()
        dataframe["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)
        self._pair_zscores[pair] = dataframe[["pair_zscore"]].copy()

        # Spread z-score
        dataframe["spread_zscore"] = self._compute_spread(pair, dataframe)

        # Spread volatility filter: z-score of spread's rolling std
        # When spread_vol_z > threshold, spread is erratic → skip entries
        if self._spread_vol_filter:
            spread_std = dataframe["spread_zscore"].rolling(self._spread_vol_window).std()
            spread_std_mean = spread_std.rolling(self._spread_vol_window).mean()
            spread_std_std = spread_std.rolling(self._spread_vol_window).std().replace(0, np.nan)
            dataframe["spread_vol_z"] = ((spread_std - spread_std_mean) / spread_std_std).fillna(0.0)
            dataframe["spread_vol_ok"] = (dataframe["spread_vol_z"] < self._spread_vol_max_z).astype(int)
        else:
            dataframe["spread_vol_ok"] = 1

        # Regime filter
        dataframe = self._compute_regime(pair, dataframe)

        # Volume filter
        vol_ma = dataframe["volume"].rolling(self._vol_ma_window).mean()
        dataframe["vol_ratio"] = (dataframe["volume"] / vol_ma.replace(0, np.nan)).fillna(1.0)
        dataframe["vol_ok"] = (dataframe["vol_ratio"] > self._vol_ok_threshold).astype(int)

        # Z-score zero-cross signals (used by scalp exit)
        dataframe["pair_z_cross_up"] = (
            (dataframe["pair_zscore"] > 0) & (dataframe["pair_zscore"].shift(1) <= 0)
        ).astype(int)
        dataframe["pair_z_cross_down"] = (
            (dataframe["pair_zscore"] < 0) & (dataframe["pair_zscore"].shift(1) >= 0)
        ).astype(int)

        return dataframe

    # =========================================================================
    # ENTRY — signal generation
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Generate entry signals based on regime + z-score + volume + BTC safety.

        RANGING regime (normal conditions):
          Group A: LONG when spread_z < -1.8 AND pair_z < -1.0
            → "A is undervalued vs B, and A itself is locally oversold"
          Group B: SHORT when spread_z < -1.8 AND pair_z > +1.0
            → "B is overvalued vs A, and B itself is locally overbought"
          Group B: LONG when spread_z > +1.8 AND pair_z < -1.0
            → "B is undervalued vs A, and B itself is locally oversold"

        CONSOLIDATION regime (low volatility):
          Group A: LONG with relaxed thresholds (spread > 1.2, pair_z > 0.5)

        TRENDING regime:
          No trades (blocked by is_ranging filter)
        """
        pair = metadata["pair"]

        btc_mom = dataframe["btc_mom"]
        btc_atr_z = dataframe["btc_atr_z"]
        spread_z = dataframe["spread_zscore"].abs()

        # Regime classification
        is_trending = (btc_mom.abs() > self._trending_btc_mom) | (btc_atr_z > self._trending_atr_z)
        is_consolidation = ((btc_atr_z < self._consolidation_atr_z) &
                            (spread_z < self._consolidation_spread_max) &
                            (btc_mom.abs() < self._consolidation_btc_mom_max))
        is_ranging = ~is_trending & ~is_consolidation

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        is_a = pair in self.group_a
        is_b = pair in self.group_b

        # Safety filters
        vol = dataframe["vol_ok"] == 1
        regime = (dataframe["regime_ok"] == 1) & (dataframe["spread_vol_ok"] == 1)
        no_chaos = ~dataframe["btc_high_vol"]
        safe_long = ~dataframe["btc_dump"] & no_chaos    # No longs during BTC dump
        safe_short = ~dataframe["btc_pump"] & no_chaos   # No shorts during BTC pump

        # Spread divergence thresholds
        spread_low = dataframe["spread_zscore"] < -self._zscore_entry   # A undervalued
        spread_high = dataframe["spread_zscore"] > self._zscore_entry   # A overvalued

        # Vol bounce: enter on relaxed spread after volatility ends
        vb_min = self._btc_vol_bounce_spread_min
        vol_bounce_low = dataframe["btc_vol_ended"] & (dataframe["spread_zscore"] < -vb_min)
        vol_bounce_high = dataframe["btc_vol_ended"] & (dataframe["spread_zscore"] > vb_min)
        spread_low = spread_low | vol_bounce_low
        spread_high = spread_high | vol_bounce_high

        # Per-pair z-score confirmation
        pair_z_long = dataframe["pair_zscore"] < -self._pair_z_entry   # Locally oversold
        pair_z_short = dataframe["pair_zscore"] > self._pair_z_entry   # Locally overbought

        # --- RANGING ENTRIES ---
        if self._hedge_pairs:
            # Hedge mode (tested: -31% over 3 months — disabled by default)
            base = is_ranging & vol & regime
            if is_a:
                dataframe.loc[base & spread_low & safe_long, ["enter_long", "enter_tag"]] = (1, "duo_long_a")
                dataframe.loc[base & spread_high & safe_short, ["enter_short", "enter_tag"]] = (1, "duo_short_a")
            elif is_b:
                dataframe.loc[base & spread_low & safe_short, ["enter_short", "enter_tag"]] = (1, "duo_short_b")
                dataframe.loc[base & spread_high & safe_long, ["enter_long", "enter_tag"]] = (1, "duo_long_b")
        else:
            # Normal mode (best: +102.93% over 3 months)
            if is_a:
                if self._group_a_long:
                    mr_long = is_ranging & vol & regime & spread_low & safe_long & pair_z_long
                    dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, "mr_long_a")
                if self._group_a_short:
                    mr_short = is_ranging & vol & regime & spread_high & safe_short & pair_z_short
                    dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (1, "mr_short_a")
            elif is_b:
                if self._group_b_short:
                    mr_short = is_ranging & vol & regime & spread_low & safe_short & pair_z_short
                    dataframe.loc[mr_short, ["enter_short", "enter_tag"]] = (1, "mr_short_b")
                if self._group_b_long:
                    mr_long = is_ranging & vol & regime & spread_high & safe_long & pair_z_long
                    dataframe.loc[mr_long, ["enter_long", "enter_tag"]] = (1, "mr_long_b")

        # --- CONSOLIDATION ENTRIES ---
        # Only Group A longs with relaxed thresholds during low-volatility periods
        consol_spread_low = dataframe["spread_zscore"] < -self._consol_zscore_entry
        consol_pair_z_long = dataframe["pair_zscore"] < -self._consol_pair_z_entry
        if is_a:
            consol_long = is_consolidation & vol & regime & consol_spread_low & safe_long & consol_pair_z_long
            mask = consol_long & (dataframe["enter_long"] == 0)  # Don't overwrite ranging signals
            dataframe.loc[mask, ["enter_long", "enter_tag"]] = (1, "consol_long_a")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """No dataframe-based exit signals — all exits handled by custom_exit."""
        return dataframe

    # =========================================================================
    # CONFIRM ENTRY — final gate before trade opens
    # =========================================================================

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """
        Final check before opening a trade:
        1. Loss cooldown: block all entries for 24h after catastrophic loss
        2. Wait all closed: optionally wait for all positions to close first
        3. Group balance: prevent excessive imbalance between Group A and B
        """
        # 24h cooldown after big loss
        if self._loss_cooldown_until and current_time < self._loss_cooldown_until:
            return False

        open_trades = Trade.get_trades_proxy(is_open=True)

        # Sequential mode: wait for all positions to close
        if self._wait_all_closed and len(open_trades) > 0:
            return False

        # Group balance check
        count_a = sum(1 for t in open_trades if t.pair in self.group_a)
        count_b = sum(1 for t in open_trades if t.pair in self.group_b)
        if pair in self.group_a and count_a + 1 - count_b > self._max_group_imbalance:
            return False
        if pair in self.group_b and count_b + 1 - count_a > self._max_group_imbalance:
            return False
        return True

    # =========================================================================
    # CUSTOM STOPLOSS — dynamic based on signal strength (disabled by default)
    # =========================================================================

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        """
        Dynamic stoploss based on entry signal strength.
        Tested: no impact because trailing stop (0.8%) acts before any stoploss level.
        Kept for future use with different trailing settings.
        """
        if not self._dynamic_sl_enabled:
            return None

        features = trade.get_custom_data("v26_features")
        if not features:
            features = self._pending_features.get(pair)
        if not features:
            return None

        entry_z = abs(features[0])
        if entry_z >= self._dynamic_sl_strong_z:
            return self._dynamic_sl_strong_stop
        elif entry_z >= self._dynamic_sl_medium_z:
            return self._dynamic_sl_medium_stop
        else:
            return self._dynamic_sl_weak_stop

    # =========================================================================
    # CUSTOM EXIT — multi-layer exit logic (checked every cycle)
    # =========================================================================

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Exit priority (first match wins):
        1. Fast exit: profit lock + rapid drop (5m data, live only)
        2. Consolidation time stop: 4h max for consol_long_a
        3. Dynamic ROI: bonus targets for high-z entries
        4. Z-score scalp: exit when pair_z reverts past threshold
        5. Market-aware stops: BTC chaos/dump/pump → immediate exit
        6. (Trailing stop + ROI + Stoploss handled by freqtrade core)
        """
        # Save entry features on first call
        if trade.get_custom_data("v26_features") is None and pair in self._pending_features:
            trade.set_custom_data("v26_features", self._pending_features.pop(pair))

        entry_tag = trade.enter_tag or ""
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60

        # --- 1. FAST EXIT (5m data, effective in live only) ---
        if self._fast_exit_enabled and self.dp:
            trade_key = f"{pair}_{trade.open_date_utc}"
            if trade_key not in self._peak_profit:
                self._peak_profit[trade_key] = current_profit
            self._peak_profit[trade_key] = max(self._peak_profit[trade_key], current_profit)
            peak = self._peak_profit[trade_key]

            # Profit lock: hit 0.8% → lock 50% → exit when drops to 0.4%
            if peak >= self._fast_exit_lock_activation and current_profit > 0:
                lock_level = peak * self._fast_exit_lock_pct
                if current_profit <= lock_level:
                    self._peak_profit.pop(trade_key, None)
                    return "fast_profit_lock"

            # Rapid loss: 5m price drops 3% in 3 candles while already losing
            df_5m = self._get_pair_df(pair, self._fast_exit_tf)
            if df_5m is not None and len(df_5m) >= self._fast_exit_rapid_candles:
                recent = df_5m.iloc[-self._fast_exit_rapid_candles:]
                is_long = trade.is_short is False
                if is_long:
                    drop = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1)
                    if drop < self._fast_exit_rapid_loss and current_profit < -0.01:
                        self._peak_profit.pop(trade_key, None)
                        return "fast_rapid_drop"
                else:
                    spike = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1)
                    if spike > abs(self._fast_exit_rapid_loss) and current_profit < -0.01:
                        self._peak_profit.pop(trade_key, None)
                        return "fast_rapid_spike"

        # --- 2. CONSOLIDATION TIME STOP ---
        # consol_long_a trades exit after 16 candles (4h) regardless of profit
        if entry_tag.startswith("consol_"):
            if trade_minutes / 15 >= self._consol_time_stop_candles:
                return "consol_time_stop"

        # --- 3. DYNAMIC ROI BOOST ---
        # High-z entries (z ≥ 3.0) get early profit target: 1.5% within 90m
        # Mid-z entries (z ≥ 2.7) get: 1.3% within 60m
        features = trade.get_custom_data("v26_features")
        if features and features[0] >= self._dyn_roi_high_z_min:
            if trade_minutes < self._dyn_roi_high_z_minutes and current_profit >= self._dyn_roi_high_z_profit:
                return "dyn_roi_high_z"
        elif features and features[0] >= self._dyn_roi_mid_z_min:
            if trade_minutes < self._dyn_roi_mid_z_minutes and current_profit >= self._dyn_roi_mid_z_profit:
                return "dyn_roi_mid_z"

        # --- 4. Z-SCORE SCALP EXIT ---
        # When pair_z reverts past threshold (0.2), the mean-reversion is complete.
        # Example: Long entered at pair_z=-1.5, exits when pair_z > +0.2
        if current_profit >= self._zscore_scalp_min_profit:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is not None and not dataframe.empty:
                pz = float(dataframe.iloc[-1].get("pair_zscore", 0.0))
                is_long = trade.is_short is False
                zt = self._zscore_scalp_exit_threshold
                if is_long and pz > zt:
                    return "zscore_scalp"
                if not is_long and pz < -zt:
                    return "zscore_scalp"

        # --- 5. MARKET-AWARE STOPS ---
        # Exit immediately when BTC shows danger signals while in loss
        if current_profit < self._mkt_stop_loss:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is not None and not dataframe.empty:
                last = dataframe.iloc[-1]
                is_long = trade.is_short is False
                if last.get("btc_high_vol", False):
                    return "mkt_stop_chaos"
                if is_long and last.get("btc_dump", False):
                    return "mkt_stop_dump"
                if not is_long and last.get("btc_pump", False):
                    return "mkt_stop_pump"
                if last.get("regime_ok", 1) == 0 and current_profit < self._mkt_stop_regime_loss:
                    return "mkt_stop_regime"

        return None

    # =========================================================================
    # CONFIRM EXIT — post-exit processing + ROI gating
    # =========================================================================

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        """
        Called after exit signal is generated. Can block the exit (return False).

        1. Catastrophic loss detection: activates 24h cooldown
        2. ROI gating: blocks ROI exit for high-z entries that haven't reached target
        3. Record trade outcome for scoring
        """
        profit = trade.calc_profit_ratio(rate)

        # Activate 24h cooldown after catastrophic loss
        if profit < self._catastrophic_loss or exit_reason in ("stop_loss", "mkt_stop_dump", "mkt_stop_pump"):
            self._loss_cooldown_until = current_time + timedelta(hours=self._loss_cooldown_hours)
            logger.info(f"V50 LOSS: {pair} {profit*100:.1f}% ({exit_reason}) — cooldown {self._loss_cooldown_hours}h")

        # ROI gating: don't let ROI exit high-z trades too early
        features = trade.get_custom_data("v26_features")
        if features is None:
            features = self._pending_features.pop(pair, None)
            if features is not None:
                trade.set_custom_data("v26_features", features)
        if exit_reason == "roi" and features:
            entry_z = features[0]
            tm = (current_time - trade.open_date_utc).total_seconds() / 60
            p = trade.calc_profit_ratio(rate)
            # High-z entry: block ROI exit if under target within time window
            if entry_z >= self._dyn_roi_high_z_min and tm < self._roi_gate_high_z_min and p < self._roi_gate_high_z_profit:
                return False
            if entry_z >= self._dyn_roi_mid_z_min and tm < self._roi_gate_mid_z_min and p < self._roi_gate_mid_z_profit:
                return False

        # Record outcome
        if features is not None:
            self._record_trade_outcome(trade, features, trade.calc_profit_ratio(rate))
        return True

    # =========================================================================
    # LEVERAGE — signal-strength based
    # =========================================================================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        """
        Exponential leverage based on signal strength.

        Formula: lev = base × e^(signal_strength × aggression / divisor)
        Example: z=2.0 → 3.0 × e^(2.0×1.5/10) = 3.0 × 1.35 = 4.05x

        Adjustments:
        - Consolidation trades: capped at 3x (lower confidence)
        - BTC high volatility: capped at 2x
        - BTC pump/dump: multiplied by 0.6 (risk reduction)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]
            features = self._snapshot_features(last)
            self._pending_features[pair] = features
        else:
            return min(self._lev_base, max_leverage)

        last = dataframe.iloc[-1]
        spread_z = abs(float(last.get("spread_zscore", 0.0)))
        pair_z = abs(float(last.get("pair_zscore", 0.0)))

        signal_strength = max(spread_z, pair_z)
        lev = self._lev_base * math.exp(signal_strength * self._lev_aggression / self._lev_divisor)
        lev = max(self._lev_min, min(lev, self._lev_max, max_leverage))

        if entry_tag and entry_tag.startswith("consol_"):
            lev = min(lev, self._lev_consol_max)

        if last.get("btc_high_vol", False):
            lev = min(lev, self._lev_btc_hv_max)
        elif last.get("btc_pump", False) or last.get("btc_dump", False):
            lev *= self._lev_btc_pd_mult

        return round(max(self._lev_floor, min(lev, max_leverage)), 1)

    # =========================================================================
    # DCA — progressive position scaling (winners only)
    # =========================================================================

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        Add to winning positions progressively. Never averages down.

        Schedule (with $40 stake):
          +0.3% profit → add 1× ($40)   → total $80  exposure
          +0.6% profit → add 2× ($80)   → total $160 exposure
          +1.0% profit → add 3× ($120)  → total $280 exposure

        Each add requires the previous threshold to have been passed.
        """
        adds = trade.nr_of_successful_entries - 1
        if adds >= len(self._dca_thresholds):
            return None
        if current_profit <= 0:
            return None
        if current_profit >= self._dca_thresholds[adds]:
            add_stake = trade.stake_amount * self._dca_multipliers[adds]
            if min_stake and add_stake < min_stake:
                add_stake = min_stake
            return min(add_stake, max_stake)
        return None

    # =========================================================================
    # STAKE — fixed per position
    # =========================================================================

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Fixed stake per position from config."""
        return min(self.stake_per_position, max_stake)
