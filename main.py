#!/usr/bin/env python3
"""
Hyperliquid Anomaly Detection Trading Bot
Main entry point
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from datetime import datetime
import signal

from src.hyperliquid_client import HyperliquidClient
from src.hyperliquid_exchange import HyperliquidExchange
from src.volume_anomaly_detector import VolumeAnomalyDetector
from src.discord_notifier import DiscordNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'trading_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AnomalyTradingBot:
    """Main trading bot class"""
    
    def __init__(self):
        """Initialize the trading bot"""
        load_dotenv()
        
        # Load configuration
        self.private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
        self.main_wallet = os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        
        # Trading parameters
        self.monitoring_interval = int(os.getenv('MONITORING_INTERVAL', 10))
        self.order_timeout = int(os.getenv('ORDER_TIMEOUT', 600))  # Cancel unfilled orders after this time
        self.position_close_timeout = int(os.getenv('POSITION_CLOSE_TIMEOUT', 1800))  # Close positions after 30 minutes
        
        # Parse multiple price multipliers and order amounts
        price_multipliers_str = os.getenv('PRICE_MULTIPLIERS', '3.0')
        order_amounts_str = os.getenv('ORDER_AMOUNTS_USDC', '100')
        
        self.price_multipliers = [float(x.strip()) for x in price_multipliers_str.split(',')]
        self.order_amounts_usdc = [float(x.strip()) for x in order_amounts_str.split(',')]
        
        # Validate that multipliers and amounts have the same count
        if len(self.price_multipliers) != len(self.order_amounts_usdc):
            error_msg = (
                f"Configuration error: Price multipliers count ({len(self.price_multipliers)}) "
                f"does not match order amounts count ({len(self.order_amounts_usdc)}). "
                f"Multipliers: {self.price_multipliers}, Amounts: {self.order_amounts_usdc}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.max_concurrent_orders = int(os.getenv('MAX_CONCURRENT_ORDERS', 1))  # Max orders at once
        
        # Detection parameters
        self.detector_window_size = int(os.getenv('DETECTOR_WINDOW_SIZE', 60))
        self.volume_z_threshold = float(os.getenv('VOLUME_Z_THRESHOLD', 3.0))
        self.price_z_threshold = float(os.getenv('PRICE_Z_THRESHOLD', 3.0))
        self.detection_mode = os.getenv('DETECTION_MODE', 'vol_only')
        
        # Symbol filter
        symbols_config = os.getenv('SYMBOLS', '').strip()
        if symbols_config:
            # Parse comma-separated list
            self.target_symbols = [s.strip() for s in symbols_config.split(',') if s.strip()]
            logger.info(f"Monitoring specific symbols: {self.target_symbols}")
        else:
            self.target_symbols = None  # Monitor all symbols
            logger.info("Monitoring all symbols")
        
        # Validate config
        if not all([self.private_key, self.main_wallet, self.discord_webhook]):
            raise ValueError("Missing required environment variables")
        
        # Initialize components
        self.client = HyperliquidClient(self.private_key, self.main_wallet)
        self.exchange = HyperliquidExchange(self.private_key, self.main_wallet)
        self.detector = VolumeAnomalyDetector(
            window_size=self.detector_window_size,
            volume_z_threshold=self.volume_z_threshold,
            price_z_threshold=self.price_z_threshold,
            detection_mode=self.detection_mode,
            min_samples=10,
            min_volume_usd=0  # No minimum volume filter
        )
        self.notifier = DiscordNotifier(self.discord_webhook)
        
        # Track active orders and positions
        self.active_orders = {}  # Track pending orders by symbol
        self.position_tracker = {}  # Track positions to close after timeout
        
        # Control flag
        self.running = False
        
        # Log configuration
        logger.info("Initialized Anomaly Trading Bot")
        logger.info(f"  API Wallet: {self.exchange.api_wallet_address}")
        logger.info(f"  Main Wallet: {self.main_wallet}")
        logger.info(f"  Monitoring Interval: {self.monitoring_interval}s")
        logger.info(f"  Price Multipliers: {self.price_multipliers}")
        logger.info(f"  Order Amounts: {self.order_amounts_usdc} USDC")
        logger.info(f"  Order Timeout: {self.order_timeout}s")
        logger.info(f"  Position Close Timeout: {self.position_close_timeout}s")
        logger.info(f"  Target Symbols: {len(self.target_symbols) if self.target_symbols else 'All'} symbols")
        logger.info(f"  Max Concurrent Orders: {self.max_concurrent_orders}")
        logger.info(f"  Detection Mode: {self.detection_mode}")
        logger.info(f"  Volume Z-threshold: {self.volume_z_threshold}")
        logger.info(f"  Price Z-threshold: {self.price_z_threshold}")
        
    async def start(self):
        """Start the trading bot"""
        self.running = True
        logger.info("Starting trading bot...")
        
        # Send startup notification
        await self.notifier.send_status_update(
            "🚀 Bot Started",
            {
                "Wallet": self.main_wallet[-8:] + "...",
                "Monitoring": f"{len(self.target_symbols) if self.target_symbols else 'All'} symbols",
                "Mode": self.detection_mode,
                "Orders Config": f"{len(self.price_multipliers)} orders per anomaly"
            }
        )
        
        # Get initial balance
        try:
            user_state = self.exchange.get_user_state()
            balance = user_state.get("marginSummary", {}).get("accountValue", 0)
            logger.info(f"Account balance: ${balance}")
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
        
        iteration = 0
        while self.running:
            iteration += 1
            
            try:
                logger.info(f"Starting iteration {iteration}")
                
                # Fetch market data
                try:
                    asset_data = await self.client.get_all_asset_data()
                    
                    if not asset_data:
                        logger.warning("No asset data received")
                        if iteration == 1:  # Only notify on first failure
                            await self.notifier.send_error_notification(
                                "⚠️ No Market Data",
                                {"Message": "Failed to fetch market data", "Iteration": iteration}
                            )
                        await asyncio.sleep(self.monitoring_interval)
                        continue
                    
                    # Filter symbols if specified
                    if self.target_symbols:
                        filtered_data = {k: v for k, v in asset_data.items() if k in self.target_symbols}
                        if not filtered_data:
                            logger.warning(f"No data for target symbols: {self.target_symbols}")
                            await asyncio.sleep(self.monitoring_interval)
                            continue
                        asset_data = filtered_data
                        logger.debug(f"Monitoring {len(asset_data)} symbols: {list(asset_data.keys())}")
                except Exception as e:
                    logger.error(f"Error fetching market data: {e}")
                    await self.notifier.send_error_notification(
                        "❌ Market Data Error",
                        {"Error": str(e), "Iteration": iteration}
                    )
                    await asyncio.sleep(self.monitoring_interval)
                    continue
                
                # Detect anomalies only if no active orders AND no positions
                try:
                    # Get current positions from exchange
                    current_positions = self.exchange.get_positions()
                    
                    # Skip anomaly detection if we have active orders OR positions
                    if len(self.active_orders) > 0:
                        logger.debug(f"Skipping anomaly detection - {len(self.active_orders)} active orders")
                    elif len(current_positions) > 0:
                        logger.debug(f"Skipping anomaly detection - {len(current_positions)} open positions")
                    elif len(self.position_tracker) > 0:
                        logger.debug(f"Skipping anomaly detection - {len(self.position_tracker)} tracked positions")
                    else:
                        anomalies = self.detector.scan_all_assets(asset_data)
                        
                        if anomalies:
                            logger.info(f"Found {len(anomalies)} anomalies")
                            
                            for anomaly in anomalies:
                                # Check if we can place more orders
                                if len(self.active_orders) >= self.max_concurrent_orders:
                                    logger.info(f"Max concurrent orders reached, skipping remaining anomalies")
                                    break
                                
                                try:
                                    await self.process_anomaly(anomaly)
                                    # After placing orders, skip remaining anomalies
                                    if len(self.active_orders) > 0:
                                        break
                                    await asyncio.sleep(1)  # Rate limiting
                                except Exception as e:
                                    # Safe symbol extraction
                                    anomaly_symbol = 'Unknown'
                                    if isinstance(anomaly, dict):
                                        anomaly_symbol = anomaly.get('symbol', 'Unknown')
                                    logger.error(f"Error processing anomaly: {e}")
                                    await self.notifier.send_error_notification(
                                        "❌ Anomaly Processing Error",
                                        {"Symbol": anomaly_symbol, "Error": str(e)}
                                    )
                except Exception as e:
                    logger.error(f"Error in anomaly detection: {e}")
                    await self.notifier.send_error_notification(
                        "❌ Anomaly Detection Error",
                        {"Error": str(e), "Iteration": iteration}
                    )
                
                # Check and cancel expired orders
                await self.check_expired_orders()
                
                # Check and close positions that are too old
                await self.check_and_close_old_positions()
                
                # Status update every 10 iterations
                if iteration % 10 == 0:
                    await self.send_status_update(iteration)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                logger.info("Main loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await self.notifier.send_error_notification(
                    "❌ Main Loop Error",
                    {"Error": str(e), "Iteration": iteration, "Action": "Bot continues running"}
                )
                await asyncio.sleep(self.monitoring_interval)
        
        logger.info("Trading bot stopped")
    
    async def process_anomaly(self, anomaly):
        """Process detected anomaly and place multiple orders"""
        # Safe anomaly access with type checking
        if not isinstance(anomaly, dict):
            logger.error(f"Anomaly is not a dict: {type(anomaly)}")
            return
            
        symbol = anomaly.get('symbol')
        if not symbol:
            logger.error(f"No symbol in anomaly: {anomaly}")
            return
        
        # Skip if already has active order for this symbol
        if symbol in self.active_orders:
            logger.info(f"Skipping {symbol} - already has active orders")
            return
        
        # Check max concurrent orders limit
        if len(self.active_orders) >= self.max_concurrent_orders:
            logger.info(f"Skipping {symbol} - max concurrent orders ({self.max_concurrent_orders}) reached")
            return
        
        try:
            # Get last normal price from detector
            last_normal_price = self.detector.last_normal_price.get(symbol)
            if not last_normal_price:
                logger.warning(f"No last normal price for {symbol}")
                return
            
            # Ensure price is a float
            last_normal_price = float(last_normal_price)
            
            current_price = anomaly.get('current_price', 0)
            if not current_price:
                logger.warning(f"No current price in anomaly for {symbol}")
                return
            
            current_price = float(current_price)
            current_volume = float(anomaly.get('current_volume', 0))
            
            # Send anomaly detection notification
            safe_anomaly_details = {
                'symbol': str(symbol),
                'current_price': float(current_price),
                'current_volume': float(current_volume),
                'last_normal_price': float(last_normal_price),
                'price_change_ratio': float(current_price / last_normal_price) if last_normal_price > 0 else 1.0,
                'volume_z_score': float(anomaly.get('volume_z_score', 0)),
                'price_z_score': float(anomaly.get('price_z_score', 0)),
                'volume_anomaly': anomaly.get('volume_anomaly', False),
                'price_anomaly': anomaly.get('price_anomaly', False),
                'detection_mode': self.detection_mode
            }
            
            await self.notifier.send_anomaly_notification(
                symbol=symbol,
                anomaly_details=safe_anomaly_details
            )
            
            # Place multiple orders with different multipliers and amounts
            orders_placed = []
            for i, (multiplier, amount_usdc) in enumerate(zip(self.price_multipliers, self.order_amounts_usdc)):
                # Calculate target price and order size for this order
                target_price = last_normal_price * multiplier
                order_size = amount_usdc / target_price
                
                # Determine order side based on multiplier
                # If multiplier > 1: SELL (short) at higher price
                # If multiplier < 1: BUY (long) at lower price
                is_buy = multiplier < 1.0
                
                logger.info(f"Placing order {i+1}/{len(self.price_multipliers)} for {symbol}")
                logger.info(f"  Multiplier: {multiplier}x")
                logger.info(f"  Side: {'BUY' if is_buy else 'SELL'}")
                logger.info(f"  Target price: ${target_price:.4f}")
                logger.info(f"  Order size: {order_size:.6f} {symbol}")
                logger.info(f"  Amount: ${amount_usdc}")
                
                # Place order
                result = await self.exchange.place_limit_order(
                    symbol=symbol,
                    is_buy=is_buy,
                    price=target_price,
                    size=order_size,
                    post_only=True
                )
                
                if result.get('status') == 'success':
                    order_id = result.get('order_id')
                    order_info = {
                        'order_id': order_id,
                        'price': target_price,
                        'size': order_size,
                        'is_buy': is_buy,
                        'placed_at': datetime.now(),
                        'last_normal_price': last_normal_price,
                        'multiplier': multiplier,
                        'amount_usdc': amount_usdc
                    }
                    orders_placed.append(order_info)
                    
                    # Send notification for this order
                    await self.notifier.send_order_placed_notification(
                        symbol=symbol,
                        order_details={
                            'order_id': str(order_id) if order_id else 'Unknown',
                            'is_buy': is_buy,
                            'price': float(target_price),
                            'size': float(order_size),
                            'multiplier': float(multiplier),
                            'amount_usdc': float(amount_usdc),
                            'order_number': i + 1,
                            'total_orders': len(self.price_multipliers)
                        }
                    )
                    
                    logger.info(f"Order {i+1} placed successfully: {order_id}")
                else:
                    error_msg = result.get('message', 'Unknown error')
                    logger.error(f"Failed to place order {i+1}: {error_msg}")
                    await self.notifier.send_error_notification(
                        f"❌ Order {i+1} Failed",
                        {
                            "Symbol": symbol,
                            "Error": error_msg,
                            "Price": f"${target_price:.4f}",
                            "Size": f"{order_size:.6f}",
                            "Multiplier": f"{multiplier}x"
                        }
                    )
            
            # Store all orders for this symbol
            if orders_placed:
                self.active_orders[symbol] = orders_placed
                
                # Track position for future closing (using first order as reference)
                first_order = orders_placed[0]
                self.position_tracker[symbol] = {
                    'opened_at': first_order['placed_at'],
                    'is_buy': first_order['is_buy'],
                    'entry_prices': [o['price'] for o in orders_placed],
                    'sizes': [o['size'] for o in orders_placed],
                    'total_size': sum(o['size'] for o in orders_placed),
                    'orders_count': len(orders_placed)
                }
                
                logger.info(f"Successfully placed {len(orders_placed)}/{len(self.price_multipliers)} orders for {symbol}")
                
        except Exception as e:
            logger.error(f"Error processing anomaly for {symbol}: {e}", exc_info=True)
            await self.notifier.send_error_notification(
                "❌ Order Processing Error",
                {"Symbol": symbol, "Error": str(e)}
            )
    
    async def check_and_close_old_positions(self):
        """Check and close positions that have been open too long"""
        current_time = datetime.now()
        
        # Get actual positions from exchange
        positions = self.exchange.get_positions()
        
        # First, check if any order got filled by checking positions
        for symbol, position in positions.items():
            # If we have a position but no tracker, it might be from a recently filled order
            if symbol not in self.position_tracker and symbol in self.active_orders:
                # Order got filled, move from active_orders to position_tracker
                logger.info(f"Order for {symbol} got filled, tracking position")
                orders_info = self.active_orders[symbol]
                if isinstance(orders_info, list) and len(orders_info) > 0:
                    first_order = orders_info[0]
                    self.position_tracker[symbol] = {
                        'opened_at': first_order.get('placed_at', current_time),
                        'is_buy': first_order.get('is_buy'),
                        'entry_prices': [o['price'] for o in orders_info],
                        'sizes': [o['size'] for o in orders_info],
                        'total_size': sum(o['size'] for o in orders_info),
                        'orders_count': len(orders_info)
                    }
                del self.active_orders[symbol]
        
        for symbol in list(self.position_tracker.keys()):
            tracker = self.position_tracker[symbol]
            
            # Ensure tracker is a dictionary
            if not isinstance(tracker, dict):
                logger.error(f"Invalid tracker format for {symbol}: {type(tracker)}")
                del self.position_tracker[symbol]
                continue
            
            opened_at = tracker.get('opened_at')
            if not opened_at:
                logger.error(f"No opened_at timestamp for {symbol}")
                del self.position_tracker[symbol]
                continue
            
            elapsed = (current_time - opened_at).seconds
            
            # Check if position should be closed
            if elapsed >= self.position_close_timeout:
                logger.info(f"Position {symbol} has been open for {elapsed}s, closing...")
                
                # Check if position actually exists
                if symbol not in positions:
                    logger.info(f"No actual position found for {symbol}, removing from tracker")
                    del self.position_tracker[symbol]
                    continue
                
                position = positions[symbol]
                position_size = position['size']
                
                # Determine direction to close
                # If position size is positive (long), sell to close
                # If position size is negative (short), buy to close
                is_buy_to_close = position_size < 0
                
                try:
                    # Place market order to close position
                    result = await self.exchange.place_market_order(
                        symbol=symbol,
                        is_buy=is_buy_to_close,
                        size=abs(position_size),
                        reduce_only=True
                    )
                    
                    if result.get('status') == 'success':
                        logger.info(f"Successfully closed {symbol} position")
                        
                        # Send notification
                        await self.notifier.send_status_update(
                            f"🔴 Position Closed (Timeout)",
                            {
                                "Symbol": symbol,
                                "Size": f"{abs(position_size):.6f}",
                                "Direction": "Long" if position_size > 0 else "Short",
                                "Entry Prices": tracker.get('entry_prices', []),
                                "PnL": f"${position.get('pnl', 0):.2f}",
                                "Time Held": f"{elapsed}s"
                            }
                        )
                        
                        # Remove from tracker after successful close
                        del self.position_tracker[symbol]
                    else:
                        error_msg = result.get('message', 'Unknown error')
                        logger.error(f"Failed to close position: {error_msg}")
                        await self.notifier.send_error_notification(
                            "❌ Position Close Failed",
                            {
                                "Symbol": symbol,
                                "Error": error_msg,
                                "Size": f"{abs(position_size):.6f}"
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Error closing position for {symbol}: {e}")
                    await self.notifier.send_error_notification(
                        "❌ Position Close Error",
                        {"Symbol": symbol, "Error": str(e)}
                    )
    
    async def check_expired_orders(self):
        """Check and cancel expired orders"""
        current_time = datetime.now()
        
        for symbol in list(self.active_orders.keys()):
            orders = self.active_orders[symbol]
            
            # Handle both single orders and lists of orders
            if not isinstance(orders, list):
                orders = [orders]
            
            remaining_orders = []
            for order in orders:
                if not isinstance(order, dict):
                    continue
                    
                placed_at = order.get('placed_at')
                if not placed_at:
                    continue
                
                elapsed = (current_time - placed_at).seconds
                
                if elapsed >= self.order_timeout:
                    order_id = order.get('order_id')
                    logger.info(f"Cancelling expired order {order_id} for {symbol} (age: {elapsed}s)")
                    
                    try:
                        result = await self.exchange.cancel_order(symbol, order_id)
                        if result.get('status') == 'success':
                            logger.info(f"Successfully cancelled order {order_id}")
                            await self.notifier.send_status_update(
                                "⏱️ Order Cancelled (Timeout)",
                                {
                                    "Symbol": symbol,
                                    "Order ID": str(order_id)[:8] + "...",
                                    "Price": f"${order.get('price', 0):.4f}",
                                    "Multiplier": f"{order.get('multiplier', 0)}x",
                                    "Time": f"{elapsed}s"
                                }
                            )
                        else:
                            logger.error(f"Failed to cancel order: {result}")
                            remaining_orders.append(order)
                    except Exception as e:
                        logger.error(f"Error cancelling order {order_id}: {e}")
                        remaining_orders.append(order)
                else:
                    remaining_orders.append(order)
            
            # Update or remove orders for this symbol
            if remaining_orders:
                self.active_orders[symbol] = remaining_orders
            else:
                del self.active_orders[symbol]
                # Also remove from position tracker if no orders left
                if symbol in self.position_tracker:
                    del self.position_tracker[symbol]
    
    async def send_status_update(self, iteration):
        """Send periodic status update"""
        try:
            user_state = self.exchange.get_user_state()
            balance = user_state.get("marginSummary", {}).get("accountValue", 0)
            
            positions = self.exchange.get_positions()
            
            status_data = {
                "Iteration": iteration,
                "Balance": f"${balance}",
                "Active Orders": len(self.active_orders),
                "Open Positions": len(positions),
                "Symbols Monitored": len(self.target_symbols) if self.target_symbols else "All"
            }
            
            await self.notifier.send_status_update("📊 Status Update", status_data)
        except Exception as e:
            logger.error(f"Failed to send status update: {e}")
    
    def stop(self):
        """Stop the trading bot"""
        self.running = False
        logger.info("Stopping trading bot...")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    if hasattr(signal_handler, 'bot'):
        signal_handler.bot.stop()


async def main():
    """Main entry point"""
    bot = AnomalyTradingBot()
    signal_handler.bot = bot
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        bot.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        bot.stop()


if __name__ == "__main__":
    asyncio.run(main())