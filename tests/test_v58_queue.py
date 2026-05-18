"""Tests for V58 queue scoring module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "user_data" / "strategies"))

from zscore_v58.entry_queue import compute_scores, build_queues, update_confirmation, reset


def _make_cfg():
    return {
        "queue": {
            "top_k": 3,
            "confirm_candles": 3,
            "cooldown_candles": 36,
            "weights": {
                "basket_z": 0.5,
                "vol_ratio": 0.2,
                "spread_velocity": 0.2,
                "cooldown": 0.1,
            },
        },
        "basket": {"entry_z": 2.0, "bull_mom_threshold": 0.0, "bear_mom_threshold": -1.0},
    }


def test_compute_scores_basic():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {
            "basket_z": -3.0,
            "basket_z_prev3": -1.5,
            "vol_ratio": 2.0,
            "vol_ok": True,
            "btc_mom": 1.0,
            "btc_pump": False,
            "btc_dump": False,
            "btc_high_vol": False,
        },
        "SOL/USDC:USDC": {
            "basket_z": -1.0,
            "basket_z_prev3": -0.5,
            "vol_ratio": 1.0,
            "vol_ok": True,
            "btc_mom": 1.0,
            "btc_pump": False,
            "btc_dump": False,
            "btc_high_vol": False,
        },
    }
    scores = compute_scores(pair_data, cfg, candle_index=100)
    assert "ETH/USDC:USDC" in scores
    assert "SOL/USDC:USDC" in scores
    assert scores["ETH/USDC:USDC"] > scores["SOL/USDC:USDC"]


def test_compute_scores_normalization_caps():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {
            "basket_z": -10.0,
            "basket_z_prev3": -5.0,
            "vol_ratio": 10.0,
            "vol_ok": True,
            "btc_mom": 1.0,
            "btc_pump": False,
            "btc_dump": False,
            "btc_high_vol": False,
        },
    }
    scores = compute_scores(pair_data, cfg, candle_index=100)
    assert 0.0 <= scores["ETH/USDC:USDC"] <= 1.0


def test_build_queues_long():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {"basket_z": -3.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "SOL/USDC:USDC": {"basket_z": -2.5, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "LINK/USDC:USDC": {"basket_z": -1.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "XRP/USDC:USDC": {"basket_z": 3.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
    }
    scores = {"ETH/USDC:USDC": 0.9, "SOL/USDC:USDC": 0.7, "LINK/USDC:USDC": 0.3, "XRP/USDC:USDC": 0.8}
    open_pairs = set()
    long_q, short_q = build_queues(scores, pair_data, cfg, open_pairs)
    assert long_q == ["ETH/USDC:USDC", "SOL/USDC:USDC"]
    assert short_q == []


def test_build_queues_short():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {"basket_z": 3.0, "btc_mom": -2.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
        "SOL/USDC:USDC": {"basket_z": 2.5, "btc_mom": -2.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
    }
    scores = {"ETH/USDC:USDC": 0.9, "SOL/USDC:USDC": 0.7}
    open_pairs = set()
    long_q, short_q = build_queues(scores, pair_data, cfg, open_pairs)
    assert long_q == []
    assert short_q == ["ETH/USDC:USDC", "SOL/USDC:USDC"]


def test_build_queues_excludes_open_trades():
    reset()
    cfg = _make_cfg()
    pair_data = {
        "ETH/USDC:USDC": {"basket_z": -3.0, "btc_mom": 1.0, "btc_pump": False, "btc_dump": False, "btc_high_vol": False, "vol_ok": True},
    }
    scores = {"ETH/USDC:USDC": 0.9}
    open_pairs = {"ETH/USDC:USDC"}
    long_q, short_q = build_queues(scores, pair_data, cfg, open_pairs)
    assert long_q == []


def test_confirmation_3_candles():
    reset()
    cfg = _make_cfg()
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == []
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == []
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == [("ETH/USDC:USDC", "long")]


def test_confirmation_resets_on_drop():
    reset()
    cfg = _make_cfg()
    update_confirmation(["ETH/USDC:USDC"], [], cfg)
    update_confirmation(["ETH/USDC:USDC"], [], cfg)
    update_confirmation([], [], cfg)
    ready = update_confirmation(["ETH/USDC:USDC"], [], cfg)
    assert ready == []
