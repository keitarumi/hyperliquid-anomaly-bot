import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv
import signal
import sys

from hyperliquid_client import HyperliquidClient
from anomaly_detector import AnomalyDetector
from discord_notifier import DiscordNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.symbol = config['symbol']
        self.monitoring_interval = config.get('monitoring_interval', 10)
        self.order_timeout = config.get('order_timeout', 600)
        self.price_multiplier = config.get('price_multiplier', 3.0)
        self.order_size = config.get('order_size', 0.01)
        
        self.client = HyperliquidClient(
            api_key=config['api_key'],
            api_secret=config['api_secret'],
            wallet_address=config['wallet_address']
        )
        
        self.detector = AnomalyDetector(
            window_size=config.get('detector_window_size', 60),
            price_z_threshold=config.get('price_z_threshold', 3.0),
            volume_z_threshold=config.get('volume_z_threshold', 3.0)
        )
        
        self.notifier = DiscordNotifier(
            webhook_url=config['discord_webhook']
        )
        
        self.active_order = None
        self.order_placed_time = None
        self.running = False
        
    async def start(self):
        self.running = True
        logger.info(f"Starting trading bot for {self.symbol}")
        
        await self.notifier.send_status_update(
            "トレーディングボット起動",
            {
                "シンボル": self.symbol,
                "監視間隔": f"{self.monitoring_interval}秒",
                "価格倍率": f"{self.price_multiplier}x",
                "注文タイムアウト": f"{self.order_timeout}秒"
            }
        )
        
        try:
            await self.main_loop()
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            await self.notifier.send_error_notification(
                "ボットがクラッシュしました",
                {"エラー": str(e)}
            )
        finally:
            self.running = False
            logger.info("Trading bot stopped")
    
    async def main_loop(self):
        while self.running:
            try:
                await self.check_and_cancel_expired_order()
                
                if self.active_order is None:
                    await self.monitor_market()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                logger.info("Main loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(self.monitoring_interval)
    
    async def monitor_market(self):
        try:
            candles = await self.client.get_candles(self.symbol, interval="1m", limit=1)
            if not candles:
                logger.warning("No candle data received")
                return
            
            latest_candle = candles[0]
            current_price = float(latest_candle.get('close', 0))
            current_volume = float(latest_candle.get('volume', 0))
            
            if current_price <= 0 or current_volume < 0:
                logger.warning(f"Invalid data: price={current_price}, volume={current_volume}")
                return
            
            is_anomaly, anomaly_details = self.detector.detect_anomaly(current_price, current_volume)
            
            self.detector.add_data(current_price, current_volume)
            
            if is_anomaly and self.active_order is None:
                logger.info(f"Anomaly detected! Details: {anomaly_details}")
                await self.handle_anomaly(anomaly_details)
            else:
                logger.debug(f"Normal market conditions - Price: {current_price:.4f}, Volume: {current_volume:.2f}")
                
        except Exception as e:
            logger.error(f"Error monitoring market: {e}", exc_info=True)
    
    async def handle_anomaly(self, anomaly_details: Dict[str, Any]):
        try:
            target_price = self.detector.get_target_price(self.price_multiplier)
            
            if target_price is None:
                logger.warning("Cannot calculate target price - no normal price available")
                return
            
            current_price = anomaly_details['current_price']
            is_buy = current_price < target_price
            
            logger.info(f"Placing {'buy' if is_buy else 'sell'} order at {target_price:.4f}")
            
            order_result = await self.client.place_limit_order(
                symbol=self.symbol,
                is_buy=is_buy,
                price=target_price,
                size=self.order_size,
                reduce_only=False,
                post_only=True
            )
            
            if order_result and 'status' in order_result and order_result['status'] == 'success':
                order_id = order_result.get('response', {}).get('data', {}).get('statuses', [{}])[0].get('resting', {}).get('oid')
                
                if order_id:
                    self.active_order = {
                        'order_id': order_id,
                        'price': target_price,
                        'size': self.order_size,
                        'is_buy': is_buy
                    }
                    self.order_placed_time = datetime.now()
                    
                    await self.notifier.send_anomaly_notification(
                        self.symbol,
                        anomaly_details,
                        self.active_order
                    )
                    
                    await self.notifier.send_order_placed_notification(
                        self.symbol,
                        self.active_order
                    )
                    
                    logger.info(f"Order placed successfully: {order_id}")
                else:
                    logger.error("Order placed but no order ID received")
                    await self.notifier.send_error_notification(
                        "注文発注は成功しましたが、注文IDを取得できませんでした",
                        {"response": order_result}
                    )
            else:
                logger.error(f"Failed to place order: {order_result}")
                await self.notifier.send_error_notification(
                    "注文発注に失敗しました",
                    {"response": order_result}
                )
                
        except Exception as e:
            logger.error(f"Error handling anomaly: {e}", exc_info=True)
            await self.notifier.send_error_notification(
                "異常値処理中にエラーが発生しました",
                {"error": str(e)}
            )
    
    async def check_and_cancel_expired_order(self):
        if self.active_order is None or self.order_placed_time is None:
            return
        
        time_elapsed = (datetime.now() - self.order_placed_time).total_seconds()
        
        if time_elapsed >= self.order_timeout:
            logger.info(f"Order timeout reached ({self.order_timeout}s), cancelling order")
            
            try:
                cancel_result = await self.client.cancel_order(
                    self.symbol,
                    self.active_order['order_id']
                )
                
                if cancel_result and 'status' in cancel_result and cancel_result['status'] == 'success':
                    await self.notifier.send_order_cancelled_notification(
                        self.symbol,
                        self.active_order['order_id'],
                        f"{self.order_timeout}秒経過"
                    )
                    logger.info(f"Order {self.active_order['order_id']} cancelled successfully")
                else:
                    logger.warning(f"Failed to cancel order: {cancel_result}")
                    
            except Exception as e:
                logger.error(f"Error cancelling order: {e}", exc_info=True)
            finally:
                self.active_order = None
                self.order_placed_time = None
    
    async def check_order_fill(self):
        if self.active_order is None:
            return
        
        try:
            open_orders = await self.client.get_open_orders(self.symbol)
            
            order_exists = any(
                order.get('oid') == self.active_order['order_id']
                for order in open_orders
            )
            
            if not order_exists:
                logger.info(f"Order {self.active_order['order_id']} no longer open - likely filled")
                await self.notifier.send_status_update(
                    "注文が約定した可能性があります",
                    {"注文ID": self.active_order['order_id']}
                )
                self.active_order = None
                self.order_placed_time = None
                
        except Exception as e:
            logger.error(f"Error checking order status: {e}")
    
    def stop(self):
        logger.info("Stopping trading bot...")
        self.running = False


async def main():
    load_dotenv()
    
    config = {
        'api_key': os.getenv('HYPERLIQUID_API_KEY'),
        'api_secret': os.getenv('HYPERLIQUID_API_SECRET'),
        'wallet_address': os.getenv('HYPERLIQUID_WALLET_ADDRESS'),
        'discord_webhook': os.getenv('DISCORD_WEBHOOK_URL'),
        'symbol': os.getenv('TRADING_SYMBOL', 'BTC'),
        'monitoring_interval': int(os.getenv('MONITORING_INTERVAL', 10)),
        'order_timeout': int(os.getenv('ORDER_TIMEOUT', 600)),
        'price_multiplier': float(os.getenv('PRICE_MULTIPLIER', 3.0)),
        'order_size': float(os.getenv('ORDER_SIZE', 0.01)),
        'detector_window_size': int(os.getenv('DETECTOR_WINDOW_SIZE', 60)),
        'price_z_threshold': float(os.getenv('PRICE_Z_THRESHOLD', 3.0)),
        'volume_z_threshold': float(os.getenv('VOLUME_Z_THRESHOLD', 3.0))
    }
    
    missing_configs = []
    for key in ['api_key', 'api_secret', 'wallet_address', 'discord_webhook']:
        if not config.get(key):
            missing_configs.append(key.upper())
    
    if missing_configs:
        logger.error(f"Missing required configuration: {', '.join(missing_configs)}")
        logger.error("Please set the required environment variables in .env file")
        return
    
    bot = TradingBot(config)
    
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        bot.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())