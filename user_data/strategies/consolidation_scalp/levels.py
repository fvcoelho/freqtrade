"""Support/Resistance level detection engines.

All engines add these columns to the dataframe:
    - support: nearest support price level
    - resistance: nearest resistance price level
    - at_support: bool — price within proximity of support
    - at_resistance: bool — price within proximity of resistance

Engine selection via cfg["level_engine"]: "order_blocks" | "pivot_fractal" | "rolling_minmax"
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame


def compute(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Dispatch to the selected engine. Mutates and returns dataframe."""
    engine = cfg["level_engine"]
    if engine == "order_blocks":
        return _order_blocks(dataframe, cfg["order_blocks"])
    elif engine == "pivot_fractal":
        return _pivot_fractal(dataframe, cfg["pivot_fractal"])
    elif engine == "rolling_minmax":
        return _rolling_minmax(dataframe, cfg["rolling_minmax"], cfg["consolidation"])
    else:
        raise ValueError(f"Unknown level engine: {engine}")


def _order_blocks(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Detect order blocks — high-volume candles preceding directional moves."""
    close = dataframe["close"].values
    high = dataframe["high"].values
    low = dataframe["low"].values
    open_ = dataframe["open"].values
    volume = dataframe["volume"].values

    vol_ma_win = cfg["volume_ma_window"]
    vol_mult = cfg["volume_mult"]
    move_thresh = cfg["move_threshold"]
    move_candles = cfg["move_candles"]
    expiry = cfg["expiry_candles"]
    max_touches = cfg["max_touches"]
    wick_ratio = cfg["wick_ratio"]

    n = len(dataframe)
    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    at_support = np.zeros(n, dtype=bool)
    at_resistance = np.zeros(n, dtype=bool)

    vol_ma = dataframe["volume"].rolling(vol_ma_win).mean().values

    active_obs: list[list] = []

    for i in range(vol_ma_win + move_candles, n):
        src = i - move_candles
        if volume[src] > vol_ma[src] * vol_mult and not np.isnan(vol_ma[src]):
            is_bearish_candle = close[src] < open_[src]
            is_bullish_candle = close[src] > open_[src]

            if i < n:
                future_max = max(close[src + 1 : i + 1]) if src + 1 <= i else close[src]
                future_min = min(close[src + 1 : i + 1]) if src + 1 <= i else close[src]
                move_up = (future_max - close[src]) / close[src]
                move_down = (close[src] - future_min) / close[src]

                if is_bearish_candle and move_up >= move_thresh:
                    active_obs.append([low[src], high[src], "support", src, 0])
                elif is_bullish_candle and move_down >= move_thresh:
                    active_obs.append([low[src], high[src], "resistance", src, 0])

        new_active = []
        best_support = np.nan
        best_resistance = np.nan
        best_sup_dist = float("inf")
        best_res_dist = float("inf")

        for ob in active_obs:
            zone_low, zone_high, ob_type, birth, touches = ob

            if i - birth > expiry:
                continue

            price = close[i]
            in_zone = zone_low <= price <= zone_high

            if in_zone:
                ob[4] += 1
                if ob[4] > max_touches:
                    continue

            zone_mid = (zone_low + zone_high) / 2
            dist = abs(price - zone_mid)

            if ob_type == "support" and dist < best_sup_dist:
                best_sup_dist = dist
                best_support = zone_mid
                if in_zone:
                    body = abs(close[i] - open_[i])
                    lower_wick = min(close[i], open_[i]) - low[i]
                    total_range = high[i] - low[i]
                    if total_range > 0 and lower_wick / total_range >= wick_ratio:
                        at_support[i] = True
                    elif in_zone:
                        at_support[i] = True

            elif ob_type == "resistance" and dist < best_res_dist:
                best_res_dist = dist
                best_resistance = zone_mid
                if in_zone:
                    body = abs(close[i] - open_[i])
                    upper_wick = high[i] - max(close[i], open_[i])
                    total_range = high[i] - low[i]
                    if total_range > 0 and upper_wick / total_range >= wick_ratio:
                        at_resistance[i] = True
                    elif in_zone:
                        at_resistance[i] = True

            new_active.append(ob)

        active_obs = new_active
        support[i] = best_support
        resistance[i] = best_resistance

    dataframe["support"] = support
    dataframe["resistance"] = resistance
    dataframe["at_support"] = at_support
    dataframe["at_resistance"] = at_resistance

    return dataframe


def _pivot_fractal(dataframe: DataFrame, cfg: dict) -> DataFrame:
    """Detect S/R via Williams fractals with clustering."""
    n_window = cfg["fractal_window"]
    cluster_pct = cfg["cluster_pct"]
    min_touches = cfg["min_touches"]
    proximity_pct = cfg["proximity_pct"]

    high = dataframe["high"].values
    low = dataframe["low"].values
    close = dataframe["close"].values
    n = len(dataframe)

    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    at_support = np.zeros(n, dtype=bool)
    at_resistance = np.zeros(n, dtype=bool)

    fractal_lows: list[tuple[int, float]] = []
    fractal_highs: list[tuple[int, float]] = []

    for i in range(n_window, n - n_window):
        window_low = low[i - n_window : i + n_window + 1]
        window_high = high[i - n_window : i + n_window + 1]

        if low[i] == window_low.min():
            fractal_lows.append((i, low[i]))
        if high[i] == window_high.max():
            fractal_highs.append((i, high[i]))

    def _cluster(points, pct):
        if not points:
            return []
        sorted_pts = sorted(points, key=lambda x: x[1])
        clusters = [[sorted_pts[0]]]
        for idx, val in sorted_pts[1:]:
            if abs(val - clusters[-1][-1][1]) / clusters[-1][-1][1] <= pct:
                clusters[-1].append((idx, val))
            else:
                clusters.append([(idx, val)])
        result = []
        for cluster in clusters:
            if len(cluster) >= min_touches:
                avg_level = sum(v for _, v in cluster) / len(cluster)
                max_idx = max(idx for idx, _ in cluster)
                result.append((avg_level, len(cluster), max_idx))
        return sorted(result, key=lambda x: -x[2])

    support_clusters = _cluster(fractal_lows, cluster_pct)
    resistance_clusters = _cluster(fractal_highs, cluster_pct)

    for i in range(2 * n_window, n):
        price = close[i]

        best_sup = np.nan
        best_sup_dist = float("inf")
        for level, touches, last_idx in support_clusters:
            if last_idx > i:
                continue
            if level <= price * (1 + proximity_pct):
                dist = abs(price - level)
                if dist < best_sup_dist:
                    best_sup_dist = dist
                    best_sup = level

        best_res = np.nan
        best_res_dist = float("inf")
        for level, touches, last_idx in resistance_clusters:
            if last_idx > i:
                continue
            if level >= price * (1 - proximity_pct):
                dist = abs(price - level)
                if dist < best_res_dist:
                    best_res_dist = dist
                    best_res = level

        support[i] = best_sup
        resistance[i] = best_res

        if not np.isnan(best_sup) and abs(price - best_sup) / price <= proximity_pct:
            at_support[i] = True
        if not np.isnan(best_res) and abs(price - best_res) / price <= proximity_pct:
            at_resistance[i] = True

    dataframe["support"] = support
    dataframe["resistance"] = resistance
    dataframe["at_support"] = at_support
    dataframe["at_resistance"] = at_resistance

    return dataframe


def _rolling_minmax(dataframe: DataFrame, cfg: dict, consol_cfg: dict) -> DataFrame:
    """Adaptive rolling min/max with ATR-adjusted window."""
    base_window = cfg["base_window"]
    proximity_pct = cfg["proximity_pct"]

    close = dataframe["close"]
    high = dataframe["high"]
    low = dataframe["low"]

    if "atr_zscore" in dataframe.columns:
        atr_z = dataframe["atr_zscore"].fillna(0)
    else:
        tr = np.maximum(
            high - low,
            np.maximum(
                abs(high - close.shift(1)),
                abs(low - close.shift(1)),
            ),
        )
        atr = tr.rolling(consol_cfg["atr_period"]).mean()
        atr_mean = atr.rolling(consol_cfg["atr_zscore_window"]).mean()
        atr_std = atr.rolling(consol_cfg["atr_zscore_window"]).std()
        atr_z = ((atr - atr_mean) / atr_std.replace(0, np.nan)).fillna(0)

    adaptive_window = (base_window * (1 + atr_z.clip(-0.5, 1.0))).astype(int)
    adaptive_window = adaptive_window.clip(base_window // 2, base_window * 2)

    median_win = int(adaptive_window.median()) if len(adaptive_window) > 0 else base_window

    support_vals = low.rolling(median_win).min()
    resistance_vals = high.rolling(median_win).max()

    dataframe["support"] = support_vals
    dataframe["resistance"] = resistance_vals

    dataframe["at_support"] = (
        ((close - support_vals).abs() / close) <= proximity_pct
    )
    dataframe["at_resistance"] = (
        ((close - resistance_vals).abs() / close) <= proximity_pct
    )

    return dataframe
