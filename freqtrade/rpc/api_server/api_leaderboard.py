import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter


logger = logging.getLogger(__name__)

router = APIRouter()

LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"


async def _classify_trader(
    client: httpx.AsyncClient, address: str
) -> dict[str, Any] | None:
    """Check fills for a trader and classify as bot or real trader.

    Returns classification dict or None if the address has no fills.
    A trader is considered a bot if:
      - avg trade size < $5,000 AND trades span < 1 hour AND > 50 fills
    """
    try:
        r = await client.post(
            HL_INFO_URL,
            json={"type": "userFills", "user": address},
            timeout=10,
        )
        fills = r.json()
        if not fills:
            return {"traderType": "unknown", "hasPositions": False, "fillCount": 0}

        closed = [f for f in fills if float(f.get("closedPnl", "0")) != 0]

        # Average notional of recent closed fills
        sample = closed[:50] if closed else fills[:50]
        avg_notional = (
            sum(float(f["sz"]) * float(f["px"]) for f in sample) / len(sample)
            if sample
            else 0
        )

        # Time span of last 50 fills
        times = [f["time"] for f in fills[:50]]
        span_hours = (times[0] - times[-1]) / 3_600_000 if len(times) > 1 else 0

        # Check for open positions
        pos_r = await client.post(
            HL_INFO_URL,
            json={"type": "clearinghouseState", "user": address},
            timeout=10,
        )
        state = pos_r.json()
        positions = state.get("assetPositions", [])
        acct_value = float(state.get("marginSummary", {}).get("accountValue", 0))

        is_bot = avg_notional < 5_000 and span_hours < 1 and len(fills) > 50

        wins = sum(1 for f in closed if float(f.get("closedPnl", "0")) > 0)
        losses = sum(1 for f in closed if float(f.get("closedPnl", "0")) < 0)

        return {
            "traderType": "bot" if is_bot else "trader",
            "hasPositions": len(positions) > 0,
            "positionCount": len(positions),
            "fillCount": len(fills),
            "closedFillCount": len(closed),
            "avgNotional": round(avg_notional, 2),
            "spanHours": round(span_hours, 1),
            "liveAccountValue": round(acct_value, 2),
            "wins": wins,
            "losses": losses,
        }
    except Exception as e:
        logger.warning(f"Failed to classify {address}: {e}")
        return {"traderType": "unknown", "fillCount": 0}


