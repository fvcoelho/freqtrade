"""Tests for V59 always-on queue."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "user_data" / "strategies"))

from zscore_v59.entry_queue import compute_scores, apply_regime_multiplier, build_queues, get_entry_candidate, reset, _get_regime


def _cfg():
    return {
        "queue": {
            "min_score": 0.45, "cooldown_candles": 36,
            "weights": {"basket_z": 0.5, "vol_ratio": 0.2, "spread_velocity": 0.2, "cooldown": 0.1},
            "regime_multipliers": {"bull_long": 1.0, "bull_short": 0.3, "ranging_long": 0.6, "ranging_short": 0.6, "bear_long": 0.3, "bear_short": 1.0},
        },
    }


def _pair(basket_z=-2.0, vol_ratio=1.5, btc_mom=1.0, vol_ok=True, btc_pump=False, btc_dump=False, btc_high_vol=False, basket_z_prev3=None):
    return {"basket_z": basket_z, "basket_z_prev3": basket_z_prev3 if basket_z_prev3 is not None else basket_z,
            "vol_ratio": vol_ratio, "vol_ok": vol_ok, "btc_mom": btc_mom, "btc_pump": btc_pump, "btc_dump": btc_dump, "btc_high_vol": btc_high_vol}


def test_regime_detection():
    assert _get_regime(1.0) == "bull"
    assert _get_regime(0.1) == "bull"
    assert _get_regime(0.0) == "ranging"
    assert _get_regime(-0.5) == "ranging"
    assert _get_regime(-1.0) == "bear"
    assert _get_regime(-2.0) == "bear"


def test_all_pairs_in_queues():
    reset()
    pair_data = {"ETH": _pair(basket_z=-2.0), "SOL": _pair(basket_z=-0.5), "LINK": _pair(basket_z=1.5), "XRP": _pair(basket_z=3.0)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    assert "ETH" in long_adj and "SOL" in long_adj
    assert "LINK" in short_adj and "XRP" in short_adj
    assert "ETH" not in short_adj and "LINK" not in long_adj


def test_regime_multiplier_bull():
    reset()
    pair_data = {"ETH": _pair(basket_z=-2.0, btc_mom=1.0, vol_ratio=2.0), "SOL": _pair(basket_z=2.0, btc_mom=1.0, vol_ratio=2.0)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    assert raw["ETH"] == raw["SOL"]
    assert long_adj["ETH"] > short_adj["SOL"]


def test_regime_multiplier_bear():
    reset()
    pair_data = {"ETH": _pair(basket_z=-2.0, btc_mom=-2.0), "SOL": _pair(basket_z=2.0, btc_mom=-2.0)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    assert long_adj["ETH"] < short_adj["SOL"]


def test_queue_ranking():
    reset()
    pair_data = {"ETH": _pair(basket_z=-3.0, vol_ratio=2.5), "SOL": _pair(basket_z=-1.0, vol_ratio=1.0), "LINK": _pair(basket_z=-2.0, vol_ratio=1.5)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    long_q, _ = build_queues(long_adj, short_adj, pair_data, set())
    assert long_q[0][0] == "ETH"
    assert len(long_q) == 3


def test_only_number_one_enters():
    reset()
    pair_data = {"ETH": _pair(basket_z=-3.0, vol_ratio=2.0, basket_z_prev3=-1.5), "SOL": _pair(basket_z=-2.5, vol_ratio=1.5, basket_z_prev3=-1.0)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    long_q, short_q = build_queues(long_adj, short_adj, pair_data, set())
    ready = get_entry_candidate(long_q, short_q, pair_data, _cfg())
    assert len(ready) <= 1
    if ready: assert ready[0][0] == "ETH"


def test_min_score_rejects():
    reset()
    pair_data = {"ETH": _pair(basket_z=-0.2, btc_mom=0.5, vol_ratio=0.5, basket_z_prev3=-0.2)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, _ = apply_regime_multiplier(raw, pair_data, _cfg())
    long_q, short_q = build_queues(long_adj, {}, pair_data, set())
    ready = get_entry_candidate(long_q, short_q, pair_data, _cfg())
    assert len(ready) == 0


def test_open_trade_excluded():
    reset()
    pair_data = {"ETH": _pair(basket_z=-3.0), "SOL": _pair(basket_z=-2.0)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    long_q, _ = build_queues(long_adj, short_adj, pair_data, {"ETH"})
    assert long_q[0][0] == "SOL"


def test_safety_blocks():
    reset()
    pair_data = {"ETH": _pair(basket_z=-3.0, vol_ratio=3.0, btc_dump=True, basket_z_prev3=-1.5)}
    raw = compute_scores(pair_data, _cfg(), 100)
    long_adj, short_adj = apply_regime_multiplier(raw, pair_data, _cfg())
    long_q, short_q = build_queues(long_adj, short_adj, pair_data, set())
    ready = get_entry_candidate(long_q, short_q, pair_data, _cfg())
    assert len(ready) == 0
