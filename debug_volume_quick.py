#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv
import numpy as np
from datetime import datetime

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.hyperliquid_client import HyperliquidClient

load_dotenv()

async def debug_volume_zscore():
    """Quick debug of volume z-score calculations"""
    
    # Initialize client
    client = HyperliquidClient(
        private_key=os.getenv('HYPERLIQUID_PRIVATE_KEY'),
        wallet_address=os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    )
    
    # Test symbols
    symbols = ['BTC', 'ETH', 'SOL']
    
    print(f"\n{'='*80}")
    print("Volume Data Analysis (Quick)")
    print(f"{'='*80}\n")
    
    all_markets = await client.get_all_asset_data()
    
    for symbol in symbols:
        if symbol in all_markets:
            market_data = all_markets[symbol]
            volume_24h = market_data['volume_24h']
            price = market_data['price']
            
            print(f"{symbol}:")
            print(f"  24h Volume: ${volume_24h:,.0f}")
            print(f"  Price: ${price:,.2f}")
            print()
    
    # Quick sample collection (10 samples)
    print(f"\n{'='*80}")
    print("Quick Z-Score Test (10 samples, 2 sec interval)")
    print(f"{'='*80}\n")
    
    symbol = 'BTC'
    volume_samples = []
    price_samples = []
    
    print(f"Collecting samples for {symbol}...")
    for i in range(10):
        all_markets = await client.get_all_asset_data()
        if symbol in all_markets:
            market_data = all_markets[symbol]
            volume = market_data['volume_24h']
            price = market_data['price']
            volume_samples.append(volume)
            price_samples.append(price)
            
            print(f"  Sample {i+1}: Volume=${volume:,.0f}")
        
        if i < 9:
            await asyncio.sleep(2)
    
    # Calculate statistics
    if len(volume_samples) >= 2:
        vol_mean = np.mean(volume_samples)
        vol_std = np.std(volume_samples)
        vol_min = min(volume_samples)
        vol_max = max(volume_samples)
        
        print(f"\nVolume Statistics:")
        print(f"  Mean: ${vol_mean:,.0f}")
        print(f"  Std Dev: ${vol_std:,.0f}")
        print(f"  Min: ${vol_min:,.0f}")
        print(f"  Max: ${vol_max:,.0f}")
        
        if vol_std > 0:
            # Calculate what z-score range we see
            z_min = (vol_min - vol_mean) / vol_std
            z_max = (vol_max - vol_mean) / vol_std
            print(f"  Z-score range: {z_min:.2f} to {z_max:.2f}")
            
            # Test spike scenarios
            print(f"\nHypothetical spikes:")
            for mult in [1.01, 1.05, 1.1, 1.2, 1.5, 2.0]:
                spike = vol_mean * mult
                z = (spike - vol_mean) / vol_std
                print(f"  {mult:.0%} increase: Z-score = {z:.2f}")
        else:
            print(f"  Std Dev is 0 - volume is constant")

if __name__ == "__main__":
    asyncio.run(debug_volume_zscore())