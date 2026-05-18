"""Bot Controller — lightweight HTTP server that manages the freqtrade process.

Runs on port 8084 and provides start/stop/switch endpoints.
The freqtrade bot runs as a child process that can be killed and restarted.

Usage:
    .venv/bin/python user_data/bot_controller.py
"""
import json
import os
import signal
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread

BASE_DIR = Path(__file__).parent.parent
VENV_BIN = BASE_DIR / ".venv" / "bin"
FT_BIN = str(VENV_BIN / "freqtrade")
CONFIG = str(BASE_DIR / "user_data" / "configs" / "config_monitor.json")
REPLAY_CONFIG = str(BASE_DIR / "user_data" / "configs" / "replay_config.json")
USERDIR = str(BASE_DIR / "user_data")
STRATEGY = "ZScoreV57Monitor"
LOG_FILE = "/tmp/freqtrade_monitor.log"
PORT = 8084

bot_process = None
bot_mode = "stopped"  # "live", "replay", "stopped"


def start_bot(mode="live", strategy=None):
    global bot_process, bot_mode
    stop_bot()
    time.sleep(1)

    strat = strategy or STRATEGY
    if mode == "replay":
        cmd = [FT_BIN, "replay", "--config", CONFIG, "--replay-config", REPLAY_CONFIG,
               "--strategy", strat, "--userdir", USERDIR]
    else:
        cmd = [FT_BIN, "trade", "--config", CONFIG, "--strategy", strat, "--userdir", USERDIR]

    with open(LOG_FILE, "w") as lf:
        bot_process = subprocess.Popen(cmd, stdout=lf, stderr=lf, preexec_fn=os.setsid)

    bot_mode = mode
    print(f"[controller] Started {mode} mode, PID={bot_process.pid}")


def stop_bot():
    global bot_process, bot_mode
    if bot_process and bot_process.poll() is None:
        print(f"[controller] Stopping PID={bot_process.pid}")
        try:
            os.killpg(os.getpgid(bot_process.pid), signal.SIGTERM)
            bot_process.wait(timeout=10)
        except Exception:
            try:
                os.killpg(os.getpgid(bot_process.pid), signal.SIGKILL)
            except Exception:
                pass
    bot_process = None
    bot_mode = "stopped"


