#!/usr/bin/env python3
import asyncio
import os
import json
from dotenv import load_dotenv
import aiohttp

load_dotenv()

async def check_fields():
    """Check field names in API response"""
    
    base_url = "https://api.hyperliquid.xyz"
    
    async with aiohttp.ClientSession() as session:
        # Get meta data
        print("Getting meta data...")
        response = await session.post(
            f"{base_url}/info",
            json={"type": "meta"}
        )
        meta_data = await response.json()
        
        # Check BTC data
        for universe in meta_data.get("universe", []):
            if universe.get("name") == "BTC":
                print("\nBTC meta data fields:")
                for key, value in universe.items():
                    print(f"  {key}: {value}")
                break
        
        # Get all mids (mark prices and volumes)
        print("\n\nGetting all mids data...")
        response = await session.post(
            f"{base_url}/info",
            json={"type": "allMids"}
        )
        all_mids = await response.json()
        
        # Check if BTC exists in mids
        if "BTC" in all_mids:
            print("\nBTC in allMids:")
            print(f"  {all_mids['BTC']}")
        
        # Get user states (includes volumes)
        print("\n\nGetting clearinghouse state...")
        response = await session.post(
            f"{base_url}/info",
            json={
                "type": "clearinghouseState",
                "user": os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
            }
        )
        ch_state = await response.json()
        
        # Check assetPositions
        if "assetPositions" in ch_state:
            positions = ch_state["assetPositions"]
            if positions:
                print(f"\nExample position fields:")
                for key, value in positions[0]["position"].items():
                    print(f"  {key}: {value}")
        
        # Get spot meta data (might have volume info)
        print("\n\nGetting spot meta data...")
        response = await session.post(
            f"{base_url}/info",
            json={"type": "spotMeta"}
        )
        spot_meta = await response.json()
        
        if spot_meta.get("tokens"):
            token = spot_meta["tokens"][0]
            print(f"\nExample spot token fields:")
            for key, value in token.items():
                print(f"  {key}: {value if len(str(value)) < 50 else str(value)[:50] + '...'}")
        
        # Get spot clearinghouse state for volume
        print("\n\nGetting spot clearinghouse state...")
        response = await session.post(
            f"{base_url}/info",
            json={
                "type": "spotClearinghouseState",
                "user": os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
            }
        )
        spot_state = await response.json()
        
        if "balances" in spot_state:
            print(f"\nSpot state has balances: {len(spot_state['balances'])} entries")

if __name__ == "__main__":
    asyncio.run(check_fields())