@router.get("/leaderboard", tags=["Leaderboard"])
async def get_leaderboard(
    limit: int = 50,
    filter: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch Hyperliquid leaderboard data.

    Args:
        limit: Max number of results to return.
        filter: Set to "real" to filter out bots and keep only real traders.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(LEADERBOARD_URL)
        r.raise_for_status()
        rows = r.json().get("leaderboardRows", [])

    # When filtering, scan more rows to find enough real traders
    scan_limit = limit * 4 if filter == "real" else limit

    results = []
    for row in rows[:scan_limit]:
        perfs = {p[0]: p[1] for p in row["windowPerformances"]}
        alltime = perfs.get("allTime", {})
        day = perfs.get("day", {})
        week = perfs.get("week", {})
        month = perfs.get("month", {})
        results.append({
            "address": row["ethAddress"],
            "accountValue": float(row["accountValue"]),
            "pnl_alltime": float(alltime.get("pnl", 0)),
            "roi_alltime": float(alltime.get("roi", 0)) * 100,
            "vlm_alltime": float(alltime.get("vlm", 0)),
            "pnl_day": float(day.get("pnl", 0)),
            "pnl_week": float(week.get("pnl", 0)),
            "pnl_month": float(month.get("pnl", 0)),
        })

    if filter == "real":
        # Classify all traders concurrently
        async with httpx.AsyncClient(timeout=15) as client:
            # Process in batches of 10 to avoid overwhelming the API
            classified = []
            for i in range(0, len(results), 10):
                batch = results[i : i + 10]
                tasks = [
                    _classify_trader(client, r["address"]) for r in batch
                ]
                batch_results = await asyncio.gather(*tasks)
                for trader, info in zip(batch, batch_results):
                    if info:
                        trader["classification"] = info
                    classified.append((trader, info))

                    # Stop if we have enough real traders
                    real_count = sum(
                        1
                        for _, inf in classified
                        if inf and inf["traderType"] == "trader"
                    )
                    if real_count >= limit:
                        break
                if real_count >= limit:
                    break

            results = []
            for t, info in classified:
                if info and info["traderType"] == "trader":
                    t["winLoss"] = {
                        "wins": info.get("wins", 0),
                        "losses": info.get("losses", 0),
                        "total": info.get("wins", 0) + info.get("losses", 0),
                    }
                    results.append(t)
            results = results[:limit]
    else:
        # Still add a quick heuristic classification based on volume/PnL ratio
        for r in results:
            pnl = abs(r["pnl_alltime"]) if r["pnl_alltime"] != 0 else 1
            vlm_ratio = r["vlm_alltime"] / pnl
            # Very rough heuristic: bots have volume > 50,000x their PnL
            r["classification"] = {
                "traderType": "likely_bot" if vlm_ratio > 50_000 else "likely_trader",
            }
            r["winLoss"] = {"wins": 0, "losses": 0, "total": 0}

    return results


@router.get("/leaderboard/trader/{address}", tags=["Leaderboard"])
async def get_trader(address: str) -> dict[str, Any]:
    """Fetch trader positions and recent fills from Hyperliquid."""
    async with httpx.AsyncClient(timeout=15) as client:
        pos_r = await client.post(HL_INFO_URL, json={
            "type": "clearinghouseState", "user": address
        })
        fills_r = await client.post(HL_INFO_URL, json={
            "type": "userFills", "user": address
        })

    state = pos_r.json()
    fills = fills_r.json()

    # Determine which coins have open positions so we know what to search for.
    position_coins = set()
    for pos in state.get("assetPositions", []):
        position_coins.add(pos.get("position", {}).get("coin", ""))

    # Find the earliest "Open" fill per coin for the *current* position.
    # Walk newest-first: track opens until we hit a "Close" (which means the
    # current position was built after that close).
    open_dates: dict[str, int] = {}
    coins_resolved: set[str] = set()  # coins where we found a Close boundary
    for coin_name in position_coins:
        coin_fills = [f for f in fills if f.get("coin") == coin_name]
        earliest_open = None
        for f in coin_fills:
            direction = f.get("dir", "")
            if "Open" in direction or ">" in direction:
                earliest_open = f["time"]
            elif "Close" in direction:
                coins_resolved.add(coin_name)
                break
        if earliest_open is not None:
            open_dates[coin_name] = earliest_open
            if coin_name not in coins_resolved:
                coins_resolved.discard(coin_name)  # not yet bounded

    # For positions where we didn't find a "Close" boundary in recent fills,
    # the position was opened earlier than our fill window.  Mark with the
    # oldest fill timestamp as "opened before" indicator.
    oldest_fill_time: int | None = fills[-1]["time"] if fills else None
    coins_needing_history = position_coins - coins_resolved
    opened_before: dict[str, int] = {}  # coin -> oldest fill timestamp
    for coin_name in coins_needing_history:
        if oldest_fill_time:
            opened_before[coin_name] = oldest_fill_time

    import time as _time
    now_ms = int(_time.time() * 1000)

    positions = []
    for pos in state.get("assetPositions", []):
        p = pos.get("position", {})
        size = float(p.get("szi", 0))
        entry = float(p.get("entryPx", 0))
        coin = p.get("coin", "")
        opened_at = open_dates.get(coin)
        before_ts = opened_before.get(coin)
        # If we have an exact open date, use it. Otherwise estimate from
        # the oldest fill we found (the position was opened before that).
        effective_open = opened_at or before_ts
        duration_ms = (now_ms - effective_open) if effective_open else None
        positions.append({
            "coin": coin,
            "side": "LONG" if size > 0 else "SHORT",
            "size": abs(size),
            "entryPx": entry,
            "unrealizedPnl": float(p.get("unrealizedPnl", 0)),
            "returnOnEquity": float(p.get("returnOnEquity", 0)) * 100,
            "leverage": p.get("leverage", {}),
            "liquidationPx": p.get("liquidationPx", "N/A"),
            "marginUsed": float(p.get("marginUsed", 0)),
            "notional": abs(size) * entry,
            "openedAt": opened_at,
            "openedBefore": before_ts if not opened_at else None,
            "durationMs": duration_ms,
            "durationEstimated": opened_at is None and before_ts is not None,
        })

    closed_fills = [f for f in fills if float(f.get("closedPnl", "0")) != 0]
    wins = [f for f in closed_fills if float(f["closedPnl"]) > 0]
    losses = [f for f in closed_fills if float(f["closedPnl"]) < 0]
    win_pnl = sum(float(f["closedPnl"]) for f in wins)
    loss_pnl = sum(float(f["closedPnl"]) for f in losses)

    recent_fills = []
    for f in fills[:50]:
        recent_fills.append({
            "time": f.get("time", 0),
            "coin": f.get("coin", ""),
            "side": f.get("side", ""),
            "dir": f.get("dir", ""),
            "sz": f.get("sz", ""),
            "px": f.get("px", ""),
            "closedPnl": f.get("closedPnl", "0"),
            "fee": f.get("fee", "0"),
        })

    margin = state.get("marginSummary", {})
    return {
        "address": address,
        "accountValue": float(margin.get("accountValue", 0)),
        "totalMarginUsed": float(margin.get("totalMarginUsed", 0)),
        "positions": positions,
        "stats": {
            "totalTrades": len(closed_fills),
            "wins": len(wins),
            "losses": len(losses),
            "winRate": len(wins) / len(closed_fills) * 100 if closed_fills else 0,
            "winPnl": win_pnl,
            "lossPnl": loss_pnl,
            "netPnl": win_pnl + loss_pnl,
            "avgWin": win_pnl / len(wins) if wins else 0,
            "avgLoss": loss_pnl / len(losses) if losses else 0,
            "profitFactor": abs(win_pnl / loss_pnl) if loss_pnl else 0,
            "expectancy": (win_pnl + loss_pnl) / len(closed_fills) if closed_fills else 0,
        },
        "recentFills": recent_fills,
    }
