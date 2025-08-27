"""
Hyperliquid Exchange Client using official SDK for order operations
"""
import logging
from typing import Dict, Any, Optional
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

logger = logging.getLogger(__name__)


class HyperliquidExchange:
    """
    Exchange client for Hyperliquid using the official SDK
    Used for authenticated operations like placing and cancelling orders
    """
    
    def __init__(self, private_key: str):
        """
        Initialize the exchange client
        
        Args:
            private_key: Private key for the wallet (with or without 0x prefix)
        """
        # Ensure 0x prefix
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # Create account from private key
        self.account = Account.from_key(private_key)
        self.wallet_address = self.account.address
        
        # Initialize exchange and info clients
        self.exchange = Exchange(self.account, constants.MAINNET_API_URL)
        self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
        
        logger.info(f"Initialized HyperliquidExchange for wallet: {self.wallet_address}")
    
    def get_asset_id(self, symbol: str) -> int:
        """Get asset ID from symbol"""
        # Get universe metadata
        meta = self.info.meta()
        universe = meta.get("universe", [])
        
        for i, asset in enumerate(universe):
            if asset.get("name") == symbol:
                return i
        
        logger.warning(f"Symbol {symbol} not found in universe, defaulting to 0")
        return 0
    
    def get_tick_size(self, symbol: str) -> float:
        """Get the tick size for a symbol"""
        # Common tick sizes (this should be fetched from API ideally)
        tick_sizes = {
            "BTC": 1.0,      # $1
            "ETH": 0.1,      # $0.1
            "DOGE": 0.0001,  # $0.0001
            "SOL": 0.01,     # $0.01
        }
        return tick_sizes.get(symbol, 0.01)
    
    def get_min_size(self, symbol: str) -> float:
        """Get minimum order size for a symbol"""
        # These are approximate minimums
        # In production, should fetch from API
        min_sizes = {
            "BTC": 0.0001,
            "ETH": 0.001,
            "DOGE": 100,  # DOGE requires larger sizes
            "SOL": 0.1,
        }
        return min_sizes.get(symbol, 1)
    
    def round_price(self, price: float, symbol: str) -> float:
        """Round price to valid tick size"""
        tick = self.get_tick_size(symbol)
        return round(price / tick) * tick
    
    def round_size(self, size: float, symbol: str) -> float:
        """Round size to valid decimals"""
        # Get szDecimals from metadata
        meta = self.info.meta()
        universe = meta.get("universe", [])
        
        for asset in universe:
            if asset.get("name") == symbol:
                sz_decimals = asset.get("szDecimals", 4)
                if sz_decimals == 0:
                    return round(size)  # No decimals
                else:
                    return round(size, sz_decimals)
        
        return round(size, 4)  # Default to 4 decimals
    
    async def place_limit_order(
        self,
        symbol: str,
        is_buy: bool,
        price: float,
        size: float,
        reduce_only: bool = False,
        post_only: bool = True
    ) -> Dict[str, Any]:
        """
        Place a limit order
        
        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")
            is_buy: True for buy, False for sell
            price: Limit price
            size: Order size
            reduce_only: If True, only reduce position
            post_only: If True, use post-only order
            
        Returns:
            Order result dictionary
        """
        try:
            # Round price and size
            price = self.round_price(price, symbol)
            size = self.round_size(size, symbol)
            
            # Check minimum size
            min_size = self.get_min_size(symbol)
            if size < min_size:
                logger.warning(f"Size {size} below minimum {min_size} for {symbol}")
                size = min_size
            
            logger.info(f"Placing {symbol} {'buy' if is_buy else 'sell'} order: "
                       f"price=${price:.2f}, size={size}")
            
            # Prepare order type
            if post_only:
                order_type = {"limit": {"tif": "Alo"}}  # Add liquidity only
            else:
                order_type = {"limit": {"tif": "Ioc"}}  # Immediate or cancel
            
            # Place order using official SDK
            result = self.exchange.order(
                symbol,
                is_buy,
                price,
                size,
                order_type,
                reduce_only=reduce_only
            )
            
            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses:
                    status = statuses[0]
                    if "error" in status:
                        logger.error(f"Order error: {status['error']}")
                        return {"status": "error", "message": status["error"]}
                    elif "resting" in status:
                        order_id = status["resting"].get("oid")
                        logger.info(f"Order placed successfully! ID: {order_id}")
                        return {"status": "success", "order_id": order_id, "response": result}
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancel result dictionary
        """
        try:
            logger.info(f"Cancelling {symbol} order: {order_id}")
            
            result = self.exchange.cancel(symbol, order_id)
            
            if result.get("status") == "ok":
                logger.info(f"Order {order_id} cancelled successfully")
                return {"status": "success", "response": result}
            else:
                logger.error(f"Failed to cancel order: {result}")
                return result
                
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_user_state(self) -> Dict[str, Any]:
        """Get user account state"""
        try:
            return self.info.user_state(self.wallet_address)
        except Exception as e:
            logger.error(f"Failed to get user state: {e}")
            return {}