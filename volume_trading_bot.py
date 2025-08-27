import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv
import signal
import sys
from collections import defaultdict

from hyperliquid_client import HyperliquidClient
from volume_anomaly_detector import VolumeAnomalyDetector
from discord_notifier import DiscordNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('volume_trading.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class OrderInfo:
    def __init__(self, symbol: str, order_id: str, price: float, size: float, is_buy: bool, placed_time: datetime):
        self.symbol = symbol
        self.order_id = order_id
        self.price = price
        self.size = size
        self.is_buy = is_buy
        self.placed_time = placed_time
        self.cancel_time = placed_time + timedelta(minutes=10)


class VolumeTradingBot:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.monitoring_interval = config.get('monitoring_interval', 30)
        
        # Trading parameters
        self.order_size_usdc = config.get('order_size_usdc', 100)  # 100 USDC
        self.price_multiplier = config.get('price_multiplier', 3.0)  # 3x normal price
        self.order_timeout_minutes = config.get('order_timeout_minutes', 10)  # 10 minutes
        
        # Detection parameters (lower for testing)
        self.volume_spike_threshold = config.get('volume_spike_threshold', 1.5)
        self.volume_drop_threshold = config.get('volume_drop_threshold', 0.5)
        self.min_volume_usd = config.get('min_volume_usd', 10000)
        
        self.client = HyperliquidClient(
            private_key=config['private_key'],
            wallet_address=config['wallet_address']
        )
        
        self.detector = VolumeAnomalyDetector(
            window_size=config.get('detector_window_size', 30),
            volume_spike_threshold=self.volume_spike_threshold,
            volume_drop_threshold=self.volume_drop_threshold,
            min_samples=config.get('min_samples', 5),
            min_volume_usd=self.min_volume_usd
        )
        
        self.notifier = DiscordNotifier(
            webhook_url=config['discord_webhook']
        )
        
        # Order management
        self.active_orders: Dict[str, OrderInfo] = {}  # symbol -> OrderInfo
        self.completed_orders: List[OrderInfo] = []
        
        self.running = False
        self.iteration_count = 0
        self.anomaly_count = 0
        self.order_count = 0
        
    async def start(self):
        self.running = True
        logger.info("Starting Volume Trading Bot")
        
        await self.notifier.send_status_update(
            "🤖 ボリューム取引ボット起動",
            {
                "監視間隔": f"{self.monitoring_interval}秒",
                "注文サイズ": f"${self.order_size_usdc}",
                "価格倍率": f"{self.price_multiplier}x",
                "注文タイムアウト": f"{self.order_timeout_minutes}分",
                "スパイク閾値": f"{self.volume_spike_threshold}x",
                "ドロップ閾値": f"{self.volume_drop_threshold}x"
            }
        )
        
        try:
            # Build up initial history
            logger.info("Building initial volume history...")
            for i in range(3):
                await self.scan_markets(notify=False, place_orders=False)
                if i < 2:
                    await asyncio.sleep(10)
            
            logger.info("Starting main trading loop...")
            await self.main_loop()
            
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            await self.notifier.send_error_notification(
                "ボットがクラッシュしました",
                {"エラー": str(e)}
            )
        finally:
            # Cancel all remaining orders
            await self.cancel_all_orders()
            self.running = False
            logger.info("Volume Trading Bot stopped")
    
    async def main_loop(self):
        while self.running:
            try:
                self.iteration_count += 1
                
                # Check and cancel expired orders
                await self.check_and_cancel_expired_orders()
                
                # Scan markets and place orders
                await self.scan_markets(notify=True, place_orders=True)
                
                # Send periodic status update
                if self.iteration_count % 10 == 0:
                    await self.send_status_summary()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                logger.info("Main loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(self.monitoring_interval)
    
    async def scan_markets(self, notify: bool = True, place_orders: bool = True):
        """Scan all markets for volume anomalies and place orders"""
        try:
            # Get all asset data efficiently
            asset_data = await self.client.get_all_asset_data()
            
            if not asset_data:
                logger.warning("No asset data received")
                return
            
            # Detect anomalies
            anomalies = self.detector.scan_all_assets(asset_data)
            
            if anomalies and notify:
                logger.info(f"Found {len(anomalies)} volume anomalies")
                self.anomaly_count += len(anomalies)
                
                # Process anomalies and place orders
                for anomaly in anomalies:
                    symbol = anomaly['symbol']
                    
                    # Skip if we already have an active order for this symbol
                    if symbol in self.active_orders:
                        logger.info(f"Skipping {symbol} - already has active order")
                        continue
                    
                    # Send notification
                    await self.send_anomaly_notification(anomaly)
                    
                    # Place order if enabled
                    if place_orders:
                        await self.place_anomaly_order(symbol, anomaly)
                    
                    await asyncio.sleep(0.5)  # Rate limiting
            
            # Log status
            if self.active_orders:
                logger.info(f"Active orders: {len(self.active_orders)}")
                
        except Exception as e:
            logger.error(f"Error scanning markets: {e}", exc_info=True)
    
    async def place_anomaly_order(self, symbol: str, anomaly: Dict[str, Any]):
        """Place a limit order when anomaly is detected"""
        try:
            # Get last normal price from detector
            last_normal_price = self.detector.last_normal_price.get(symbol)
            
            if not last_normal_price:
                logger.warning(f"No last normal price for {symbol}, using current price")
                last_normal_price = anomaly['current_price']
            
            # Calculate target price (3x last normal price)
            target_price = last_normal_price * self.price_multiplier
            
            # Determine if buy or sell based on anomaly type
            # If volume spike and price drop -> buy opportunity
            # If volume spike and price rise -> sell opportunity
            current_price = anomaly['current_price']
            is_buy = current_price < last_normal_price
            
            # Calculate order size in base asset
            order_size = self.order_size_usdc / target_price
            
            logger.info(f"Placing {'buy' if is_buy else 'sell'} order for {symbol} at ${target_price:.4f}, size: {order_size:.6f}")
            
            # Place the order
            order_result = await self.client.place_limit_order(
                symbol=symbol,
                is_buy=is_buy,
                price=target_price,
                size=order_size,
                reduce_only=False,
                post_only=True
            )
            
            if order_result and 'status' in order_result and order_result['status'] == 'success':
                order_id = order_result.get('response', {}).get('data', {}).get('statuses', [{}])[0].get('resting', {}).get('oid')
                
                if order_id:
                    # Store order info
                    order_info = OrderInfo(
                        symbol=symbol,
                        order_id=order_id,
                        price=target_price,
                        size=order_size,
                        is_buy=is_buy,
                        placed_time=datetime.now()
                    )
                    self.active_orders[symbol] = order_info
                    self.order_count += 1
                    
                    # Send notification
                    await self.send_order_notification(order_info, anomaly)
                    
                    logger.info(f"Order placed successfully: {order_id}")
                else:
                    logger.error(f"Order placed but no order ID received for {symbol}")
            else:
                logger.error(f"Failed to place order for {symbol}: {order_result}")
                
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}", exc_info=True)
    
    async def check_and_cancel_expired_orders(self):
        """Check for orders that have exceeded timeout and cancel them"""
        current_time = datetime.now()
        orders_to_cancel = []
        
        for symbol, order_info in self.active_orders.items():
            if current_time >= order_info.cancel_time:
                orders_to_cancel.append(symbol)
        
        for symbol in orders_to_cancel:
            await self.cancel_order(symbol)
    
    async def cancel_order(self, symbol: str):
        """Cancel an active order"""
        if symbol not in self.active_orders:
            return
        
        order_info = self.active_orders[symbol]
        
        try:
            logger.info(f"Cancelling order for {symbol}: {order_info.order_id}")
            
            cancel_result = await self.client.cancel_order(symbol, order_info.order_id)
            
            if cancel_result and 'status' in cancel_result and cancel_result['status'] == 'success':
                # Move to completed orders
                self.completed_orders.append(order_info)
                del self.active_orders[symbol]
                
                # Send notification
                await self.send_cancel_notification(order_info)
                
                logger.info(f"Order cancelled successfully: {order_info.order_id}")
            else:
                logger.warning(f"Failed to cancel order: {cancel_result}")
                # Remove from active orders anyway
                del self.active_orders[symbol]
                
        except Exception as e:
            logger.error(f"Error cancelling order for {symbol}: {e}", exc_info=True)
            # Remove from active orders
            if symbol in self.active_orders:
                del self.active_orders[symbol]
    
    async def cancel_all_orders(self):
        """Cancel all active orders"""
        symbols = list(self.active_orders.keys())
        for symbol in symbols:
            await self.cancel_order(symbol)
    
    async def send_anomaly_notification(self, anomaly: Dict[str, Any]):
        """Send Discord notification for anomaly"""
        try:
            import discord
            
            emoji = "🚀" if anomaly["anomaly_type"] == "spike" else "📉"
            color = discord.Color.green() if anomaly["anomaly_type"] == "spike" else discord.Color.red()
            
            embed = discord.Embed(
                title=f"{emoji} ボリューム異常検知: {anomaly['symbol']}",
                color=color,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="異常タイプ",
                value=f"{'急増' if anomaly['anomaly_type'] == 'spike' else '急減'}",
                inline=True
            )
            
            embed.add_field(
                name="現在価格",
                value=f"${anomaly['current_price']:,.4f}",
                inline=True
            )
            
            embed.add_field(
                name="出来高変動",
                value=f"{anomaly['volume_change_pct']:+.1f}%",
                inline=True
            )
            
            # Send via webhook
            loop = asyncio.get_event_loop()
            from discord import SyncWebhook
            webhook = SyncWebhook.from_url(self.config['discord_webhook'])
            await loop.run_in_executor(None, lambda: webhook.send(embeds=[embed]))
            
        except Exception as e:
            logger.error(f"Failed to send anomaly notification: {e}")
    
    async def send_order_notification(self, order_info: OrderInfo, anomaly: Dict[str, Any]):
        """Send Discord notification for placed order"""
        try:
            import discord
            
            embed = discord.Embed(
                title=f"📊 注文発注: {order_info.symbol}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="注文タイプ",
                value="買い" if order_info.is_buy else "売り",
                inline=True
            )
            
            embed.add_field(
                name="注文価格",
                value=f"${order_info.price:,.4f}",
                inline=True
            )
            
            embed.add_field(
                name="数量",
                value=f"{order_info.size:.6f}",
                inline=True
            )
            
            embed.add_field(
                name="想定金額",
                value=f"${self.order_size_usdc:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="前回正常価格",
                value=f"${order_info.price / self.price_multiplier:,.4f}",
                inline=True
            )
            
            embed.add_field(
                name="キャンセル予定",
                value=f"{self.order_timeout_minutes}分後",
                inline=True
            )
            
            embed.set_footer(text=f"Order ID: {order_info.order_id[:8]}...")
            
            # Send via webhook
            loop = asyncio.get_event_loop()
            from discord import SyncWebhook
            webhook = SyncWebhook.from_url(self.config['discord_webhook'])
            await loop.run_in_executor(None, lambda: webhook.send(embeds=[embed]))
            
        except Exception as e:
            logger.error(f"Failed to send order notification: {e}")
    
    async def send_cancel_notification(self, order_info: OrderInfo):
        """Send Discord notification for cancelled order"""
        try:
            import discord
            
            embed = discord.Embed(
                title=f"❌ 注文キャンセル: {order_info.symbol}",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="注文タイプ",
                value="買い" if order_info.is_buy else "売り",
                inline=True
            )
            
            embed.add_field(
                name="注文価格",
                value=f"${order_info.price:,.4f}",
                inline=True
            )
            
            embed.add_field(
                name="理由",
                value=f"{self.order_timeout_minutes}分タイムアウト",
                inline=True
            )
            
            # Send via webhook
            loop = asyncio.get_event_loop()
            from discord import SyncWebhook
            webhook = SyncWebhook.from_url(self.config['discord_webhook'])
            await loop.run_in_executor(None, lambda: webhook.send(embeds=[embed]))
            
        except Exception as e:
            logger.error(f"Failed to send cancel notification: {e}")
    
    async def send_status_summary(self):
        """Send periodic status summary"""
        await self.notifier.send_status_update(
            "📊 取引ステータス",
            {
                "イテレーション": self.iteration_count,
                "検出異常数": self.anomaly_count,
                "発注数": self.order_count,
                "アクティブ注文": len(self.active_orders),
                "完了注文": len(self.completed_orders),
                "稼働時間": f"{self.iteration_count * self.monitoring_interval // 60}分"
            }
        )
    
    def stop(self):
        logger.info("Stopping Volume Trading Bot...")
        self.running = False


async def main():
    load_dotenv()
    
    config = {
        'private_key': os.getenv('HYPERLIQUID_PRIVATE_KEY'),
        'wallet_address': os.getenv('HYPERLIQUID_WALLET_ADDRESS'),
        'discord_webhook': os.getenv('DISCORD_WEBHOOK_URL'),
        'monitoring_interval': int(os.getenv('VOLUME_MONITORING_INTERVAL', 30)),
        'order_size_usdc': float(os.getenv('ORDER_SIZE_USDC', 100)),
        'price_multiplier': float(os.getenv('PRICE_MULTIPLIER', 3.0)),
        'order_timeout_minutes': int(os.getenv('ORDER_TIMEOUT_MINUTES', 10)),
        'volume_spike_threshold': float(os.getenv('VOLUME_SPIKE_THRESHOLD', 1.5)),
        'volume_drop_threshold': float(os.getenv('VOLUME_DROP_THRESHOLD', 0.5)),
        'min_volume_usd': float(os.getenv('MIN_VOLUME_USD', 10000)),
        'detector_window_size': int(os.getenv('DETECTOR_WINDOW_SIZE', 30)),
        'min_samples': int(os.getenv('MIN_SAMPLES', 5))
    }
    
    missing_configs = []
    for key in ['private_key', 'wallet_address', 'discord_webhook']:
        if not config.get(key):
            missing_configs.append(key.upper())
    
    if missing_configs:
        logger.error(f"Missing required configuration: {', '.join(missing_configs)}")
        logger.error("Please set the required environment variables in .env file")
        return
    
    bot = VolumeTradingBot(config)
    
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