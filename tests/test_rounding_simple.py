#!/usr/bin/env python3
"""
Simple test of rounding logic without authentication
"""
from hyperliquid.info import Info
from hyperliquid.utils import constants
import math

def get_price_decimals(symbol: str, info) -> int:
    """Get price decimals by observing current market price"""
    try:
        all_mids = info.all_mids()
        if symbol in all_mids:
            price_str = str(all_mids[symbol])
            if '.' in price_str:
                decimal_part = price_str.split('.')[1].rstrip('0')
                decimals = len(decimal_part) if decimal_part else 2
                return decimals
            else:
                return 0
        return 4  # Default
    except:
        return 4

def round_price(price: float, symbol: str, info) -> float:
    """Round price to match observed API price precision"""
    decimals = get_price_decimals(symbol, info)
    rounded = round(price, decimals)
    return rounded

def round_size_down(size: float, sz_decimals: int) -> float:
    """Round size DOWN to valid decimals (truncate)"""
    if sz_decimals == 0:
        return float(int(size))
    else:
        multiplier = 10 ** sz_decimals
        return int(size * multiplier) / multiplier

def main():
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    
    # Get metadata
    meta = info.meta()
    universe = meta.get("universe", [])
    
    # Test cases
    test_cases = [
        ("ARK", 0.5519, 181.198811),
        ("BTC", 111320.123456, 0.000897),
        ("ETH", 4614.567, 0.021662),
        ("SOL", 205.123456, 0.487460),
    ]
    
    print("\n" + "="*60)
    print("PRICE AND SIZE ROUNDING TESTS")
    print("="*60)
    
    for symbol, test_price, test_size in test_cases:
        print(f"\n📊 {symbol}:")
        
        # Get metadata
        sz_decimals = None
        for asset in universe:
            if asset.get("name") == symbol:
                sz_decimals = asset.get("szDecimals", 4)
                print(f"  Metadata: szDecimals={sz_decimals}")
                break
        
        if sz_decimals is None:
            print(f"  ⚠️  {symbol} not found in metadata")
            continue
        
        # Get current price for reference
        all_mids = info.all_mids()
        if symbol in all_mids:
            current_price = all_mids[symbol]
            print(f"  Current API price: ${current_price}")
            price_str = str(current_price)
            if '.' in price_str:
                observed_decimals = len(price_str.split('.')[1].rstrip('0'))
            else:
                observed_decimals = 0
            print(f"  Observed price decimals: {observed_decimals}")
        
        # Test price rounding
        rounded_price = round_price(test_price, symbol, info)
        price_decimals = get_price_decimals(symbol, info)
        print(f"  Price: ${test_price:.6f} -> ${rounded_price} (using {price_decimals} decimals)")
        
        # Test size rounding
        rounded_size = round_size_down(test_size, sz_decimals)
        print(f"  Size: {test_size:.8f} -> {rounded_size} (truncated to {sz_decimals} decimals)")

if __name__ == "__main__":
    main()