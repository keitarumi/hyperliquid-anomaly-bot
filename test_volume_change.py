#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv
import numpy as np

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.hyperliquid_client import HyperliquidClient
from src.volume_anomaly_detector import VolumeAnomalyDetector

load_dotenv()

async def test_volume_change():
    """Test volume change rate based z-score"""
    
    # Initialize client
    client = HyperliquidClient(
        private_key=os.getenv('HYPERLIQUID_PRIVATE_KEY'),
        wallet_address=os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    )
    
    detector = VolumeAnomalyDetector(
        window_size=50,
        volume_z_threshold=1.5,
        price_z_threshold=1.5,
        detection_mode='vol_only',
        min_samples=10
    )
    
    print("Testing volume change rate Z-score calculation\n")
    print("="*80)
    
    # Test with BTC
    symbol = 'BTC'
    print(f"Collecting data for {symbol}...")
    
    for i in range(15):
        all_markets = await client.get_all_asset_data()
        if symbol in all_markets:
            market_data = all_markets[symbol]
            volume = market_data['volume_24h']
            price = market_data['price']
            
            # Detect anomaly
            is_anomaly, details = detector.detect_anomaly(symbol, price, volume)
            
            # Update history
            detector.update_data(symbol, price, volume)
            
            if i >= detector.min_samples:
                print(f"\nSample {i+1}:")
                print(f"  Volume: ${volume:,.0f}")
                print(f"  Volume Change: {details.get('volume_change_pct', 0):.4f}%")
                print(f"  Volume Z-score: {details.get('volume_z_score', 0):.2f}")
                print(f"  Is Anomaly: {is_anomaly}")
                
                if is_anomaly:
                    print(f"  >>> ANOMALY DETECTED! Type: {details.get('anomaly_type', 'unknown')}")
        
        await asyncio.sleep(3)
    
    print("\n" + "="*80)
    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(test_volume_change())