def bot_status():
    if bot_process and bot_process.poll() is None:
        return {"status": "running", "mode": bot_mode, "pid": bot_process.pid}
    return {"status": "stopped", "mode": "stopped", "pid": None}


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept")
        self.send_header("Access-Control-Max-Age", "86400")

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self._json_response(bot_status())
        elif self.path.startswith("/browse"):
            self._handle_browse()
            return
        elif self.path.startswith("/bt-signals"):
            self._handle_bt_signals()
            return
        elif self.path.startswith("/signals"):
            self._handle_signals()
            return
        elif self.path.startswith("/candles"):
            self._handle_candles()
            return
        elif self.path == "/replay_config":
            try:
                with open(REPLAY_CONFIG) as f:
                    self._json_response(json.load(f))
            except Exception:
                self._json_response({"replay_start": "2026-04-01", "replay_end": "2026-05-01", "speed": 0})
        elif self.path == "/logs":
            try:
                with open(LOG_FILE) as f:
                    lines = f.readlines()[-50:]
                self._json_response({"lines": [l.rstrip() for l in lines]})
            except Exception:
                self._json_response({"lines": []})
        else:
            self._json_response({"error": "not found"}, 404)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_len > 0:
            body = json.loads(self.rfile.read(content_len))

        if self.path == "/start":
            mode = body.get("mode", "live")
            strategy = body.get("strategy", STRATEGY)

            if mode == "replay":
                rc = body.get("replay_config")
                if rc:
                    with open(REPLAY_CONFIG, "w") as f:
                        json.dump(rc, f, indent=4)

            start_bot(mode=mode, strategy=strategy)
            time.sleep(2)
            self._json_response({"status": "ok", **bot_status()})

        elif self.path == "/stop":
            stop_bot()
            self._json_response({"status": "ok", **bot_status()})

        elif self.path == "/restart":
            mode = body.get("mode", bot_mode if bot_mode != "stopped" else "live")
            strategy = body.get("strategy", STRATEGY)

            if mode == "replay":
                rc = body.get("replay_config")
                if rc:
                    with open(REPLAY_CONFIG, "w") as f:
                        json.dump(rc, f, indent=4)

            start_bot(mode=mode, strategy=strategy)
            time.sleep(2)
            self._json_response({"status": "ok", **bot_status()})

        else:
            self._json_response({"error": "not found"}, 404)

    def _handle_bt_signals(self):
        """Serve REAL backtest trades + OHLCV candles in same format as /signals."""
        import pandas as pd
        import numpy as np
        import zipfile
        from urllib.parse import urlparse, parse_qs

        params = parse_qs(urlparse(self.path).query)
        start = params.get("start", ["2026-01-01"])[0]
        end = params.get("end", ["2026-05-01"])[0]
        tf = params.get("timeframe", ["5m"])[0]
        bt_file = params.get("file", [""])[0]

        # Find latest backtest ZIP
        bt_dir = BASE_DIR / "user_data" / "backtest_results"
        if bt_file:
            zip_path = bt_dir / bt_file
        else:
            zips = sorted(bt_dir.glob("backtest-result-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not zips:
                self._json_response({"error": "No backtest results found"}, 404)
                return
            zip_path = zips[0]

        # Load trades from ZIP
        try:
            zf = zipfile.ZipFile(zip_path)
            stats_name = [n for n in zf.namelist() if n.endswith('.json') and 'meta' not in n and 'config' not in n][0]
            stats = json.loads(zf.read(stats_name))
            strat = list(stats['strategy'].keys())[0]
            all_trades = stats['strategy'][strat]['trades']
            # Filter trades to requested date range
            trades = [t for t in all_trades if t['open_date'] >= start and t['close_date'] <= end]
            # Always start with wallet value — same as backtest
            range_initial_balance = 100.0
        except Exception as e:
            self._json_response({"error": f"Failed to load backtest: {e}"}, 500)
            return

        # Load OHLCV data
        data_dir = BASE_DIR / "user_data" / "data" / "hyperliquid" / "futures"
        cfg_path = BASE_DIR / "user_data" / "strategies" / "v59_config.json"
        with open(cfg_path) as f:
            cfg = json.load(f)
        all_pairs = cfg["basket"]["pairs"]
        btc_ref = cfg["basket"]["btc_ref"]
        if btc_ref not in all_pairs:
            all_pairs = all_pairs + [btc_ref]

        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")

        # Build per-pair candle data
        # Load PRE-COMPUTED indicators from backtest (feather files)
        # These are generated by ZScoreV52Strategy.populate_indicators during backtest
        # 100% identical to backtest — zero recalculation
        indicator_dir = BASE_DIR / "user_data" / "backtest_results" / "indicators"

        pair_dfs = {}
        for pair in all_pairs:
            c = pair.split("/")[0]
            ind_path = indicator_dir / f"{c}_indicators.feather"
            if ind_path.exists():
                df = pd.read_feather(ind_path)
                df["date"] = pd.to_datetime(df["date"], utc=True)
                df = df[(df["date"] >= start_ts) & (df["date"] < end_ts)].reset_index(drop=True)
                if len(df) > 0:
                    pair_dfs[pair] = df
            else:
                # Fallback: load raw OHLCV without indicators
                fpath = data_dir / f"{c}_USDC_USDC-{tf}-futures.feather"
                if fpath.exists():
                    df = pd.read_feather(fpath)
                    df["date"] = pd.to_datetime(df["date"], utc=True)
                    df = df[(df["date"] >= start_ts) & (df["date"] < end_ts)].reset_index(drop=True)
                    if len(df) > 0:
                        pair_dfs[pair] = df

        # Build result per pair
        result = {}
        n_frames = max((len(df) for df in pair_dfs.values()), default=0)

        for pair, df in pair_dfs.items():
            labels = []
            ohlc = []
            prices = []
            for _, row in df.iterrows():
                d = row["date"]
                labels.append(f"{d.month}/{d.day} {d.hour:02d}:{d.minute:02d}")
                ohlc.append([round(float(row["open"]), 6), round(float(row["close"]), 6),
                             round(float(row["low"]), 6), round(float(row["high"]), 6)])
                prices.append(round(float(row["close"]), 6))

            # All indicators from strategy modules (identical to backtest)
            def col_float(name, decimals=4):
                if name in df.columns:
                    return [round(float(v), decimals) for v in df[name].values]
                return [0.0] * len(df)
            def col_bool(name, default=False):
                if name in df.columns:
                    return [bool(v) for v in df[name].values]
                return [default] * len(df)
            def col_int(name, default=0):
                if name in df.columns:
                    return [int(v) for v in df[name].values]
                return [default] * len(df)

            bz_arr = col_float("basket_z")
            bs_arr = col_float("basket_spread")
            # Backward compat: also try old column names
            if all(v == 0.0 for v in bz_arr[:100]):
                bz_arr = col_float("pair_zscore")
            if all(v == 0.0 for v in bs_arr[:100]):
                bs_arr = col_float("spread_zscore")
            vol_ok_arr = col_bool("vol_ok")
            regime_ok_arr = col_int("regime_ok", 1)
            spread_vol_ok_arr = col_int("spread_vol_ok", 1)
            rolling_corr_arr = col_float("rolling_corr")
            vol_ratio_arr = col_float("vol_ratio", 2)
            btc_mom_arr = col_float("btc_mom")
            btc_atr_z_arr = col_float("btc_atr_z")
            btc_pump_arr = col_bool("btc_pump")
            btc_dump_arr = col_bool("btc_dump")
            btc_high_vol_arr = col_bool("btc_high_vol")

            # Map real trades to candle indices
            pair_trades = [t for t in trades if t["pair"] == pair]
            signals = []
            trade_ranges = []

            for t in pair_trades:
                open_dt = pd.Timestamp(t["open_date"], tz="UTC")
                close_dt = pd.Timestamp(t["close_date"], tz="UTC")

                # Find nearest candle indices
                entry_idx = df["date"].searchsorted(open_dt)
                exit_idx = df["date"].searchsorted(close_dt)
                entry_idx = max(0, min(int(entry_idx), len(df) - 1))
                exit_idx = max(0, min(int(exit_idx), len(df) - 1))

                side = "short" if t.get("is_short", False) else "long"
                tag = t.get("enter_tag", "")
                exit_reason = t.get("exit_reason", "")
                profit_pct = round(t.get("profit_ratio", 0) * 100, 2)
                win = profit_pct > 0

                signals.append({"index": entry_idx, "type": "entry", "side": side, "tag": tag, "price": round(t.get("open_rate", 0), 6)})
                signals.append({"index": exit_idx, "type": "exit", "side": side, "tag": exit_reason, "profit_pct": profit_pct, "win": win})

                trade_ranges.append({
                    "entry_index": entry_idx, "exit_index": exit_idx,
                    "side": side, "tag": tag, "entry_price": round(t.get("open_rate", 0), 6),
                    "profit_pct": profit_pct, "profit_abs": round(t.get("profit_abs", 0), 4),
                    "win": win, "exit_tag": exit_reason,
                    "stake_amount": round(t.get("stake_amount", 0), 2),
                    "leverage": t.get("leverage", 1),
                    "trade_duration": t.get("trade_duration", 0),
                })

            result[pair] = {
                "labels": labels, "ohlc": ohlc, "price": prices,
                "basket_z": bz_arr,
                "basket_spread": bs_arr,
                # Keep old names for backward compat with existing UI code
                "pair_zscore": bz_arr,
                "spread_zscore": bs_arr,
                "regime_ok": regime_ok_arr,
                "spread_vol_ok": spread_vol_ok_arr,
                "rolling_corr": rolling_corr_arr,
                "vol_ratio": vol_ratio_arr,
                "btc_mom": btc_mom_arr,
                "btc_atr_z": btc_atr_z_arr,
                "btc_pump": btc_pump_arr,
                "btc_dump": btc_dump_arr,
                "btc_high_vol": btc_high_vol_arr,
                "signals": signals, "trade_ranges": trade_ranges,
                "vol_ok": vol_ok_arr,
                "count": len(labels),
            }

        # ── V59: Pre-compute scoring, queue (always-on), and trade_type ──
        queue_cfg = cfg.get("queue", {})
        weights = queue_cfg.get("weights", {})
        w_bz = weights.get("basket_z", 0.5)
        w_vol = weights.get("vol_ratio", 0.2)
        w_vel = weights.get("spread_velocity", 0.2)
        w_cd = weights.get("cooldown", 0.1)
        cooldown_candles = queue_cfg.get("cooldown_candles", 36)
        regime_mults = queue_cfg.get("regime_multipliers", {
            "bull_long": 1.0, "bull_short": 0.3,
            "ranging_long": 0.6, "ranging_short": 0.6,
            "bear_long": 0.3, "bear_short": 1.0,
        })

        tradable = [p for p in result if not p.startswith("_") and not p.startswith("BTC")]

        # Initialize new arrays for all pairs (including BTC)
        for pair in list(result.keys()):
            if pair.startswith("_"):
                continue
            n = result[pair]["count"]
            result[pair]["score"] = [0.0] * n
            result[pair]["score_adjusted"] = [0.0] * n
            result[pair]["score_bz"] = [0.0] * n
            result[pair]["score_vol"] = [0.0] * n
            result[pair]["score_vel"] = [0.0] * n
            result[pair]["score_cd"] = [0.0] * n
            result[pair]["queue_side"] = [""] * n
            result[pair]["queue_rank"] = [0] * n
            result[pair]["cooldown_remaining"] = [0] * n
            result[pair]["trade_type"] = ["mean_reversion"] * n
            result[pair]["regime_mult"] = [1.0] * n

        last_exit = {}

        for i in range(n_frames):
            # Determine open trades at this candle
            open_at_i = set()
            for pair in tradable:
                for tr in result[pair].get("trade_ranges", []):
                    if tr["entry_index"] <= i <= tr["exit_index"]:
                        open_at_i.add(pair)
                    if tr["exit_index"] == i:
                        last_exit[pair] = i

            # Determine regime from BTC momentum
            btc_mom_i = 0.0
            for pair in tradable:
                r = result[pair]
                if i < len(r.get("btc_mom", [])):
                    btc_mom_i = r["btc_mom"][i]
                    break
            if btc_mom_i > 0.0:
                regime = "bull"
            elif btc_mom_i <= -1.0:
                regime = "bear"
            else:
                regime = "ranging"

            long_mult = regime_mults.get(f"{regime}_long", 0.6)
            short_mult = regime_mults.get(f"{regime}_short", 0.6)

            # Compute scores + trade_type for all tradable pairs
            for pair in tradable:
                r = result[pair]
                if i >= r["count"]:
                    continue

                bz = abs(r["basket_z"][i])
                vr = r["vol_ratio"][i] if i < len(r.get("vol_ratio", [])) else 1.0
                bz_prev = r["basket_z"][i - 3] if i >= 3 else r["basket_z"][i]
                velocity = abs(r["basket_z"][i] - bz_prev)

                bz_norm = min(bz, 4.0) / 4.0
                vol_norm = min(vr, 3.0) / 3.0
                vel_norm = min(velocity, 2.0) / 2.0
                le = last_exit.get(pair, -999)
                cd_norm = 0.0 if (i - le) < cooldown_candles else 1.0
                cd_remaining = max(0, cooldown_candles - (i - le)) if le >= 0 else 0

                raw_score = w_bz * bz_norm + w_vol * vol_norm + w_vel * vel_norm + w_cd * cd_norm

                # Apply regime multiplier based on z direction
                bz_val = r["basket_z"][i]
                if bz_val < 0:
                    mult = long_mult
                elif bz_val > 0:
                    mult = short_mult
                else:
                    mult = 0.0
                adj_score = raw_score * mult

                r["score"][i] = round(raw_score, 4)
                r["score_adjusted"][i] = round(adj_score, 4)
                r["score_bz"][i] = round(bz_norm, 4)
                r["score_vol"][i] = round(vol_norm, 4)
                r["score_vel"][i] = round(vel_norm, 4)
                r["score_cd"][i] = round(cd_norm, 4)
                r["cooldown_remaining"][i] = cd_remaining
                r["regime_mult"][i] = round(mult, 2)

                # Trade type classification
                mom = r["btc_mom"][i] if i < len(r.get("btc_mom", [])) else 0.0
                atr_z = r["btc_atr_z"][i] if i < len(r.get("btc_atr_z", [])) else 0.0
                if velocity >= 1.0 and vr >= 2.0:
                    r["trade_type"][i] = "breakout"
                elif abs(mom) >= 1.5 and atr_z < 2.0:
                    r["trade_type"][i] = "trending"
                else:
                    r["trade_type"][i] = "mean_reversion"

            # Build queues — V59: ALL pairs in queue, z<0→long, z>0→short
            long_cand = []
            short_cand = []
            for pair in tradable:
                r = result[pair]
                if i >= r["count"]:
                    continue

                bz_val = r["basket_z"][i]
                adj = r["score_adjusted"][i]

                # All pairs go into a queue based on z sign (open trades included for display)
                if bz_val < 0:
                    long_cand.append((pair, adj, pair in open_at_i))
                elif bz_val > 0:
                    short_cand.append((pair, adj, pair in open_at_i))

            # Sort by adjusted score descending
            long_cand.sort(key=lambda x: x[1], reverse=True)
            short_cand.sort(key=lambda x: x[1], reverse=True)

            # Assign ranks to ALL pairs in queue (not just top-K)
            for rank, (pair, _, is_open) in enumerate(long_cand, 1):
                result[pair]["queue_side"][i] = "long"
                result[pair]["queue_rank"][i] = rank
            for rank, (pair, _, is_open) in enumerate(short_cand, 1):
                result[pair]["queue_side"][i] = "short"
                result[pair]["queue_rank"][i] = rank

        # Tag each trade_range with entry trade_type, score, and regime_mult
        for pair in tradable:
            for tr in result[pair].get("trade_ranges", []):
                ei = tr["entry_index"]
                if ei < len(result[pair]["trade_type"]):
                    tr["trade_type"] = result[pair]["trade_type"][ei]
                else:
                    tr["trade_type"] = "mean_reversion"
                if ei < len(result[pair]["score"]):
                    tr["entry_score"] = result[pair]["score"][ei]
                    tr["entry_score_adjusted"] = result[pair]["score_adjusted"][ei]
                else:
                    tr["entry_score"] = 0.0
                    tr["entry_score_adjusted"] = 0.0

        # Build equity curve from REAL profit_abs values
        # range_initial_balance includes profit from trades before this range
        initial_balance = range_initial_balance
        equity = [initial_balance] * n_frames
        balance = initial_balance

        sorted_trades = sorted(trades, key=lambda t: t["close_date"])
        for t in sorted_trades:
            close_dt = pd.Timestamp(t["close_date"], tz="UTC")
            pair = t["pair"]
            if pair not in pair_dfs:
                continue
            exit_idx = int(pair_dfs[pair]["date"].searchsorted(close_dt))
            exit_idx = max(0, min(exit_idx, n_frames - 1))
            balance += t["profit_abs"]
            for i in range(exit_idx, n_frames):
                equity[i] = round(balance, 2)

        # Pre-compute summary stats from filtered trades
        total_profit = sum(t["profit_abs"] for t in trades)
        wins = sum(1 for t in trades if t["profit_ratio"] > 0)
        losses = len(trades) - wins
        win_pct = round(wins / len(trades) * 100, 1) if trades else 0
        final_balance = round(initial_balance + total_profit, 2)
        profit_pct = round(total_profit / initial_balance * 100, 2)

        result["_equity"] = {"equity": equity, "initial": initial_balance}
        result["_summary"] = {
            "total_trades": len(trades),
            "total_trades_all": len(all_trades),
            "wins": wins,
            "losses": losses,
            "win_pct": win_pct,
            "total_profit_abs": round(total_profit, 2),
            "profit_pct": profit_pct,
            "final_balance": final_balance,
            "initial_balance": round(initial_balance, 2),
        }
        result["_meta"] = {
            "strategy": strat, "bot_name": "V59 Always-On Queue",
            "backtest_file": zip_path.name,
            "trades": len(trades), "timeframe": tf,
            "basket_pairs": [p for p in all_pairs if p != btc_ref],
            "btc_ref": btc_ref,
            "queue_config": cfg.get("queue", {}),
        }

        self._json_response(result)

    def _handle_signals(self):
        """Compute z-scores, entry/exit signals, and simulate trades from OHLCV data."""
        import pandas as pd
        import numpy as np
        from urllib.parse import urlparse, parse_qs

        params = parse_qs(urlparse(self.path).query)
        start = params.get("start", ["2026-04-01"])[0]
        end = params.get("end", ["2026-05-01"])[0]
        tf = params.get("timeframe", ["15m"])[0]

        # Load config
        cfg_path = BASE_DIR / "user_data" / "strategies" / "v57_config.json"
        with open(cfg_path) as f:
            cfg = json.load(f)

        data_dir = BASE_DIR / "user_data" / "data" / "hyperliquid" / "futures"
        group_a = cfg["groups"]["group_a"]
        group_b = cfg["groups"]["group_b"]
        btc_ref = cfg["groups"]["btc_ref"]
        all_pairs = group_a + group_b + [btc_ref]
        zw = cfg["zscore"]["zscore_window"]
        crw = cfg["zscore"]["cum_return_window"]
        z_entry = cfg["zscore"]["zscore_entry"]
        pz_entry = cfg["zscore"]["pair_z_entry"]
        scalp_profit = cfg["zscore"]["zscore_scalp_min_profit"]
        vol_window = cfg["volume"]["vol_ma_window"]
        vol_thresh = cfg["volume"]["vol_ok_threshold"]
        stoploss = cfg["risk"]["stoploss"]
        roi = cfg["risk"]["minimal_roi"]

        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")
        # Load extra data for startup
        startup_td = pd.Timedelta(seconds=300 * 900)  # 300 candles * 15m
        load_start = start_ts - startup_td

        # Load all pair data
        pair_dfs = {}
        for pair in all_pairs:
            coin = pair.split("/")[0]
            fpath = data_dir / f"{coin}_USDC_USDC-{tf}-futures.feather"
            if not fpath.exists():
                continue
            df = pd.read_feather(fpath)
            df["date"] = pd.to_datetime(df["date"], utc=True)
            df = df[(df["date"] >= load_start) & (df["date"] < end_ts)].reset_index(drop=True)
            if len(df) == 0:
                continue

            # Compute pair z-score
            df["log_return"] = np.log(df["close"] / df["close"].shift(1))
            cum_ret = df["log_return"].rolling(crw).sum()
            cum_mean = cum_ret.rolling(zw).mean()
            cum_std = cum_ret.rolling(zw).std()
            df["pair_zscore"] = ((cum_ret - cum_mean) / cum_std.replace(0, np.nan)).fillna(0.0)

            # Volume
            vol_ma = df["volume"].rolling(vol_window).mean()
            df["vol_ratio"] = (df["volume"] / vol_ma.replace(0, np.nan)).fillna(1.0)
            df["vol_ok"] = (df["vol_ratio"] > vol_thresh).astype(int)

            pair_dfs[pair] = df

        # Compute spread z-score
        for pair in all_pairs:
            if pair not in pair_dfs:
                continue
            df = pair_dfs[pair]
            a_zs = [pair_dfs[p]["pair_zscore"].iloc[-len(df):].reset_index(drop=True) for p in group_a if p in pair_dfs]
            b_zs = [pair_dfs[p]["pair_zscore"].iloc[-len(df):].reset_index(drop=True) for p in group_b if p in pair_dfs]
            if a_zs and b_zs:
                spread = sum(a_zs) / len(a_zs) - sum(b_zs) / len(b_zs)
                sm = spread.rolling(zw).mean()
                ss = spread.rolling(zw).std()
                df["spread_zscore"] = ((spread - sm) / ss.replace(0, np.nan)).fillna(0.0)
            else:
                df["spread_zscore"] = 0.0

        # Detect signals and simulate trades
        wait_all_closed = cfg.get("balance", {}).get("wait_all_closed", False)

        # First pass: build labels/ohlc/z-scores for all pairs
        pair_frames = {}
        for pair in all_pairs:
            if pair not in pair_dfs:
                continue
            df = pair_dfs[pair]
            df = df[df["date"] >= start_ts].reset_index(drop=True)
            is_a = pair in group_a
            is_b = pair in group_b

            labels, prices, ohlc_arr, pair_z_arr, spread_z_arr = [], [], [], [], []
            for _, row in df.iterrows():
                d = row["date"]
                labels.append(f"{d.month}/{d.day} {d.hour:02d}:{d.minute:02d}")
                prices.append(round(float(row["close"]), 6))
                ohlc_arr.append([round(float(row["open"]), 6), round(float(row["close"]), 6),
                                 round(float(row["low"]), 6), round(float(row["high"]), 6)])
                pair_z_arr.append(round(float(row["pair_zscore"]), 4))
                spread_z_arr.append(round(float(row["spread_zscore"]), 4))

            pair_frames[pair] = {
                "labels": labels, "prices": prices, "ohlc": ohlc_arr,
                "pair_z": pair_z_arr, "spread_z": spread_z_arr,
                "is_a": is_a, "is_b": is_b,
                "vol_ok": [bool(df.iloc[j]["vol_ok"]) if j < len(df) else False for j in range(len(labels))],
            }

        # Second pass: simulate trades frame by frame across all pairs
        n_frames = max((len(v["labels"]) for v in pair_frames.values()), default=0)
        trade_state = {}  # pair -> {in_trade, entry_price, entry_idx, side, tag}
        for pair in pair_frames:
            trade_state[pair] = {"in_trade": False, "entry_price": 0, "entry_idx": 0, "side": "", "tag": ""}
        signals_per_pair = {pair: [] for pair in pair_frames}

        for idx in range(n_frames):
            # Count globally open trades
            global_open = sum(1 for s in trade_state.values() if s["in_trade"])

            for pair, pf in pair_frames.items():
                if idx >= len(pf["labels"]):
                    continue
                st = trade_state[pair]
                pz = pf["pair_z"][idx]
                sz = pf["spread_z"][idx]
                close = pf["prices"][idx]
                vol_ok = pf["vol_ok"][idx]

                if st["in_trade"]:
                    # Check exits
                    if st["side"] == "long":
                        profit = (close - st["entry_price"]) / st["entry_price"]
                    else:
                        profit = (st["entry_price"] - close) / st["entry_price"]

                    exit_reason = None
                    if profit <= stoploss:
                        exit_reason = "stop_loss"
                    elif profit >= scalp_profit:
                        if st["side"] == "long" and pz > 0:
                            exit_reason = "zscore_scalp"
                        elif st["side"] == "short" and pz < 0:
                            exit_reason = "zscore_scalp"

                    candles_in = idx - st["entry_idx"]
                    minutes_in = candles_in * 15
                    if not exit_reason:
                        for roi_min, roi_val in sorted(roi.items(), key=lambda x: int(x[0])):
                            if minutes_in >= int(roi_min) and profit >= roi_val:
                                exit_reason = "roi"
                                break

                    if exit_reason:
                        signals_per_pair[pair].append({
                            "index": idx, "type": "exit", "side": st["side"],
                            "tag": exit_reason,
                            "profit_pct": round(profit * 100, 2),
                            "win": profit > 0,
                        })
                        st["in_trade"] = False
                else:
                    # Check entries
                    if not vol_ok:
                        continue
                    # Block if wait_all_closed and any trade is open
                    if wait_all_closed and global_open > 0:
                        continue

                    entry_tag = None
                    side = None
                    if pf["is_a"] and sz < -z_entry and pz < -pz_entry:
                        entry_tag = "mr_long_a"
                        side = "long"
                    elif pf["is_b"] and sz < -z_entry and pz > pz_entry:
                        entry_tag = "mr_short_b"
                        side = "short"
                    elif pf["is_b"] and sz > z_entry and pz < -pz_entry:
                        entry_tag = "mr_long_b"
                        side = "long"

                    if entry_tag:
                        signals_per_pair[pair].append({
                            "index": idx, "type": "entry", "side": side,
                            "tag": entry_tag, "price": round(close, 6),
                        })
                        st["in_trade"] = True
                        st["entry_price"] = close
                        st["entry_idx"] = idx
                        st["side"] = side
                        st["tag"] = entry_tag

        result = {}
        for pair, pf in pair_frames.items():
            signals = signals_per_pair[pair]
            labels = pf["labels"]
            ohlc = pf["ohlc"]
            prices = pf["prices"]
            pair_z = pf["pair_z"]
            spread_z = pf["spread_z"]

                # Build active trade ranges
            trade_ranges = []
            i_sig = 0
            while i_sig < len(signals):
                s = signals[i_sig]
                if s["type"] == "entry":
                    exit_sig = None
                    for j in range(i_sig + 1, len(signals)):
                        if signals[j]["type"] == "exit":
                            exit_sig = signals[j]
                            i_sig = j
                            break
                    trade_ranges.append({
                        "entry_index": s["index"],
                        "exit_index": exit_sig["index"] if exit_sig else len(labels) - 1,
                        "side": s["side"],
                        "tag": s["tag"],
                        "entry_price": s.get("price", 0),
                        "profit_pct": exit_sig["profit_pct"] if exit_sig else None,
                        "win": exit_sig.get("win", False) if exit_sig else None,
                        "exit_tag": exit_sig["tag"] if exit_sig else "open",
                    })
                i_sig += 1

            # Vol ok per frame
            df_trimmed = pair_dfs[pair][pair_dfs[pair]["date"] >= start_ts].reset_index(drop=True)
            vol_ok_arr = [bool(df_trimmed.iloc[j]["vol_ok"]) if j < len(df_trimmed) else False for j in range(len(labels))]

            result[pair] = {
                "labels": labels, "ohlc": ohlc, "price": prices,
                "pair_zscore": pair_z, "spread_zscore": spread_z,
                "signals": signals, "trade_ranges": trade_ranges,
                "vol_ok": vol_ok_arr,
                "count": len(labels),
            }

        # Build equity curve across ALL pairs
        initial_balance = 100.0
        equity = [initial_balance] * (totalFrames if (totalFrames := max(v["count"] for v in result.values())) else 0)
        balance = initial_balance
        all_trades = []
        for pair_data in result.values():
            for tr in pair_data.get("trade_ranges", []):
                all_trades.append(tr)
        all_trades.sort(key=lambda t: t["exit_index"])
        for tr in all_trades:
            if tr["profit_pct"] is not None:
                profit_abs = balance * (tr["profit_pct"] / 100) * 0.4  # 40% stake
                balance += profit_abs
                for i in range(tr["exit_index"], len(equity)):
                    equity[i] = round(balance, 2)

        result["_equity"] = {"equity": equity, "initial": initial_balance}

        self._json_response(result)

    def _handle_candles(self):
        """Return ALL candles for a coin in a date range. Used by Monitor for bulk load."""
        import pandas as pd
        from urllib.parse import urlparse, parse_qs

        params = parse_qs(urlparse(self.path).query)
        coin = params.get("coin", ["BTC"])[0]
        start = params.get("start", ["2026-04-01"])[0]
        end = params.get("end", ["2026-05-01"])[0]
        tf = params.get("timeframe", ["15m"])[0]

        data_dir = BASE_DIR / "user_data" / "data" / "hyperliquid" / "futures"
        fpath = data_dir / f"{coin}_USDC_USDC-{tf}-futures.feather"

        if not fpath.exists():
            self._json_response({"labels": [], "ohlc": [], "price": [], "error": f"No data for {coin}"})
            return

        df = pd.read_feather(fpath)
        df["date"] = pd.to_datetime(df["date"], utc=True)
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")
        df = df[(df["date"] >= start_ts) & (df["date"] < end_ts)].reset_index(drop=True)

        labels = []
        ohlc = []
        prices = []
        for _, row in df.iterrows():
            d = row["date"]
            labels.append(f"{d.month}/{d.day} {d.hour:02d}:{d.minute:02d}")
            # ECharts candlestick: [open, close, low, high]
            ohlc.append([
                round(float(row["open"]), 6),
                round(float(row["close"]), 6),
                round(float(row["low"]), 6),
                round(float(row["high"]), 6),
            ])
            prices.append(round(float(row["close"]), 6))

        self._json_response({"labels": labels, "ohlc": ohlc, "price": prices, "count": len(labels)})

    def _handle_browse(self):
        """Browse historical feather data frame by frame. No bot required."""
        import pandas as pd
        from urllib.parse import urlparse, parse_qs

        params = parse_qs(urlparse(self.path).query)
        start = params.get("start", ["2026-04-01"])[0]
        end = params.get("end", ["2026-04-15"])[0]
        index = int(params.get("index", ["0"])[0])
        tf = params.get("timeframe", ["15m"])[0]

        data_dir = BASE_DIR / "user_data" / "data" / "hyperliquid" / "futures"
        pairs = ["XRP/USDC:USDC", "ADA/USDC:USDC", "SOL/USDC:USDC", "LINK/USDC:USDC", "BTC/USDC:USDC"]

        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")

        result = {"candles": {}, "index": index, "total": 0, "timestamp": "",
                  "start": start, "end": end, "timeframe": tf}

        for pair in pairs:
            coin = pair.split("/")[0]
            fpath = data_dir / f"{coin}_USDC_USDC-{tf}-futures.feather"
            if not fpath.exists():
                continue
            df = pd.read_feather(fpath)
            df["date"] = pd.to_datetime(df["date"], utc=True)
            df = df[(df["date"] >= start_ts) & (df["date"] < end_ts)].reset_index(drop=True)
            if len(df) == 0:
                continue
            if result["total"] == 0:
                result["total"] = len(df)
            idx = max(0, min(index, len(df) - 1))
            row = df.iloc[idx]
            result["timestamp"] = str(row["date"])
            result["candles"][pair] = {
                "date": str(row["date"]),
                "open": round(float(row["open"]), 6),
                "high": round(float(row["high"]), 6),
                "low": round(float(row["low"]), 6),
                "close": round(float(row["close"]), 6),
                "volume": round(float(row["volume"]), 2),
            }

        result["index"] = max(0, min(index, max(result["total"] - 1, 0)))
        self._json_response(result)

    def log_message(self, fmt, *args):
        print(f"[controller] {args[0]}")


def main():
    # Kill any existing freqtrade
    os.system("pkill -f 'freqtrade trade.*config_monitor' 2>/dev/null")
    os.system("pkill -f 'freqtrade replay.*config_monitor' 2>/dev/null")
    time.sleep(1)

    # Only start bot if --live flag is passed
    if "--live" in sys.argv:
        start_bot("live")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[controller] Listening on http://0.0.0.0:{PORT}")
    print(f"[controller] Endpoints: GET /status, /logs | POST /start, /stop, /restart")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[controller] Shutting down...")
        stop_bot()
        server.server_close()


if __name__ == "__main__":
    main()
