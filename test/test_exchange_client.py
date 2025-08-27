import asyncio
import logging
import os
from dotenv import load_dotenv
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid_exchange import HyperliquidExchange

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_exchange_client():
    """Test the HyperliquidExchange client"""
    
    load_dotenv()
    
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    if not private_key:
        logger.error("Missing HYPERLIQUID_PRIVATE_KEY")
        return False
    
    try:
        # Initialize exchange client
        exchange = HyperliquidExchange(private_key)
        
        # Get user state to check balance
        user_state = exchange.get_user_state()
        if 'marginSummary' in user_state:
            margin = user_state['marginSummary']
            logger.info(f"Account value: ${margin.get('accountValue', 0)}")
        
        # Get current BTC price
        all_mids = exchange.info.all_mids()
        btc_price = float(all_mids.get("BTC", 100000))
        logger.info(f"Current BTC price: ${btc_price:.2f}")
        
        # Place a safe test order
        symbol = "BTC"
        order_price = btc_price - 500  # $500 below market
        order_size = 0.0001  # Minimum size
        
        logger.info(f"\n📊 Placing test order:")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Price: ${order_price:.2f} (${btc_price - order_price:.2f} below market)")
        logger.info(f"   Size: {order_size} {symbol}")
        
        # Place the order
        result = await exchange.place_limit_order(
            symbol=symbol,
            is_buy=True,
            price=order_price,
            size=order_size,
            post_only=True
        )
        
        logger.info(f"\nOrder result: {result}")
        
        if result.get("status") == "success":
            logger.info("✅ Order placed successfully!")
            order_id = result.get("order_id")
            
            if order_id:
                # Wait 5 seconds then cancel
                logger.info("\nWaiting 5 seconds before cancelling...")
                await asyncio.sleep(5)
                
                cancel_result = await exchange.cancel_order(symbol, order_id)
                logger.info(f"Cancel result: {cancel_result}")
                
                if cancel_result.get("status") == "success":
                    logger.info("✅ Order cancelled successfully!")
                    return True
        elif result.get("status") == "error":
            logger.error(f"❌ Order failed: {result.get('message')}")
        
        return False
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def main():
    logger.info("=" * 60)
    logger.info("Testing HyperliquidExchange Client")
    logger.info("=" * 60)
    
    success = await test_exchange_client()
    
    if success:
        logger.info("\n✅ SUCCESS: Exchange client works correctly!")
        logger.info("Orders can be placed and cancelled successfully.")
    else:
        logger.info("\n❌ Test failed - check error messages above")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())