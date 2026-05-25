#!/usr/bin/env python3
"""Monitor Freqtrade trades and send notification when new trades open."""
import sqlite3
import os
import sys
import json
from datetime import datetime

DB_PATH = "/root/freqtrade/twin_pennies_mainnet.sqlite"
STATE_FILE = "/root/freqtrade/.trade_monitor_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_trade_count": 0, "notified": False}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def check_trades():
    if not os.path.exists(DB_PATH):
        return 0, []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if trades table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
    if not cursor.fetchone():
        conn.close()
        return 0, []
    
    # Get open trades count
    cursor.execute("SELECT COUNT(*) FROM trades WHERE is_open=1")
    open_count = cursor.fetchone()[0]
    
    # Get details of open trades
    cursor.execute("SELECT pair, is_short, open_date, stake_amount FROM trades WHERE is_open=1")
    trades = cursor.fetchall()
    
    conn.close()
    return open_count, trades

def main():
    state = load_state()
    open_count, trades = check_trades()
    
    # If we have trades and haven't notified yet
    if open_count > 0 and not state.get("notified"):
        trade_details = []
        for pair, is_short, open_date, stake in trades:
            side = "SHORT" if is_short else "LONG"
            trade_details.append(f"{pair} {side} (${stake:.2f})")
        
        message = f"🚨 TRADE ABERTA NO FREQTRADE!\n\n"
        message += f"Total: {open_count} trade(s) aberta(s)\n"
        message += f"\n".join(trade_details)
        message += f"\n\nBot: TwinPenniesStrategy (entry_z=1.2)"
        
        # Print to stdout for capture
        print(message)
        print("\n---NOTIFY---")
        
        # Update state
        state["notified"] = True
        state["last_trade_count"] = open_count
        state["notification_time"] = datetime.now().isoformat()
        save_state(state)
        
        return 1  # Signal that notification was sent
    
    # Reset notification if all trades closed
    if open_count == 0 and state.get("notified"):
        state["notified"] = False
        state["last_trade_count"] = 0
        save_state(state)
        print(f"No open trades. Monitor reset at {datetime.now()}")
    
    print(f"Monitor check: {open_count} trades open (last: {state.get('last_trade_count', 0)})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
