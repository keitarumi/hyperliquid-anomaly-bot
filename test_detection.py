#!/usr/bin/env python3
"""
Test anomaly detection logic
"""
import asyncio
import logging
from src.hyperliquid_client import HyperliquidClient
from src.volume_anomaly_detector import VolumeAnomalyDetector
import os
from dotenv import load_dotenv
import time

logging.basicConfig(level=logging.DEBUG)

async def main():
    load_dotenv()
    
    # Initialize client
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    main_wallet = os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    
    client = HyperliquidClient(private_key, main_wallet)
    
    # Initialize detector with z_score_threshold=0
    detector = VolumeAnomalyDetector(
        window_size=60,
        z_score_threshold=0,  # Detect ANY change
        min_samples=10,
        min_volume_usd=0  # No minimum volume
    )
    
    print("\n" + "="*60)
    print("TESTING ANOMALY DETECTION (Z-score threshold = 0)")
    print("="*60)
    
    # Collect data for a few iterations to build history
    print("\nBuilding history (need 10 samples)...")
    
    for i in range(12):  # Collect 12 samples
        print(f"\nIteration {i+1}/12:")
        
        asset_data = await client.get_all_asset_data()
        
        # Focus on BTC for testing
        if "BTC" in asset_data:
            btc_data = asset_data["BTC"]
            print(f"  BTC Price: ${btc_data['price']:,.2f}")
            print(f"  BTC Volume: ${btc_data['volume_24h']:,.2f}")
            
            # Check for anomaly
            is_anomaly, details = detector.detect_anomaly(
                "BTC", 
                btc_data['price'], 
                btc_data['volume_24h']
            )
            
            print(f"  History samples: {details.get('samples', 0)}")
            print(f"  Volume mean: ${details.get('volume_mean', 0):,.2f}")
            print(f"  Volume std: ${details.get('volume_std', 0):,.2f}")
            print(f"  Z-score: {details.get('volume_z_score', 0):.6f}")
            print(f"  Is anomaly? {is_anomaly}")
            
            if is_anomaly:
                print(f"  🔴 ANOMALY DETECTED! Type: {details.get('anomaly_type')}")
            
            # Update history
            detector.update_data("BTC", btc_data['price'], btc_data['volume_24h'])
        
        if i < 11:
            await asyncio.sleep(2)  # Wait 2 seconds between iterations
    
    # Test with all symbols
    print("\n" + "="*60)
    print("SCANNING ALL SYMBOLS")
    print("="*60)
    
    asset_data = await client.get_all_asset_data()
    anomalies = detector.scan_all_assets(asset_data)
    
    print(f"\nTotal anomalies detected: {len(anomalies)}")
    if anomalies:
        print("\nFirst 5 anomalies:")
        for i, anomaly in enumerate(anomalies[:5]):
            print(f"\n{i+1}. {anomaly['symbol']}:")
            print(f"   Type: {anomaly['anomaly_type']}")
            print(f"   Z-score: {anomaly['volume_z_score']:.4f}")
            print(f"   Volume change: {anomaly['volume_change_pct']:.2f}%")

if __name__ == "__main__":
    asyncio.run(main())