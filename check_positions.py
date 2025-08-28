#!/usr/bin/env python3
"""Check current positions"""
from src.hyperliquid_exchange import HyperliquidExchange
import os
from dotenv import load_dotenv
import json

load_dotenv()

private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
main_wallet = os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')

exchange = HyperliquidExchange(private_key, main_wallet)

# Get raw user state
user_state = exchange.get_user_state()
print("\n=== Raw User State ===")
print(json.dumps(user_state, indent=2)[:1000])  # First 1000 chars

# Get positions
positions = exchange.get_positions()

print(f"\n=== Positions ===")
if positions:
    print(f"ポジション数: {len(positions)}")
    for symbol, pos in positions.items():
        print(f"\n銘柄: {symbol}")
        print(f"  詳細: {pos}")
else:
    print("ポジションなし")

# Check length directly
print(f"\nlen(positions) = {len(positions)}")