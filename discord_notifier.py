import discord
from discord.ext import commands
import asyncio
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.webhook = None
        self._setup_webhook()
    
    def _setup_webhook(self):
        try:
            from discord import SyncWebhook
            self.webhook = SyncWebhook.from_url(self.webhook_url)
        except Exception as e:
            logger.error(f"Failed to setup Discord webhook: {e}")
    
    async def send_anomaly_notification(
        self,
        symbol: str,
        anomaly_details: Dict[str, Any],
        order_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            embed = discord.Embed(
                title="🚨 異常値検知アラート",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="シンボル",
                value=symbol,
                inline=True
            )
            
            embed.add_field(
                name="現在価格",
                value=f"${anomaly_details.get('current_price', 'N/A'):,.4f}",
                inline=True
            )
            
            embed.add_field(
                name="出来高",
                value=f"{anomaly_details.get('current_volume', 'N/A'):,.2f}",
                inline=True
            )
            
            embed.add_field(
                name="価格Zスコア",
                value=f"{anomaly_details.get('price_z_score', 'N/A')}",
                inline=True
            )
            
            embed.add_field(
                name="出来高Zスコア",
                value=f"{anomaly_details.get('volume_z_score', 'N/A')}",
                inline=True
            )
            
            embed.add_field(
                name="異常タイプ",
                value=self._get_anomaly_type(anomaly_details),
                inline=True
            )
            
            if anomaly_details.get('last_normal_price'):
                embed.add_field(
                    name="前回正常価格",
                    value=f"${anomaly_details['last_normal_price']:,.4f}",
                    inline=True
                )
            
            if anomaly_details.get('price_change_ratio'):
                change_pct = (anomaly_details['price_change_ratio'] - 1) * 100
                embed.add_field(
                    name="価格変動率",
                    value=f"{change_pct:+.2f}%",
                    inline=True
                )
            
            if order_details:
                embed.add_field(
                    name="📊 注文情報",
                    value=self._format_order_details(order_details),
                    inline=False
                )
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.webhook.send, None, None, None, None, None, None, [embed])
            
            logger.info(f"Discord notification sent for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
    
    async def send_order_placed_notification(
        self,
        symbol: str,
        order_details: Dict[str, Any]
    ) -> bool:
        try:
            embed = discord.Embed(
                title="✅ 注文発注完了",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="シンボル",
                value=symbol,
                inline=True
            )
            
            embed.add_field(
                name="注文タイプ",
                value="買い" if order_details.get('is_buy') else "売り",
                inline=True
            )
            
            embed.add_field(
                name="注文価格",
                value=f"${order_details.get('price', 'N/A'):,.4f}",
                inline=True
            )
            
            embed.add_field(
                name="数量",
                value=f"{order_details.get('size', 'N/A'):,.4f}",
                inline=True
            )
            
            if order_details.get('order_id'):
                embed.add_field(
                    name="注文ID",
                    value=order_details['order_id'],
                    inline=False
                )
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.webhook.send, None, None, None, None, None, None, [embed])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send order placed notification: {e}")
            return False
    
    async def send_order_cancelled_notification(
        self,
        symbol: str,
        order_id: str,
        reason: str = "10分経過"
    ) -> bool:
        try:
            embed = discord.Embed(
                title="🔄 注文キャンセル",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="シンボル",
                value=symbol,
                inline=True
            )
            
            embed.add_field(
                name="注文ID",
                value=order_id,
                inline=True
            )
            
            embed.add_field(
                name="キャンセル理由",
                value=reason,
                inline=False
            )
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.webhook.send, None, None, None, None, None, None, [embed])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send order cancelled notification: {e}")
            return False
    
    async def send_error_notification(
        self,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            embed = discord.Embed(
                title="❌ エラー発生",
                description=error_message,
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            
            if error_details:
                for key, value in error_details.items():
                    embed.add_field(
                        name=key,
                        value=str(value)[:1024],
                        inline=False
                    )
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.webhook.send, None, None, None, None, None, None, [embed])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False
    
    async def send_status_update(
        self,
        status_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            embed = discord.Embed(
                title="ℹ️ ステータス更新",
                description=status_message,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            if details:
                for key, value in details.items():
                    embed.add_field(
                        name=key,
                        value=str(value)[:1024],
                        inline=True
                    )
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.webhook.send, None, None, None, None, None, None, [embed])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send status update: {e}")
            return False
    
    def _get_anomaly_type(self, anomaly_details: Dict[str, Any]) -> str:
        types = []
        if anomaly_details.get('price_anomaly'):
            types.append("価格")
        if anomaly_details.get('volume_anomaly'):
            types.append("出来高")
        return " & ".join(types) if types else "不明"
    
    def _format_order_details(self, order_details: Dict[str, Any]) -> str:
        lines = []
        if order_details.get('order_id'):
            lines.append(f"注文ID: {order_details['order_id']}")
        if order_details.get('price'):
            lines.append(f"価格: ${order_details['price']:,.4f}")
        if order_details.get('size'):
            lines.append(f"数量: {order_details['size']:,.4f}")
        if order_details.get('is_buy') is not None:
            lines.append(f"方向: {'買い' if order_details['is_buy'] else '売り'}")
        return "\n".join(lines) if lines else "詳細なし"