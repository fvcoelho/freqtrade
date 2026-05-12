"""Exit logic for ZScore V52.

Pure-function extraction of V51 custom_exit + confirm_trade_exit.
Identical logic — no behavioral changes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def _get_pair_df(pair: str, timeframe: str, dp, df_cache: dict):
    """Cached wrapper around dp.get_pair_dataframe.

    Mirrors V51 _get_pair_df — cache is valid for one cycle.
    """
    key = f"{pair}__{timeframe}"
    if key in df_cache:
        return df_cache[key]
    if dp is None:
        return None
    df = dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
    if df is not None:
        df_cache[key] = df
    return df


def record_trade_outcome(trade, features: list[float], profit: float,
                         trade_history: list) -> None:
    """Store trade result for potential future scoring/learning."""
    trade_history.append({
        "vector": features,
        "outcome": 1 if profit > 0 else -1,
        "profit_pct": profit,
        "pair": trade.pair,
        "side": "long" if trade.is_short is False else "short",
    })


def check_exit(
    pair: str,
    trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    cfg: dict,
    dp,
    btc_state: dict,
    peak_profit: dict,
    timeframe: str,
    df_cache: dict,
    pending_features: dict,
) -> Optional[str]:
    """Check exit conditions in priority order. Returns exit reason or None.

    Mutates peak_profit dict and pending_features dict as side effects
    (same as V51 custom_exit).

    Parameters
    ----------
    pair : str
        Trading pair.
    trade : Trade
        Freqtrade Trade object.
    current_time : datetime
        Current candle time.
    current_rate : float
        Current price.
    current_profit : float
        Current profit ratio.
    cfg : dict
        Full strategy config with sections: fast_exit, consolidation, exits, zscore.
    dp : DataProvider
        Freqtrade data provider (may be None in backtesting).
    btc_state : dict
        Not used directly (BTC columns in dataframe).
    peak_profit : dict
        Mutable dict tracking per-trade peak profit. Keys: "{pair}_{open_date}".
    timeframe : str
        Main strategy timeframe (e.g. "5m").
    df_cache : dict
        Mutable dict caching dataframes per cycle.
    pending_features : dict
        Mutable dict of pending entry features keyed by pair.

    Returns
    -------
    Optional[str]
        Exit reason string, or None to continue holding.
    """
    # Save entry features on first call
    if trade.get_custom_data("v26_features") is None and pair in pending_features:
        trade.set_custom_data("v26_features", pending_features.pop(pair))

    entry_tag = trade.enter_tag or ""
    trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60

    # --- Config lookups ---
    fast_cfg = cfg["fast_exit"]
    consol_cfg = cfg["consolidation"]
    exit_cfg = cfg["exits"]
    zscore_cfg = cfg["zscore"]

    # --- 1. FAST EXIT (5m data, effective in live only) ---
    if fast_cfg["enabled"] and dp:
        trade_key = f"{pair}_{trade.open_date_utc}"
        if trade_key not in peak_profit:
            peak_profit[trade_key] = current_profit
        peak_profit[trade_key] = max(peak_profit[trade_key], current_profit)
        peak = peak_profit[trade_key]

        # Profit lock
        if peak >= fast_cfg["profit_lock_activation"] and current_profit > 0:
            lock_level = peak * fast_cfg["profit_lock_pct"]
            if current_profit <= lock_level:
                peak_profit.pop(trade_key, None)
                return "fast_profit_lock"

        # Rapid loss
        df_5m = _get_pair_df(pair, fast_cfg["timeframe"], dp, df_cache)
        rapid_candles = fast_cfg["rapid_loss_candles"]
        if df_5m is not None and len(df_5m) >= rapid_candles:
            recent = df_5m.iloc[-rapid_candles:]
            is_long = trade.is_short is False
            rapid_loss = fast_cfg["rapid_loss_threshold"]
            if is_long:
                drop = recent["close"].iloc[-1] / recent["close"].iloc[0] - 1
                if drop < rapid_loss and current_profit < -0.01:
                    peak_profit.pop(trade_key, None)
                    return "fast_rapid_drop"
            else:
                spike = recent["close"].iloc[-1] / recent["close"].iloc[0] - 1
                if spike > abs(rapid_loss) and current_profit < -0.01:
                    peak_profit.pop(trade_key, None)
                    return "fast_rapid_spike"

    # --- 2. CONSOLIDATION TIME STOP ---
    if entry_tag.startswith("consol_"):
        if trade_minutes / 5 >= consol_cfg["consol_time_stop_candles"]:
            return "consol_time_stop"

    # --- 2b. GLOBAL TIME STOP ---
    if trade_minutes >= 360:
        return "time_stop"

    # --- 2c. NO REVERSION EXIT ---
    # If pair_z diverged further after entry (no mean-reversion happening),
    # exit early to avoid stop_loss. Checks after N candles.
    # Evidence: all 8 historical stop_losses showed divergence from candle 1.
    # Logic: long entered because pz < -1.2 (oversold). If after 15min pz is
    # even MORE negative → reversion not happening → exit early.
    nr_cfg = cfg.get("no_reversion_exit", {})
    if nr_cfg.get("enabled", False) and dp:
        nr_candles = nr_cfg.get("check_after_candles", 3)
        nr_z_threshold = nr_cfg.get("z_diverge_threshold", 0.2)
        nr_max_loss = nr_cfg.get("max_loss_pct", -0.01)

        if trade_minutes >= nr_candles * 5 and current_profit < nr_max_loss:
            dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
            if dataframe is not None and len(dataframe) > nr_candles:
                current_pz = float(dataframe.iloc[-1].get("pair_zscore", 0.0))
                entry_pz = float(dataframe.iloc[-(nr_candles + 1)].get("pair_zscore", 0.0))
                is_long = trade.is_short is False

                if is_long:
                    # Long expects pz to rise (revert towards 0)
                    # Diverging = pz dropped further negative
                    diverging = current_pz < entry_pz - nr_z_threshold
                else:
                    # Short expects pz to fall (revert towards 0)
                    # Diverging = pz rose further positive
                    diverging = current_pz > entry_pz + nr_z_threshold

                if diverging:
                    return "no_reversion"

    # --- 3. DYNAMIC ROI BOOST ---
    features = trade.get_custom_data("v26_features")
    dyn_roi_high_z_min = exit_cfg["dyn_roi_high_z_min"]
    dyn_roi_mid_z_min = exit_cfg["dyn_roi_mid_z_min"]

    if features and features[0] >= dyn_roi_high_z_min:
        if (trade_minutes < exit_cfg["dyn_roi_high_z_minutes"]
                and current_profit >= exit_cfg["dyn_roi_high_z_profit"]):
            return "dyn_roi_high_z"
    elif features and features[0] >= dyn_roi_mid_z_min:
        if (trade_minutes < exit_cfg["dyn_roi_mid_z_minutes"]
                and current_profit >= exit_cfg["dyn_roi_mid_z_profit"]):
            return "dyn_roi_mid_z"

    # --- 4. Z-SCORE SCALP EXIT ---
    if current_profit >= zscore_cfg["zscore_scalp_min_profit"]:
        dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if dataframe is not None and not dataframe.empty:
            pz = float(dataframe.iloc[-1].get("pair_zscore", 0.0))
            is_long = trade.is_short is False
            zt = zscore_cfg["zscore_scalp_exit_threshold"]
            if is_long and pz > zt:
                return "zscore_scalp"
            if not is_long and pz < -zt:
                return "zscore_scalp"

    # --- 5. MARKET-AWARE STOPS ---
    if current_profit < exit_cfg["mkt_stop_loss_threshold"]:
        dataframe, _ = dp.get_analyzed_dataframe(pair, timeframe)
        if dataframe is not None and not dataframe.empty:
            last = dataframe.iloc[-1]
            is_long = trade.is_short is False
            if last.get("btc_high_vol", False):
                return "mkt_stop_chaos"
            if is_long and last.get("btc_dump", False):
                return "mkt_stop_dump"
            if not is_long and last.get("btc_pump", False):
                return "mkt_stop_pump"
            if (last.get("regime_ok", 1) == 0
                    and current_profit < exit_cfg["mkt_stop_regime_loss"]):
                return "mkt_stop_regime"

    return None


def confirm_exit(
    pair: str,
    trade,
    exit_reason: str,
    current_time: datetime,
    rate: float,
    cfg: dict,
    pending_features: dict,
    cooldown_until: Optional[datetime],
    trade_history: list,
) -> tuple[bool, Optional[datetime]]:
    """Post-exit processing. Returns (allow_exit, new_cooldown_until).

    Mirrors V51 confirm_trade_exit. The caller (strategy.py) manages
    the cooldown_until state variable.

    Parameters
    ----------
    pair : str
        Trading pair.
    trade : Trade
        Freqtrade Trade object.
    exit_reason : str
        Reason for exit (e.g. "roi", "stop_loss", "mkt_stop_dump").
    current_time : datetime
        Current time.
    rate : float
        Exit rate.
    cfg : dict
        Full strategy config with section: exits.
    pending_features : dict
        Mutable dict of pending entry features keyed by pair.
    cooldown_until : Optional[datetime]
        Current cooldown deadline (may be None).
    trade_history : list
        Mutable list for recording trade outcomes.

    Returns
    -------
    tuple[bool, Optional[datetime]]
        (allow_exit, new_cooldown_until). If allow_exit is False, the exit
        is blocked. new_cooldown_until replaces the caller's state.
    """
    exit_cfg = cfg["exits"]
    consol_cfg = cfg["consolidation"]

    profit = trade.calc_profit_ratio(rate)
    new_cooldown = cooldown_until

    # Activate cooldown after catastrophic loss or stop events
    catastrophic_loss = exit_cfg["catastrophic_loss_threshold"]
    if profit < catastrophic_loss or exit_reason in (
        "stop_loss", "mkt_stop_dump", "mkt_stop_pump"
    ):
        cooldown_hours = consol_cfg["loss_cooldown_hours"]
        new_cooldown = current_time + timedelta(hours=cooldown_hours)
        logger.info(
            "V52 LOSS: %s %.1f%% (%s) — cooldown %dh",
            pair, profit * 100, exit_reason, cooldown_hours,
        )

    # ROI gating: don't let ROI exit high-z trades too early
    features = trade.get_custom_data("v26_features")
    if features is None:
        features = pending_features.pop(pair, None)
        if features is not None:
            trade.set_custom_data("v26_features", features)

    if exit_reason == "roi" and features:
        entry_z = features[0]
        tm = (current_time - trade.open_date_utc).total_seconds() / 60
        p = trade.calc_profit_ratio(rate)

        dyn_roi_high_z_min = exit_cfg["dyn_roi_high_z_min"]
        dyn_roi_mid_z_min = exit_cfg["dyn_roi_mid_z_min"]

        if (entry_z >= dyn_roi_high_z_min
                and tm < exit_cfg["roi_gate_high_z_minutes"]
                and p < exit_cfg["roi_gate_high_z_profit"]):
            return False, new_cooldown
        if (entry_z >= dyn_roi_mid_z_min
                and tm < exit_cfg["roi_gate_mid_z_minutes"]
                and p < exit_cfg["roi_gate_mid_z_profit"]):
            return False, new_cooldown

    # Record outcome
    if features is not None:
        record_trade_outcome(trade, features, trade.calc_profit_ratio(rate), trade_history)

    return True, new_cooldown
