import numpy as np
from collections import defaultdict, deque
from typing import Dict, Any, List, Tuple, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class VolumeAnomalyDetector:
    """Detects volume anomalies across all symbols"""
    
    def __init__(
        self,
        window_size: int = 30,
        volume_spike_threshold: float = 2.0,  # Volume spike as multiplier of mean
        volume_drop_threshold: float = 0.3,   # Volume drop as fraction of mean
        min_samples: int = 10,
        min_volume_usd: float = 1000  # Minimum volume to consider
    ):
        self.window_size = window_size
        self.volume_spike_threshold = volume_spike_threshold
        self.volume_drop_threshold = volume_drop_threshold
        self.min_samples = min_samples
        self.min_volume_usd = min_volume_usd
        
        # Store historical data per symbol
        self.volume_history = defaultdict(lambda: deque(maxlen=window_size))
        self.price_history = defaultdict(lambda: deque(maxlen=window_size))
        
        # Track last known normal values
        self.last_normal_volume = {}
        self.last_normal_price = {}
        
    def update_data(self, symbol: str, price: float, volume: float) -> None:
        """Update historical data for a symbol"""
        if volume >= self.min_volume_usd:
            # Check if this is normal before adding
            is_anomaly, _ = self.detect_anomaly(symbol, price, volume)
            
            if not is_anomaly and len(self.volume_history[symbol]) >= self.min_samples:
                self.last_normal_volume[symbol] = volume
                self.last_normal_price[symbol] = price
            elif len(self.volume_history[symbol]) < self.min_samples:
                # Not enough data yet, consider it normal
                self.last_normal_volume[symbol] = volume
                self.last_normal_price[symbol] = price
            
            self.volume_history[symbol].append(volume)
            self.price_history[symbol].append(price)
    
    def detect_anomaly(self, symbol: str, current_price: float, current_volume: float) -> Tuple[bool, Dict[str, Any]]:
        """Detect if current volume is anomalous for a symbol"""
        
        history = self.volume_history[symbol]
        
        if len(history) < self.min_samples:
            return False, {"reason": "Insufficient data", "samples": len(history)}
        
        # Calculate statistics
        volume_mean = np.mean(history)
        volume_std = np.std(history)
        
        # Detect spikes and drops
        is_spike = current_volume > volume_mean * self.volume_spike_threshold
        is_drop = current_volume < volume_mean * self.volume_drop_threshold
        
        # Calculate percentage change
        volume_change_pct = ((current_volume - volume_mean) / volume_mean * 100) if volume_mean > 0 else 0
        
        # Price change from last known normal
        price_change_pct = 0
        if symbol in self.last_normal_price and self.last_normal_price[symbol] > 0:
            price_change_pct = ((current_price - self.last_normal_price[symbol]) / self.last_normal_price[symbol] * 100)
        
        is_anomaly = is_spike or is_drop
        
        details = {
            "is_anomaly": is_anomaly,
            "anomaly_type": "spike" if is_spike else ("drop" if is_drop else "normal"),
            "symbol": symbol,
            "current_price": current_price,
            "current_volume": current_volume,
            "volume_mean": volume_mean,
            "volume_std": volume_std,
            "volume_change_pct": volume_change_pct,
            "price_change_pct": price_change_pct,
            "threshold_spike": volume_mean * self.volume_spike_threshold,
            "threshold_drop": volume_mean * self.volume_drop_threshold,
            "samples": len(history)
        }
        
        return is_anomaly, details
    
    def scan_all_assets(self, asset_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scan all assets for volume anomalies"""
        anomalies = []
        
        for symbol, data in asset_data.items():
            price = data.get("price", 0)
            volume = data.get("volume_24h", 0)
            
            if price > 0 and volume >= self.min_volume_usd:
                is_anomaly, details = self.detect_anomaly(symbol, price, volume)
                
                # Update historical data
                self.update_data(symbol, price, volume)
                
                if is_anomaly:
                    anomalies.append(details)
        
        # Sort by volume change percentage
        anomalies.sort(key=lambda x: abs(x["volume_change_pct"]), reverse=True)
        
        return anomalies
    
    def get_statistics(self, symbol: str) -> Dict[str, Any]:
        """Get statistics for a specific symbol"""
        history = self.volume_history.get(symbol, [])
        
        if len(history) == 0:
            return {"status": "No data", "symbol": symbol}
        
        return {
            "symbol": symbol,
            "samples": len(history),
            "volume_mean": np.mean(history) if history else 0,
            "volume_std": np.std(history) if history else 0,
            "volume_min": min(history) if history else 0,
            "volume_max": max(history) if history else 0,
            "last_normal_volume": self.last_normal_volume.get(symbol),
            "last_normal_price": self.last_normal_price.get(symbol)
        }
    
    def get_top_movers(self, asset_data: Dict[str, Dict[str, Any]], top_n: int = 10) -> Dict[str, List[Dict]]:
        """Get top volume movers (both increases and decreases)"""
        changes = []
        
        for symbol, data in asset_data.items():
            volume = data.get("volume_24h", 0)
            history = self.volume_history.get(symbol, [])
            
            if len(history) >= self.min_samples and volume >= self.min_volume_usd:
                volume_mean = np.mean(history)
                if volume_mean > 0:
                    change_pct = ((volume - volume_mean) / volume_mean * 100)
                    changes.append({
                        "symbol": symbol,
                        "price": data.get("price", 0),
                        "volume": volume,
                        "volume_mean": volume_mean,
                        "change_pct": change_pct
                    })
        
        # Sort by absolute change
        changes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        
        # Split into gainers and losers
        gainers = [c for c in changes if c["change_pct"] > 0][:top_n]
        losers = [c for c in changes if c["change_pct"] < 0][:top_n]
        
        return {
            "gainers": gainers,
            "losers": losers,
            "total_tracked": len(changes)
        }