#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def check_tick_size():
    """Check tick size requirements for Hyperliquid"""
    
    base_url = "https://api.hyperliquid.xyz"
    
    async with aiohttp.ClientSession() as session:
        # Get meta data
        response = await session.post(
            f"{base_url}/info",
            json={"type": "meta"}
        )
        meta_data = await response.json()
        
        print("Checking tick size for various symbols...\n")
        print(f"{'Symbol':<10} {'szDecimals':<12} {'Max Leverage':<15}")
        print("-" * 40)
        
        # Check some common symbols
        symbols_to_check = ['BTC', 'ETH', 'SOL', 'DOGE', 'PEPE', 'ARK', 'WIF']
        
        for universe in meta_data.get("universe", []):
            symbol = universe.get("name")
            if symbol in symbols_to_check:
                sz_decimals = universe.get("szDecimals", "N/A")
                max_leverage = universe.get("maxLeverage", "N/A")
                print(f"{symbol:<10} {sz_decimals:<12} {max_leverage:<15}")
        
        print("\n" + "="*60)
        print("\nGetting order book to check actual price tick sizes...")
        
        # Get L2 book for BTC to see price increments
        response = await session.post(
            f"{base_url}/info",
            json={
                "type": "l2Book",
                "coin": "BTC"
            }
        )
        book_data = await response.json()
        
        if book_data and "levels" in book_data:
            bids = book_data["levels"][0][:5]  # First 5 bids
            asks = book_data["levels"][1][:5]  # First 5 asks
            
            print("\nBTC Order Book (top 5 levels):")
            print("\nAsks:")
            for ask in asks:
                print(f"  Price: ${float(ask['px']):,.2f}, Size: {float(ask['sz']):.5f}")
            
            print("\nBids:")
            for bid in bids:
                print(f"  Price: ${float(bid['px']):,.2f}, Size: {float(bid['sz']):.5f}")
            
            # Calculate tick size from price differences
            if len(asks) >= 2:
                price_diff = float(asks[1]['px']) - float(asks[0]['px'])
                print(f"\nObserved price difference between asks: ${price_diff:.2f}")
        
        # Check exchange info for proper tick sizes
        print("\n" + "="*60)
        print("\nChecking exchange info endpoint...")
        
        response = await session.post(
            f"{base_url}/info",
            json={"type": "exchangeInfo"}
        )
        exchange_info = await response.json()
        print(f"Exchange info response: {json.dumps(exchange_info, indent=2)[:500]}...")

if __name__ == "__main__":
    asyncio.run(check_tick_size())