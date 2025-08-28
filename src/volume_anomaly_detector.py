import numpy as np
from collections import defaultdict, deque
from typing import Dict, Any, List, Tuple, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class VolumeAnomalyDetector:
    """Detects volume and price anomalies across all symbols"""
    
    def __init__(
        self,
        window_size: int = 30,
        volume_z_threshold: float = 3.0,  # Volume Z-score threshold
        price_z_threshold: float = 3.0,  # Price Z-score threshold
        detection_mode: str = "vol_only",  # vol_only, price_only, vol_and_price, vol_or_price
        min_samples: int = 10,
        min_volume_usd: float = 1000  # Minimum volume to consider
    ):
        self.window_size = window_size
        self.volume_z_threshold = volume_z_threshold
        self.price_z_threshold = price_z_threshold
        self.detection_mode = detection_mode
        self.min_samples = min_samples
        self.min_volume_usd = min_volume_usd
        
        # Store historical data per symbol
        self.volume_history = defaultdict(lambda: deque(maxlen=window_size))
        self.price_history = defaultdict(lambda: deque(maxlen=window_size))
        
        # Track last known normal values
        self.last_normal_volume = {}
        self.last_normal_price = {}
        
    def update_data(self, symbol: str, price: float, volume: float):
        """Update historical data for a symbol"""
        # Always update history
        if not self.is_anomalous(symbol, price, volume):
            # If current data is not anomalous, update normal baseline
            if len(self.volume_history[symbol]) > self.min_samples:
                self.last_normal_volume[symbol] = volume
                self.last_normal_price[symbol] = price
            elif len(self.volume_history[symbol]) < self.min_samples:
                # Not enough data yet, consider it normal
                self.last_normal_volume[symbol] = volume
                self.last_normal_price[symbol] = price
            
            self.volume_history[symbol].append(volume)
            self.price_history[symbol].append(price)
    
    def detect_anomaly(self, symbol: str, current_price: float, current_volume: float) -> Tuple[bool, Dict[str, Any]]:
        """Detect if current volume and/or price is anomalous for a symbol"""
        
        volume_history = self.volume_history[symbol]
        price_history = self.price_history[symbol]
        
        if len(volume_history) < self.min_samples:
            return False, {"reason": "Insufficient data", "samples": len(volume_history)}
        
        # Calculate volume statistics
        volume_mean = np.mean(volume_history)
        volume_std = np.std(volume_history)
        
        # Calculate volume z-score
        if volume_std > 0:
            volume_z_score = (current_volume - volume_mean) / volume_std
        else:
            # When std is 0, all historical values are the same
            if current_volume != volume_mean and self.volume_z_threshold == 0:
                volume_z_score = 1.0  # Treat any difference as anomaly when threshold is 0
            else:
                volume_z_score = 0
        
        # Calculate price statistics
        price_mean = np.mean(price_history)
        price_std = np.std(price_history)
        
        # Calculate price z-score
        if price_std > 0:
            price_z_score = (current_price - price_mean) / price_std
        else:
            if current_price != price_mean and self.price_z_threshold == 0:
                price_z_score = 1.0
            else:
                price_z_score = 0
        
        # Detect anomaly based on detection mode
        volume_anomaly = abs(volume_z_score) >= self.volume_z_threshold if self.volume_z_threshold == 0 else abs(volume_z_score) > self.volume_z_threshold
        price_anomaly = abs(price_z_score) >= self.price_z_threshold if self.price_z_threshold == 0 else abs(price_z_score) > self.price_z_threshold
        
        if self.detection_mode == "vol_only":
            is_anomaly = volume_anomaly
        elif self.detection_mode == "price_only":
            is_anomaly = price_anomaly
        elif self.detection_mode == "vol_and_price":
            is_anomaly = volume_anomaly and price_anomaly
        elif self.detection_mode == "vol_or_price":
            is_anomaly = volume_anomaly or price_anomaly
        else:
            is_anomaly = volume_anomaly  # Default to volume only
        
        # Calculate percentage changes
        volume_change_pct = ((current_volume - volume_mean) / volume_mean * 100) if volume_mean > 0 else 0
        price_change_pct = ((current_price - price_mean) / price_mean * 100) if price_mean > 0 else 0
        
        # Determine anomaly type
        anomaly_type = "normal"
        if is_anomaly:
            if self.detection_mode == "vol_only":
                anomaly_type = "volume_spike" if volume_z_score > 0 else "volume_drop"
            elif self.detection_mode == "price_only":
                anomaly_type = "price_spike" if price_z_score > 0 else "price_drop"
            else:
                # Combined modes
                if volume_anomaly and price_anomaly:
                    anomaly_type = "vol_price_anomaly"
                elif volume_anomaly:
                    anomaly_type = "volume_anomaly"
                elif price_anomaly:
                    anomaly_type = "price_anomaly"
        
        details = {
            "is_anomaly": is_anomaly,
            "anomaly_type": anomaly_type,
            "symbol": symbol,
            "current_price": current_price,
            "current_volume": current_volume,
            "volume_mean": volume_mean,
            "volume_std": volume_std,
            "volume_z_score": volume_z_score,
            "volume_change_pct": volume_change_pct,
            "volume_anomaly": volume_anomaly,
            "price_mean": price_mean,
            "price_std": price_std,
            "price_z_score": price_z_score,
            "price_change_pct": price_change_pct,
            "price_anomaly": price_anomaly,
            "detection_mode": self.detection_mode,
            "volume_threshold": self.volume_z_threshold,
            "price_threshold": self.price_z_threshold,
            "samples": len(volume_history)
        }
        
        return is_anomaly, details
    
    def is_anomalous(self, symbol: str, price: float, volume: float) -> bool:
        """Quick check if data point is anomalous"""
        is_anomaly, _ = self.detect_anomaly(symbol, price, volume)
        return is_anomaly
    
    def scan_all_assets(self, asset_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scan all assets for volume and/or price anomalies"""
        anomalies = []
        
        for symbol, data in asset_data.items():
            price = data.get("price", 0)
            volume = data.get("volume_24h", 0)
            
            if price > 0 and volume >= self.min_volume_usd:
                # Detect anomaly based on existing history
                is_anomaly, details = self.detect_anomaly(symbol, price, volume)
                
                # Always update historical data after detection
                self.update_data(symbol, price, volume)
                
                if is_anomaly:
                    anomalies.append(details)
        
        # Sort by combined z-score magnitude
        anomalies.sort(key=lambda x: abs(x.get("volume_z_score", 0)) + abs(x.get("price_z_score", 0)), reverse=True)
        
        return anomalies
    
    def get_statistics(self, symbol: str) -> Dict[str, Any]:
        """Get statistics for a specific symbol"""
        volume_history = self.volume_history[symbol]
        price_history = self.price_history[symbol]
        
        if len(volume_history) < 2:
            return {"error": "Insufficient data"}
        
        return {
            "symbol": symbol,
            "samples": len(volume_history),
            "volume": {
                "mean": np.mean(volume_history),
                "std": np.std(volume_history),
                "min": min(volume_history),
                "max": max(volume_history),
                "current": volume_history[-1] if volume_history else 0
            },
            "price": {
                "mean": np.mean(price_history),
                "std": np.std(price_history),
                "min": min(price_history),
                "max": max(price_history),
                "current": price_history[-1] if price_history else 0
            }
        }
    
    def reset(self):
        """Reset all historical data"""
        self.volume_history.clear()
        self.price_history.clear()
        self.last_normal_volume.clear()
        self.last_normal_price.clear()
        logger.info("Detector reset - all historical data cleared")