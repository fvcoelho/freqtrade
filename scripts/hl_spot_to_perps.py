"""Transfer USDC from Spot to Perps on Hyperliquid mainnet.

Usage: python scripts/hl_spot_to_perps.py <amount_usdc>
Reads the private key from config_v53.json (same wallet the bot uses).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/hl_spot_to_perps.py <amount_usdc>")
        return 2
    amount = float(sys.argv[1])

    cfg_path = Path(__file__).resolve().parent.parent / "config_v53.json"
    with open(cfg_path) as f:
        cfg = json.load(f)
    secret = cfg["exchange"]["secret"]
    address = cfg["exchange"]["key"]

    wallet = Account.from_key(secret)
    if wallet.address.lower() != address.lower():
        print(f"WARN: derived address {wallet.address} != config key {address}")

    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    spot_before = info.spot_user_state(address)
    perps_before = info.user_state(address)
    print("=== BEFORE ===")
    for b in spot_before["balances"]:
        if b["coin"] == "USDC":
            print(f"  Spot USDC: {b['total']}")
    print(f"  Perps accountValue: {perps_before['marginSummary']['accountValue']}")
    print(f"  Perps withdrawable: {perps_before['withdrawable']}")

    print(f"\n>>> Transferring {amount} USDC: Spot -> Perps")
    ex = Exchange(wallet, constants.MAINNET_API_URL)
    result = ex.usd_class_transfer(amount, to_perp=True)
    print(f"Result: {json.dumps(result, indent=2)}")

    if result.get("status") != "ok":
        print("ERROR: transfer did not return ok status")
        return 1

    import time
    time.sleep(3)
    spot_after = info.spot_user_state(address)
    perps_after = info.user_state(address)
    print("\n=== AFTER ===")
    for b in spot_after["balances"]:
        if b["coin"] == "USDC":
            print(f"  Spot USDC: {b['total']}")
    print(f"  Perps accountValue: {perps_after['marginSummary']['accountValue']}")
    print(f"  Perps withdrawable: {perps_after['withdrawable']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
