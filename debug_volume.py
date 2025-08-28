#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv
import numpy as np
from collections import deque
from datetime import datetime

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.hyperliquid_client import HyperliquidClient
from src.volume_anomaly_detector import VolumeAnomalyDetector

load_dotenv()

async def debug_volume_zscore():
    """Debug volume z-score calculations"""
    
    # Initialize client
    client = HyperliquidClient(
        private_key=os.getenv('HYPERLIQUID_PRIVATE_KEY'),
        wallet_address=os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    )
    
    # Test symbols
    symbols = ['BTC', 'ETH', 'SOL', 'DOGE', 'PEPE']
    
    # Collect volume data
    print(f"\n{'='*80}")
    print("Volume Data Analysis")
    print(f"{'='*80}\n")
    
    all_markets = await client.get_all_asset_data()
    
    for symbol in symbols:
        try:
            if symbol in all_markets:
                market_data = all_markets[symbol]
                volume_24h = market_data['volume_24h']
                price = market_data['price']
                
                print(f"{symbol}:")
                print(f"  24h Volume: ${volume_24h:,.0f}")
                print(f"  Price: ${price:,.2f}")
                print()
        except Exception as e:
            print(f"{symbol}: Error - {e}")
    
    # Simulate historical collection
    print(f"\n{'='*80}")
    print("Z-Score Simulation (50 samples)")
    print(f"{'='*80}\n")
    
    detector = VolumeAnomalyDetector(
        window_size=50,
        volume_z_threshold=1.5,
        price_z_threshold=1.5,
        detection_mode='vol_only'
    )
    
    # Collect 50 samples for BTC
    symbol = 'BTC'
    volume_samples = []
    price_samples = []
    
    print(f"Collecting 50 samples for {symbol} (5 seconds interval)...")
    for i in range(50):
        try:
            all_markets = await client.get_all_asset_data()
            if symbol in all_markets:
                market_data = all_markets[symbol]
                volume = market_data['volume_24h']
                price = market_data['price']
                volume_samples.append(volume)
                price_samples.append(price)
                
                if (i + 1) % 10 == 0:
                    print(f"  Sample {i+1}: Volume=${volume:,.0f}, Price=${price:,.2f}")
            
            if i < 49:  # Don't wait after last sample
                await asyncio.sleep(5)
        except Exception as e:
            print(f"  Error collecting sample {i+1}: {e}")
    
    # Calculate statistics
    print(f"\n{'='*80}")
    print("Statistical Analysis")
    print(f"{'='*80}\n")
    
    if len(volume_samples) >= 10:
        # Volume stats
        vol_mean = np.mean(volume_samples)
        vol_std = np.std(volume_samples)
        vol_min = min(volume_samples)
        vol_max = max(volume_samples)
        
        print(f"Volume Statistics:")
        print(f"  Mean: ${vol_mean:,.0f}")
        print(f"  Std Dev: ${vol_std:,.0f}")
        print(f"  Min: ${vol_min:,.0f}")
        print(f"  Max: ${vol_max:,.0f}")
        print(f"  Range: ${vol_max - vol_min:,.0f}")
        print(f"  Coefficient of Variation: {(vol_std/vol_mean)*100:.2f}%")
        
        # Price stats
        price_mean = np.mean(price_samples)
        price_std = np.std(price_samples)
        price_min = min(price_samples)
        price_max = max(price_samples)
        
        print(f"\nPrice Statistics:")
        print(f"  Mean: ${price_mean:,.2f}")
        print(f"  Std Dev: ${price_std:,.2f}")
        print(f"  Min: ${price_min:,.2f}")
        print(f"  Max: ${price_max:,.2f}")
        print(f"  Range: ${price_max - price_min:,.2f}")
        print(f"  Coefficient of Variation: {(price_std/price_mean)*100:.2f}%")
        
        # Calculate Z-scores for extreme values
        print(f"\nZ-Score Analysis:")
        
        # Volume Z-scores
        if vol_std > 0:
            vol_z_min = (vol_min - vol_mean) / vol_std
            vol_z_max = (vol_max - vol_mean) / vol_std
            print(f"  Volume Z-score range: {vol_z_min:.2f} to {vol_z_max:.2f}")
        else:
            print(f"  Volume Z-score: N/A (std=0)")
        
        # Price Z-scores
        if price_std > 0:
            price_z_min = (price_min - price_mean) / price_std
            price_z_max = (price_max - price_mean) / price_std
            print(f"  Price Z-score range: {price_z_min:.2f} to {price_z_max:.2f}")
        else:
            print(f"  Price Z-score: N/A (std=0)")
        
        # Test with a hypothetical spike
        print(f"\n{'='*80}")
        print("Hypothetical Spike Test")
        print(f"{'='*80}\n")
        
        # Test different volume multipliers
        multipliers = [1.1, 1.2, 1.5, 2.0, 3.0, 5.0, 10.0]
        
        print("Volume spike Z-scores:")
        for mult in multipliers:
            spike_volume = vol_mean * mult
            if vol_std > 0:
                z_score = (spike_volume - vol_mean) / vol_std
                print(f"  {mult:.1f}x mean: Z-score = {z_score:.2f}")
            else:
                print(f"  {mult:.1f}x mean: Z-score = N/A (std=0)")
    
    # No need to close as we don't have persistent connection

if __name__ == "__main__":
    asyncio.run(debug_volume_zscore())