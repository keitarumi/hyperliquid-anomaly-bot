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
    """Main trading bot that monitors all perps for anomalies"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get credentials
        self.private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
        self.main_wallet = os.getenv('HYPERLIQUID_MAIN_WALLET_ADDRESS')
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        
        # Trading parameters
        self.monitoring_interval = int(os.getenv('MONITORING_INTERVAL', 10))
        self.order_timeout = int(os.getenv('ORDER_TIMEOUT', 600))  # Cancel unfilled orders after this time
        self.position_close_timeout = int(os.getenv('POSITION_CLOSE_TIMEOUT', 1800))  # Close positions after 30 minutes
        self.price_multiplier = float(os.getenv('PRICE_MULTIPLIER', 3.0))
        self.order_amount_usdc = float(os.getenv('ORDER_AMOUNT_USDC', 100))  # Order size in USDC
        self.max_concurrent_orders = int(os.getenv('MAX_CONCURRENT_ORDERS', 1))  # Max orders at once
        
        # Detection parameters
        self.detector_window_size = int(os.getenv('DETECTOR_WINDOW_SIZE', 60))
        self.volume_z_threshold = float(os.getenv('VOLUME_Z_THRESHOLD', 3.0))
        
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
            z_score_threshold=self.volume_z_threshold,
            min_samples=10,
            min_volume_usd=0  # No minimum volume filter
        )
        self.notifier = DiscordNotifier(self.discord_webhook)
        
        # Track active orders and positions
        self.active_orders = {}  # Track pending orders
        self.position_tracker = {}  # Track positions to close after timeout
        self.running = False
        
        logger.info("Initialized Anomaly Trading Bot")
        logger.info(f"  API Wallet: {self.exchange.api_wallet_address}")
        logger.info(f"  Main Wallet: {self.main_wallet}")
        logger.info(f"  Monitoring Interval: {self.monitoring_interval}s")
        logger.info(f"  Price Multiplier: {self.price_multiplier}x")
        logger.info(f"  Order Timeout: {self.order_timeout}s")
        logger.info(f"  Position Close Timeout: {self.position_close_timeout}s")
        logger.info(f"  Target Symbols: {len(self.target_symbols) if self.target_symbols else 'All'} symbols")
        logger.info(f"  Max Concurrent Orders: {self.max_concurrent_orders}")
        
    async def start(self):
        """Start the trading bot"""
        self.running = True
        logger.info("Starting trading bot...")
        
        try:
            # Send startup notification
            wallet_display = str(self.main_wallet)[:8] + "..." if self.main_wallet and len(str(self.main_wallet)) > 8 else str(self.main_wallet or "N/A")
            await self.notifier.send_status_update(
                "🚀 Trading Bot Started",
                {
                    "Main Wallet": wallet_display,
                    "Monitoring Interval": f"{self.monitoring_interval}s",
                    "Price Multiplier": f"{self.price_multiplier}x",
                    "Order Size": f"${self.order_amount_usdc}",
                    "Symbols": ', '.join(self.target_symbols) if self.target_symbols else "All"
                }
            )
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")
        
        # Check account balance
        try:
            user_state = self.exchange.get_user_state()
            if 'marginSummary' in user_state:
                balance = user_state['marginSummary'].get('accountValue', 0)
                logger.info(f"Account balance: ${balance}")
                
                if float(balance) < 500:
                    logger.warning("Low account balance!")
                    await self.notifier.send_error_notification(
                        "⚠️ Low Balance Warning",
                        {"Balance": f"${balance}", "Recommended": "$500+"}
                    )
            else:
                logger.warning("Could not fetch account balance")
                await self.notifier.send_error_notification(
                    "⚠️ Balance Check Failed",
                    {"Error": "Could not fetch account state"}
                )
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            await self.notifier.send_error_notification(
                "❌ Balance Check Error",
                {"Error": str(e)}
            )
        
        # Main monitoring loop
        iteration = 0
        while self.running:
            try:
                iteration += 1
                logger.info(f"Starting iteration {iteration}")
                
                # Get all market data
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
                                    # After placing an order, skip remaining anomalies
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
        """Process detected anomaly and place order"""
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
            logger.info(f"Skipping {symbol} - already has active order")
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
            
            # Calculate target price (3x pre-anomaly price)
            target_price = last_normal_price * self.price_multiplier
            order_size = self.order_amount_usdc / target_price
            
            # Determine order side with safe access
            current_price = anomaly.get('current_price', 0)
            if not current_price:
                logger.warning(f"No current price in anomaly for {symbol}")
                return
            
            current_price = float(current_price)
            current_volume = float(anomaly.get('current_volume', 0))
            is_buy = current_price < last_normal_price
            
            logger.info(f"Placing {'BUY' if is_buy else 'SELL'} order for {symbol}")
            logger.info(f"  Last normal price: ${last_normal_price:.4f}")
            logger.info(f"  Current price: ${current_price:.4f}")
            logger.info(f"  Target price: ${target_price:.4f}")
            logger.info(f"  Order size: {order_size:.6f} {symbol}")
            
            # Send anomaly detection notification with safe details
            safe_anomaly_details = {
                'symbol': str(symbol),
                'current_price': float(current_price),
                'current_volume': float(current_volume),
                'last_normal_price': float(last_normal_price),
                'price_change_ratio': float(current_price / last_normal_price) if last_normal_price > 0 else 1.0,
                'volume_z_score': float(anomaly.get('volume_change_pct', 0)),
                'price_z_score': float(anomaly.get('price_change_pct', 0)),
                'volume_anomaly': True,
                'price_anomaly': abs(current_price - last_normal_price) > 0.01
            }
            
            await self.notifier.send_anomaly_notification(
                symbol=symbol,
                anomaly_details=safe_anomaly_details
            )
            
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
                order_time = datetime.now()
                self.active_orders[symbol] = {
                    'order_id': order_id,
                    'price': target_price,
                    'size': order_size,
                    'is_buy': is_buy,
                    'placed_at': order_time,
                    'last_normal_price': last_normal_price
                }
                
                # Track position for future closing
                self.position_tracker[symbol] = {
                    'opened_at': order_time,
                    'is_buy': is_buy,
                    'entry_price': target_price,
                    'size': order_size
                }
                
                # Send notification with safe order details
                await self.notifier.send_order_placed_notification(
                    symbol=symbol,
                    order_details={
                        'order_id': str(order_id) if order_id else 'Unknown',
                        'is_buy': is_buy,
                        'price': float(target_price),
                        'size': float(order_size)
                    }
                )
                
                logger.info(f"Order placed successfully: {order_id}")
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Failed to place order: {error_msg}")
                await self.notifier.send_error_notification(
                    "❌ Order Failed",
                    {
                        "Symbol": symbol,
                        "Error": error_msg,
                        "Price": f"${target_price:.4f}",
                        "Size": f"{order_size:.6f}"
                    }
                )
                
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
                order_info = self.active_orders[symbol]
                self.position_tracker[symbol] = {
                    'opened_at': order_info.get('placed_at', current_time),
                    'is_buy': order_info.get('is_buy'),
                    'entry_price': position.get('entry_px', order_info.get('price')),
                    'size': abs(position.get('size', order_info.get('size')))
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
                                "Entry Price": f"${tracker.get('entry_price', 0):.2f}",
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
            order = self.active_orders[symbol]
            # Ensure order is a dictionary
            if not isinstance(order, dict):
                logger.error(f"Invalid order format for {symbol}: {type(order)}")
                del self.active_orders[symbol]
                continue
            
            placed_at = order.get('placed_at')
            if not placed_at:
                logger.error(f"No placed_at timestamp for {symbol}")
                del self.active_orders[symbol]
                continue
                
            elapsed = (current_time - placed_at).seconds
            
            if elapsed >= self.order_timeout:
                logger.info(f"Cancelling expired order for {symbol}")
                
                try:
                    order_id = order.get('order_id') if isinstance(order, dict) else None
                    if not order_id:
                        logger.error(f"No order_id found for {symbol}")
                        del self.active_orders[symbol]
                        continue
                    
                    result = await self.exchange.cancel_order(
                        symbol=symbol,
                        order_id=order_id
                    )
                    
                    if result.get('status') == 'success':
                        order_id_value = order.get('order_id') if isinstance(order, dict) else order
                        logger.info(f"Order cancelled: {order_id_value}")
                        
                        # Send notification
                        await self.notifier.send_order_cancelled_notification(
                            symbol=symbol,
                            order_id=str(order_id_value),
                            reason='Timeout'
                        )
                    
                    # Only remove from active orders, keep position tracker for actual position management
                    del self.active_orders[symbol]
                    
                except Exception as e:
                    logger.error(f"Error cancelling order for {symbol}: {e}")
                    try:
                        # Ensure order_id is converted to string properly
                        order_id = order.get('order_id', 'Unknown')
                        order_id_str = str(order_id)
                        # Only truncate if it's actually a string with content
                        if isinstance(order_id_str, str) and len(order_id_str) > 8:
                            display_id = order_id_str[:8] + "..."
                        else:
                            display_id = order_id_str
                        await self.notifier.send_error_notification(
                            "❌ Cancel Order Error",
                            {"Symbol": symbol, "Order ID": display_id, "Error": str(e)}
                        )
                    except Exception as notify_error:
                        logger.error(f"Failed to send error notification: {notify_error}")
                    del self.active_orders[symbol]
    
    async def send_status_update(self, iteration):
        """Send periodic status update"""
        try:
            user_state = self.exchange.get_user_state()
            balance = 0
            
            if 'marginSummary' in user_state:
                balance = user_state['marginSummary'].get('accountValue', 0)
            
            await self.notifier.send_status_update(
                "📊 Bot Status Update",
                {
                    "Iteration": iteration,
                    "Active Orders": len(self.active_orders),
                    "Account Balance": f"${balance}",
                    "Uptime": f"{iteration * self.monitoring_interval}s"
                }
            )
        except Exception as e:
            logger.error(f"Error sending status update: {e}")
    
    def stop(self):
        """Stop the trading bot"""
        logger.info("Stopping trading bot...")
        self.running = False


async def main():
    """Main entry point"""
    bot = None
    
    try:
        bot = AnomalyTradingBot()
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            if bot:
                bot.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
        if bot and hasattr(bot, 'notifier'):
            try:
                await bot.notifier.send_status_update(
                    "🛑 Bot Stopped",
                    {"Reason": "User interrupted"}
                )
            except:
                pass
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Configuration Error: {e}")
        print("Please check your .env file configuration")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if bot and hasattr(bot, 'notifier'):
            try:
                await bot.notifier.send_error_notification(
                    "💀 Bot Fatal Error",
                    {"Error": str(e), "Type": type(e).__name__}
                )
            except:
                pass
        print(f"\n❌ Fatal Error: {e}")
    finally:
        logger.info("Shutdown complete")
        if bot and hasattr(bot, 'notifier'):
            try:
                await bot.notifier.send_status_update(
                    "⚪ Bot Shutdown Complete",
                    {"Status": "Offline"}
                )
            except:
                pass


if __name__ == "__main__":
    asyncio.run(main())