#!/usr/bin/env python3
"""
Check ARK full metadata for price decimals
"""
from hyperliquid.info import Info
from hyperliquid.utils import constants
import json

def main():
    # Initialize info client
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    
    # Get metadata
    meta = info.meta()
    universe = meta.get("universe", [])
    
    # Find ARK
    for i, asset in enumerate(universe):
        if asset.get("name") == "ARK":
            print(f"\n✅ ARK found at index {i}")
            print(f"\nFull ARK metadata:")
            print(json.dumps(asset, indent=2))
            
            print(f"\n📊 Key fields:")
            print(f"  name: {asset.get('name')}")
            print(f"  szDecimals: {asset.get('szDecimals')} (SIZE decimals, not price)")
            print(f"  maxLeverage: {asset.get('maxLeverage')}")
            print(f"  onlyIsolated: {asset.get('onlyIsolated', 'N/A')}")
            
            # Check for price-related fields
            for key in asset.keys():
                if 'price' in key.lower() or 'tick' in key.lower() or 'px' in key.lower():
                    print(f"  {key}: {asset.get(key)}")
            
            break
    
    # Also check asset contexts for price info
    print("\n\n📋 Checking asset contexts for ARK price info...")
    try:
        asset_contexts = info.asset_contexts()
        for context in asset_contexts:
            if context.get("coin") == "ARK":
                print("\nARK context found:")
                print(json.dumps(context, indent=2))
                break
    except Exception as e:
        print(f"Error getting asset contexts: {e}")
    
    # Check all mids for current price
    print("\n\n💰 Checking current ARK price...")
    try:
        all_mids = info.all_mids()
        if "ARK" in all_mids:
            print(f"Current ARK mid price: ${all_mids['ARK']}")
    except Exception as e:
        print(f"Error getting prices: {e}")

if __name__ == "__main__":
    main()