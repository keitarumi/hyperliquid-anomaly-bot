#!/usr/bin/env python3
"""
Test data fetching to verify volume and price are being retrieved correctly
"""
import asyncio
import logging
from src.hyperliquid_client import HyperliquidClient
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

async def main():
    load_dotenv()
    
    # Initialize client
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    main_wallet = os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    
    client = HyperliquidClient(private_key, main_wallet)
    
    print("\n" + "="*60)
    print("TESTING DATA FETCH")
    print("="*60)
    
    # Fetch all asset data
    asset_data = await client.get_all_asset_data()
    
    print(f"\nTotal symbols fetched: {len(asset_data)}")
    
    # Show first 10 symbols with data
    print("\nFirst 10 symbols with their data:")
    print("-" * 60)
    
    for i, (symbol, data) in enumerate(list(asset_data.items())[:10]):
        print(f"\n{i+1}. {symbol}:")
        print(f"   Price: ${data.get('price', 0):.6f}")
        print(f"   Volume 24h: ${data.get('volume_24h', 0):,.2f}")
        print(f"   Volume 24h Base: {data.get('volume_24h_base', 0):,.6f}")
        print(f"   Open Interest: ${data.get('open_interest', 0):,.2f}")
    
    # Check for symbols with zero volume
    zero_volume = [s for s, d in asset_data.items() if d.get('volume_24h', 0) == 0]
    print(f"\n\nSymbols with zero volume: {len(zero_volume)}")
    if zero_volume[:5]:
        print(f"Examples: {zero_volume[:5]}")
    
    # Check for symbols with non-zero volume
    non_zero_volume = [s for s, d in asset_data.items() if d.get('volume_24h', 0) > 0]
    print(f"\nSymbols with non-zero volume: {len(non_zero_volume)}")
    
    # Show symbols with highest volume
    sorted_by_volume = sorted(asset_data.items(), key=lambda x: x[1].get('volume_24h', 0), reverse=True)
    print("\nTop 5 symbols by volume:")
    for symbol, data in sorted_by_volume[:5]:
        print(f"   {symbol}: ${data.get('volume_24h', 0):,.2f}")

if __name__ == "__main__":
    asyncio.run(main())