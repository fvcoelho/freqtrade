"""Regime Agent: determines market state from BTC data."""
from __future__ import annotations

import logging

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

logger = logging.getLogger(__name__)


class RegimeState:
    """Current market regime state."""

    def __init__(self):
        self.regime: str = "ranging"
        self.strength: float = 0.0
        self.btc_momentum: float = 0.0
        self.btc_adx: float = 0.0

    def get_multiplier(self, side: str, cfg: dict) -> float:
        mults = cfg.get("entry", {}).get("regime_multipliers", {})
        key = f"{self.regime}_{side}"
        return mults.get(key, 0.5)

    def __repr__(self):
        return f"Regime({self.regime}, str={self.strength:.2f}, mom={self.btc_momentum:.2f})"


class RegimeAgent:
    """Analyzes BTC data to determine market regime."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.state = RegimeState()
        self._rcfg = cfg.get("regime", {})

    def update(self, btc_df: DataFrame) -> RegimeState:
        if btc_df is None or len(btc_df) < 30:
            return self.state

        adx_ranging = self._rcfg.get("adx_ranging", 18)
        adx_trending = self._rcfg.get("adx_trending", 25)
        mom_window = self._rcfg.get("btc_momentum_window", 48)

        adx = ta.ADX(btc_df, timeperiod=14)
        ema21 = ta.EMA(btc_df, timeperiod=21)
        momentum = ta.ROC(btc_df, timeperiod=mom_window)

        last_adx = adx.iloc[-1] if not adx.empty else 0
        last_mom = momentum.iloc[-1] if not momentum.empty else 0

        if len(ema21) >= 4:
            last_slope = (ema21.iloc[-1] - ema21.iloc[-4]) / (ema21.iloc[-4] + 1e-10) * 100
        else:
            last_slope = 0

        if last_adx < adx_ranging:
            regime = "ranging"
            strength = 1.0 - (last_adx / adx_ranging)
        elif last_mom > 0 and last_slope > 0:
            regime = "bull"
            strength = min(last_adx / 50.0, 1.0)
        elif last_mom < 0 and last_slope < 0:
            regime = "bear"
            strength = min(last_adx / 50.0, 1.0)
        else:
            regime = "ranging"
            strength = 0.3

        self.state.regime = regime
        self.state.strength = float(strength)
        self.state.btc_momentum = float(last_mom) if not np.isnan(last_mom) else 0.0
        self.state.btc_adx = float(last_adx) if not np.isnan(last_adx) else 0.0

        logger.info(f"[ZAP:Regime] {self.state}")
        return self.state
