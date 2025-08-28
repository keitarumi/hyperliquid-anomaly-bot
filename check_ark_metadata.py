#!/usr/bin/env python3
"""
Check ARK metadata and price rounding issue
"""
from hyperliquid.info import Info
from hyperliquid.utils import constants

def main():
    # Initialize info client
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    
    # Get metadata
    meta = info.meta()
    universe = meta.get("universe", [])
    
    # Find ARK
    ark_found = False
    for i, asset in enumerate(universe):
        if asset.get("name") == "ARK":
            ark_found = True
            print(f"\n✅ ARK found in universe at index {i}")
            print(f"ARK metadata: {asset}")
            
            sz_decimals = asset.get("szDecimals", 8)
            tick_size = 10 ** (-sz_decimals)
            
            print(f"\nARK Trading Parameters:")
            print(f"  szDecimals: {sz_decimals}")
            print(f"  tick_size: {tick_size}")
            print(f"  maxLeverage: {asset.get('maxLeverage', 'N/A')}")
            print(f"  onlyIsolated: {asset.get('onlyIsolated', 'N/A')}")
            
            # Test price rounding
            test_prices = [0.4599, 0.5519, 0.9999, 1.0, 1.5]
            print(f"\nPrice Rounding Tests (tick_size={tick_size}):")
            for price in test_prices:
                num_ticks = round(price / tick_size)
                rounded = num_ticks * tick_size
                print(f"  ${price:.4f} -> {num_ticks} ticks -> ${rounded:.4f}")
            
            break
    
    if not ark_found:
        print("❌ ARK not found in universe")
        print("\nSearching for similar symbols...")
        for asset in universe:
            name = asset.get("name", "")
            if "ARK" in name.upper():
                print(f"  Found: {name}")

if __name__ == "__main__":
    main()