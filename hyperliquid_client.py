import asyncio
import pybotters
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class HyperliquidClient:
    def __init__(self, api_key: str, api_secret: str, wallet_address: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.wallet_address = wallet_address
        self.base_url = "https://api.hyperliquid.xyz"
        
    async def create_session(self):
        return pybotters.Client(apis={
            'hyperliquid': [self.api_key, self.api_secret.encode()]
        })
    
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        async with await self.create_session() as client:
            response = await client.get(
                f"{self.base_url}/info",
                params={
                    "type": "meta"
                }
            )
            data = await response.json()
            
            for universe in data.get("universe", []):
                if universe.get("name") == symbol:
                    return universe
            return {}
    
    async def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        async with await self.create_session() as client:
            response = await client.get(
                f"{self.base_url}/info",
                params={
                    "type": "l2Book",
                    "coin": symbol
                }
            )
            return await response.json()
    
    async def get_recent_trades(self, symbol: str) -> List[Dict]:
        async with await self.create_session() as client:
            response = await client.get(
                f"{self.base_url}/info",
                params={
                    "type": "recentTrades",
                    "coin": symbol
                }
            )
            data = await response.json()
            return data if isinstance(data, list) else []
    
    async def get_candles(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[Dict]:
        async with await self.create_session() as client:
            response = await client.get(
                f"{self.base_url}/info",
                params={
                    "type": "candles",
                    "coin": symbol,
                    "interval": interval,
                    "limit": limit
                }
            )
            data = await response.json()
            return data if isinstance(data, list) else []
    
    async def place_limit_order(
        self, 
        symbol: str, 
        is_buy: bool, 
        price: float, 
        size: float,
        reduce_only: bool = False,
        post_only: bool = True
    ) -> Dict[str, Any]:
        async with await self.create_session() as client:
            order_data = {
                "coin": symbol,
                "isBuy": is_buy,
                "px": str(price),
                "sz": str(size),
                "orderType": "Limit",
                "reduceOnly": reduce_only,
                "postOnly": post_only,
                "clientOrderId": None
            }
            
            response = await client.post(
                f"{self.base_url}/exchange",
                json={
                    "action": {
                        "type": "order",
                        "orders": [order_data]
                    },
                    "address": self.wallet_address,
                    "nonce": int(datetime.now().timestamp() * 1000)
                }
            )
            return await response.json()
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        async with await self.create_session() as client:
            response = await client.post(
                f"{self.base_url}/exchange",
                json={
                    "action": {
                        "type": "cancel",
                        "cancels": [{
                            "coin": symbol,
                            "oid": order_id
                        }]
                    },
                    "address": self.wallet_address,
                    "nonce": int(datetime.now().timestamp() * 1000)
                }
            )
            return await response.json()
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        async with await self.create_session() as client:
            response = await client.get(
                f"{self.base_url}/info",
                params={
                    "type": "openOrders",
                    "user": self.wallet_address
                }
            )
            data = await response.json()
            if symbol and isinstance(data, list):
                return [order for order in data if order.get("coin") == symbol]
            return data if isinstance(data, list) else []
    
    async def get_user_state(self) -> Dict[str, Any]:
        async with await self.create_session() as client:
            response = await client.get(
                f"{self.base_url}/info",
                params={
                    "type": "userState",
                    "user": self.wallet_address
                }
            )
            return await response.json()