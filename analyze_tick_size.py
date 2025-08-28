#!/usr/bin/env python3
import asyncio
import aiohttp
import math
from decimal import Decimal

async def analyze_tick_size():
    """Analyze tick size for different symbols"""
    
    base_url = "https://api.hyperliquid.xyz"
    
    async with aiohttp.ClientSession() as session:
        symbols = ['BTC', 'ETH', 'SOL', 'DOGE', 'ARK', 'PEPE', 'WIF']
        
        print(f"{'Symbol':<8} {'Sample Price':<15} {'Tick Size':<15} {'Suggested Rounding'}")
        print("-" * 65)
        
        for symbol in symbols:
            try:
                # Get order book
                response = await session.post(
                    f"{base_url}/info",
                    json={
                        "type": "l2Book", 
                        "coin": symbol
                    }
                )
                book_data = await response.json()
                
                if book_data and "levels" in book_data:
                    asks = book_data["levels"][1][:10]  # First 10 asks
                    
                    if len(asks) >= 2:
                        # Get multiple price samples
                        prices = [float(ask['px']) for ask in asks]
                        
                        # Calculate tick size from price differences
                        tick_sizes = []
                        for i in range(1, len(prices)):
                            diff = prices[i] - prices[i-1]
                            if diff > 0:
                                tick_sizes.append(diff)
                        
                        if tick_sizes:
                            # Find the minimum non-zero difference (tick size)
                            tick_size = min(tick_sizes)
                            
                            # Determine decimal places needed
                            tick_str = f"{tick_size:.10f}".rstrip('0')
                            if '.' in tick_str:
                                decimals = len(tick_str.split('.')[1])
                            else:
                                decimals = 0
                            
                            print(f"{symbol:<8} ${prices[0]:<14,.2f} ${tick_size:<14.6f} Round to {decimals} decimals")
                            
                            # Additional check: what's the tick size pattern?
                            if tick_size >= 1:
                                print(f"         -> Round to nearest {int(tick_size)}")
                            elif tick_size >= 0.1:
                                print(f"         -> Round to nearest {tick_size:.1f}")
                            elif tick_size >= 0.01:
                                print(f"         -> Round to nearest {tick_size:.2f}")
                            else:
                                print(f"         -> Round to nearest {tick_size:.6f}")
                        else:
                            print(f"{symbol:<8} No price differences found")
                    else:
                        print(f"{symbol:<8} Not enough order book levels")
                else:
                    print(f"{symbol:<8} No order book data")
                    
            except Exception as e:
                print(f"{symbol:<8} Error: {e}")
            
            await asyncio.sleep(0.5)  # Rate limiting

if __name__ == "__main__":
    asyncio.run(analyze_tick_size())