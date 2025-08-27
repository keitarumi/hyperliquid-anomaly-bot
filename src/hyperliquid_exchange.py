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
    
    def __init__(self, private_key: str, main_wallet_address: str = None):
        """
        Initialize the exchange client
        
        Args:
            private_key: Private key for API wallet (for signing)
            main_wallet_address: Main wallet address (where funds are)
        """
        # Ensure 0x prefix
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # Create account from private key (API wallet for signing)
        self.account = Account.from_key(private_key)
        self.api_wallet_address = self.account.address
        
        # Main wallet address (where funds are)
        self.main_wallet_address = main_wallet_address or self.api_wallet_address
        
        # Initialize exchange with account_address pointing to main wallet
        if main_wallet_address:
            self.exchange = Exchange(
                self.account,  # API wallet for signing
                base_url=constants.MAINNET_API_URL,
                account_address=main_wallet_address  # Main wallet with funds
            )
        else:
            self.exchange = Exchange(
                self.account,
                base_url=constants.MAINNET_API_URL
            )
        
        self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
        
        logger.info(f"Initialized HyperliquidExchange")
        logger.info(f"  API Wallet (signing): {self.api_wallet_address}")
        logger.info(f"  Main Wallet (funds): {self.main_wallet_address}")
    
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
        """Get the tick size for a symbol from metadata"""
        try:
            meta = self.info.meta()
            universe = meta.get("universe", [])
            
            for asset in universe:
                if asset.get("name") == symbol:
                    # Get szDecimals from metadata
                    sz_decimals = asset.get("szDecimals", 8)
                    # Return tick size based on decimals
                    return 10 ** (-sz_decimals)
            
            # Fallback to hardcoded values
            logger.warning(f"Symbol {symbol} not found in metadata, using fallback")
            tick_sizes = {
                "BTC": 1.0,
                "ETH": 0.1,
                "SOL": 0.01,
                "DOGE": 0.00001,
            }
            return tick_sizes.get(symbol, 0.01)
            
        except Exception as e:
            logger.error(f"Error getting tick size: {e}")
            return 0.01
    
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
        """Round price to match API price precision and tick size"""
        try:
            # Get tick size for the symbol
            tick = self.get_tick_size(symbol)
            
            # Special handling for ETH (0.1 tick size)
            if symbol == "ETH":
                # Round to nearest 0.1
                return round(price * 10) / 10
            
            # Round to nearest tick
            # Use round() to handle floating point precision issues
            num_ticks = round(price / tick)
            rounded = num_ticks * tick
            
            # Clean up floating point precision errors
            # Count decimal places in tick
            tick_str = str(tick)
            if '.' in tick_str and tick_str.split('.')[1].rstrip('0'):
                # Get decimal places from tick (excluding trailing zeros)
                decimals = len(tick_str.split('.')[1].rstrip('0'))
                return round(rounded, decimals)
            else:
                # Integer tick size
                return float(int(rounded))
            
        except Exception as e:
            logger.error(f"Error rounding price: {e}")
            # Safe fallback
            return round(price, 2)
    
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
            # Note: order parameters are (symbol, is_buy, size, price, order_type)
            result = self.exchange.order(
                symbol,
                is_buy,
                size,  # size comes BEFORE price
                price,
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
            # Query main wallet, not API wallet
            return self.info.user_state(self.main_wallet_address)
        except Exception as e:
            logger.error(f"Failed to get user state: {e}")
            return {}
    
    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all open positions"""
        try:
            user_state = self.get_user_state()
            positions = {}
            
            if 'assetPositions' in user_state:
                for position in user_state['assetPositions']:
                    pos_data = position.get('position', {})
                    symbol = position.get('position', {}).get('coin', '')
                    szi = float(pos_data.get('szi', 0))  # Signed size
                    
                    if szi != 0:  # Only return non-zero positions
                        positions[symbol] = {
                            'symbol': symbol,
                            'size': szi,  # Positive = long, negative = short
                            'entry_px': float(pos_data.get('entryPx', 0)),
                            'pnl': float(pos_data.get('unrealizedPnl', 0)),
                            'margin_used': float(pos_data.get('marginUsed', 0))
                        }
            
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {}
    
    async def place_market_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float = None,
        reduce_only: bool = True
    ) -> Dict[str, Any]:
        """
        Place a market order (mainly for closing positions)
        
        Args:
            symbol: Trading symbol
            is_buy: True for buy (close short), False for sell (close long)
            size: Order size (if None, close entire position)
            reduce_only: If True, only reduce position (default True for safety)
            
        Returns:
            Order result dictionary
        """
        try:
            # If no size specified, get current position size
            if size is None:
                positions = self.get_positions()
                if symbol in positions:
                    position_size = abs(positions[symbol]['size'])
                    size = position_size
                    logger.info(f"Closing entire {symbol} position: {size}")
                else:
                    logger.warning(f"No position found for {symbol}")
                    return {"status": "error", "message": f"No position found for {symbol}"}
            
            # Round size
            size = self.round_size(size, symbol)
            
            logger.info(f"Placing {symbol} market {'buy' if is_buy else 'sell'} order: size={size}")
            
            # Market order type
            order_type = {"limit": {"tif": "Ioc"}}  # IOC acts as market when price is far from market
            
            # Get current price for market-like execution
            # Use a price that guarantees execution
            meta = self.info.meta()
            current_prices = self.info.all_mids()
            
            # Find current price
            current_price = None
            for key, price in current_prices.items():
                if key == symbol:
                    current_price = float(price)
                    break
            
            if current_price is None:
                logger.error(f"Could not get current price for {symbol}")
                return {"status": "error", "message": "Could not get current price"}
            
            # Set aggressive price for guaranteed execution
            if is_buy:
                # For buy (closing short), use higher price
                market_price = current_price * 1.01
            else:
                # For sell (closing long), use lower price
                market_price = current_price * 0.99
            
            market_price = self.round_price(market_price, symbol)
            
            # Place order using official SDK
            result = self.exchange.order(
                symbol,
                is_buy,
                size,
                market_price,
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
                    elif "filled" in status:
                        logger.info(f"Market order filled immediately")
                        return {"status": "success", "filled": True, "response": result}
                    elif "resting" in status:
                        order_id = status["resting"].get("oid")
                        logger.info(f"Market order placed (may fill immediately): {order_id}")
                        return {"status": "success", "order_id": order_id, "response": result}
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return {"status": "error", "message": str(e)}