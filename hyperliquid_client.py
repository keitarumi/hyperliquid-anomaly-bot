import asyncio
import pybotters
import aiohttp
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class HyperliquidClient:
    def __init__(self, private_key: str, wallet_address: str):
        self.private_key = private_key
        self.wallet_address = wallet_address
        self.base_url = "https://api.hyperliquid.xyz"
        
    async def create_session(self):
        # pybotters derives the wallet address from the private key
        return pybotters.Client(apis={
            'hyperliquid': self.private_key
        })
    
    async def create_info_session(self):
        """Create a session for info endpoints (no auth needed)"""
        return aiohttp.ClientSession()
    
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/info",
                json={
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
            response = await client.post(
                f"{self.base_url}/info",
                json={
                    "type": "l2Book",
                    "coin": symbol
                }
            )
            return await response.json()
    
    async def get_recent_trades(self, symbol: str) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/info",
                json={
                    "type": "recentTrades",
                    "coin": symbol
                }
            )
            data = await response.json()
            return data if isinstance(data, list) else []
    
    async def get_candles(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (limit * 60 * 1000)  # limit minutes back
            
            response = await session.post(
                f"{self.base_url}/info",
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": symbol,
                        "interval": interval,
                        "startTime": start_time,
                        "endTime": end_time
                    }
                }
            )
            data = await response.json()
            
            if isinstance(data, list):
                # Convert candle format to standardized format
                candles = []
                for candle in data:
                    candles.append({
                        "t": candle.get("t"),
                        "open": candle.get("o"),
                        "high": candle.get("h"),
                        "low": candle.get("l"),
                        "close": candle.get("c"),
                        "volume": candle.get("v", 0)
                    })
                return candles
            return []
    
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
                "a": self._get_asset_id(symbol),
                "b": is_buy,
                "p": str(price),
                "s": str(size),
                "r": reduce_only,
                "t": {"limit": {"tif": "Gtc" if not post_only else "Alo"}}
            }
            
            # pybotters handles Hyperliquid auth and JSON conversion
            # We must use data= parameter (not json=)
            response = await client.post(
                f"{self.base_url}/exchange",
                data={
                    "action": {
                        "type": "order",
                        "orders": [order_data],
                        "grouping": "na"
                    }
                }
            )
            
            # Parse response - Hyperliquid returns JSON even on error
            try:
                result = await response.json()
                return result
            except Exception as e:
                text = await response.text()
                logger.error(f"Could not parse response: {text}")
                return {"status": "error", "message": str(e)}
    
    def _get_asset_id(self, symbol: str) -> int:
        # Updated asset map based on current Hyperliquid indices
        asset_map = {
            "BTC": 0,
            "ETH": 1,
            "ATOM": 2,
            "MATIC": 3,
            "DYDX": 4,
            "SOL": 5,
            "AVAX": 6,
            "BNB": 7,
            "APE": 8,
            "OP": 9,
            "LTC": 10,
            "ARB": 11,
            "DOGE": 12,
            "INJ": 13,
            "SUI": 14,
            "kPEPE": 15,
            "CRV": 16,
            "LDO": 17,
            "LINK": 18,
            "STX": 19
        }
        # For unknown symbols, we should probably fetch dynamically
        # but for now return the symbol itself as fallback
        return asset_map.get(symbol, 0)
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        async with await self.create_session() as client:
            response = await client.post(
                f"{self.base_url}/exchange",
                data={
                    "action": {
                        "type": "cancel",
                        "cancels": [{
                            "a": self._get_asset_id(symbol),
                            "o": order_id
                        }]
                    }
                }
            )
            
            # Parse response
            try:
                result = await response.json()
                return result
            except Exception as e:
                text = await response.text()
                logger.error(f"Could not parse response: {text}")
                return {"status": "error", "message": str(e)}
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/info",
                json={
                    "type": "openOrders",
                    "user": self.wallet_address
                }
            )
            data = await response.json()
            if symbol and isinstance(data, list):
                return [order for order in data if order.get("coin") == symbol]
            return data if isinstance(data, list) else []
    
    async def get_user_state(self) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/info",
                json={
                    "type": "userState",
                    "user": self.wallet_address
                }
            )
            return await response.json()
    
    async def get_all_perp_symbols(self) -> List[str]:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/info",
                json={
                    "type": "meta"
                }
            )
            data = await response.json()
            
            symbols = []
            for universe in data.get("universe", []):
                symbol = universe.get("name")
                if symbol:
                    symbols.append(symbol)
            
            logger.info(f"Found {len(symbols)} perp symbols")
            return symbols
    
    async def get_all_mids(self) -> Dict[str, float]:
        """Get current mid prices for all assets"""
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/info",
                json={"type": "allMids"}
            )
            data = await response.json()
            return data if isinstance(data, dict) else {}
    
    async def get_all_asset_data(self) -> Dict[str, Dict[str, Any]]:
        """Get price and volume data for all assets efficiently"""
        async with aiohttp.ClientSession() as session:
            # Get meta and asset contexts in one call
            response = await session.post(
                f"{self.base_url}/info",
                json={"type": "metaAndAssetCtxs"}
            )
            data = await response.json()
            
            if not isinstance(data, list) or len(data) < 2:
                logger.error("Unexpected response format from metaAndAssetCtxs")
                return {}
            
            meta = data[0]
            contexts = data[1]
            
            result = {}
            
            # Combine meta and context data
            for i, asset_meta in enumerate(meta.get("universe", [])):
                if i < len(contexts):
                    symbol = asset_meta.get("name")
                    if symbol:
                        ctx = contexts[i]
                        result[symbol] = {
                            "symbol": symbol,
                            "price": float(ctx.get("markPx", 0)),
                            "volume_24h": float(ctx.get("dayNtlVlm", 0)),
                            "volume_24h_base": float(ctx.get("dayBaseVlm", 0)),
                            "open_interest": float(ctx.get("openInterest", 0)),
                            "funding": float(ctx.get("funding", 0)),
                            "prev_day_px": float(ctx.get("prevDayPx", 0)),
                        }
            
            return result
    
    async def get_multiple_candles(self, symbols: List[str], interval: str = "1m", limit: int = 1) -> Dict[str, List[Dict]]:
        results = {}
        tasks = []
        
        async def fetch_candles(symbol):
            try:
                candles = await self.get_candles(symbol, interval, limit)
                return symbol, candles
            except Exception as e:
                logger.error(f"Error fetching candles for {symbol}: {e}")
                return symbol, []
        
        tasks = [fetch_candles(symbol) for symbol in symbols]
        responses = await asyncio.gather(*tasks)
        
        for symbol, candles in responses:
            results[symbol] = candles
        
        return results