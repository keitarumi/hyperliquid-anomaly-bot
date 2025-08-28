import asyncio
from src.hyperliquid_client import HyperliquidClient
import os
from dotenv import load_dotenv

async def check_price_precision():
    load_dotenv()
    client = HyperliquidClient(
        os.getenv('HYPERLIQUID_PRIVATE_KEY'),
        os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
    )
    
    # Get current prices
    data = await client.get_all_asset_data()
    
    symbols = ['BTC', 'ETH', 'SOL', 'DOGE', 'ARB', 'WIF', 'PEPE', 'SUI', 'MATIC']
    
    print('Current prices and their precision:')
    for symbol in symbols:
        if symbol in data:
            price = data[symbol].get('price', 0)
            price_str = str(price)
            
            # Count decimal places
            if '.' in price_str:
                decimals = len(price_str.split('.')[1].rstrip('0'))
            else:
                decimals = 0
                
            print(f'{symbol:6s}: ${price:12.8f} (decimals: {decimals})')

if __name__ == "__main__":
    asyncio.run(check_price_precision())