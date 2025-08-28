#!/usr/bin/env python3
"""
Check actual price precision by looking at order book
"""
from hyperliquid.info import Info
from hyperliquid.utils import constants

def main():
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    
    # Get order book for ARK
    symbols = ["ARK", "BTC", "ETH", "SOL"]
    
    for symbol in symbols:
        try:
            # Get L2 order book
            l2_book = info.l2_book(symbol)
            
            print(f"\n📊 {symbol} Order Book:")
            
            # Check first few bids and asks
            bids = l2_book.get("levels", [])[0][:5] if l2_book.get("levels") else []
            asks = l2_book.get("levels", [])[1][:5] if len(l2_book.get("levels", [])) > 1 else []
            
            print(f"  Top Bids:")
            for bid in bids[:3]:
                print(f"    ${float(bid.get('px', 0)):.8f} - Size: {bid.get('sz')}")
            
            print(f"  Top Asks:")
            for ask in asks[:3]:
                print(f"    ${float(ask.get('px', 0)):.8f} - Size: {ask.get('sz')}")
            
            # Analyze price differences to infer tick size
            if len(bids) > 1:
                price_diffs = []
                for i in range(len(bids)-1):
                    diff = abs(float(bids[i].get('px', 0)) - float(bids[i+1].get('px', 0)))
                    if diff > 0:
                        price_diffs.append(diff)
                
                if price_diffs:
                    min_diff = min(price_diffs)
                    print(f"  Minimum price difference observed: ${min_diff:.8f}")
                    print(f"  Likely tick size: ${min_diff:.8f}")
            
        except Exception as e:
            print(f"Error getting {symbol} order book: {e}")

if __name__ == "__main__":
    main()