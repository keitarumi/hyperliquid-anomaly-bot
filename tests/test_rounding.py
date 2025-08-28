#!/usr/bin/env python3
"""
Test new rounding logic for ARK and other symbols
"""
import asyncio
import logging
from src.hyperliquid_exchange import HyperliquidExchange
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)

async def main():
    load_dotenv()
    
    # Initialize exchange
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    main_wallet = os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    
    exchange = HyperliquidExchange(private_key, main_wallet)
    
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
        meta = exchange.info.meta()
        universe = meta.get("universe", [])
        for asset in universe:
            if asset.get("name") == symbol:
                print(f"  Metadata: szDecimals={asset.get('szDecimals')}")
                break
        
        # Get current price for reference
        all_mids = exchange.info.all_mids()
        if symbol in all_mids:
            print(f"  Current API price: ${all_mids[symbol]}")
        
        # Test price rounding
        rounded_price = exchange.round_price(test_price, symbol)
        print(f"  Price: ${test_price:.6f} -> ${rounded_price}")
        
        # Test size rounding
        rounded_size = exchange.round_size(test_size, symbol)
        print(f"  Size: {test_size:.8f} -> {rounded_size}")

if __name__ == "__main__":
    asyncio.run(main())