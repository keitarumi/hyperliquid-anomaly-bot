import numpy as np
from collections import deque
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(
        self, 
        window_size: int = 60,
        price_z_threshold: float = 3.0,
        volume_z_threshold: float = 3.0,
        min_samples: int = 30
    ):
        self.window_size = window_size
        self.price_z_threshold = price_z_threshold
        self.volume_z_threshold = volume_z_threshold
        self.min_samples = min_samples
        
        self.price_history = deque(maxlen=window_size)
        self.volume_history = deque(maxlen=window_size)
        
        self.last_normal_price = None
        self.last_normal_volume = None
        
    def add_data(self, price: float, volume: float) -> None:
        if len(self.price_history) >= self.min_samples:
            is_anomaly, _ = self.detect_anomaly(price, volume)
            if not is_anomaly:
                self.last_normal_price = price
                self.last_normal_volume = volume
        else:
            self.last_normal_price = price
            self.last_normal_volume = volume
            
        self.price_history.append(price)
        self.volume_history.append(volume)
    
    def detect_anomaly(self, current_price: float, current_volume: float) -> Tuple[bool, Dict[str, Any]]:
        if len(self.price_history) < self.min_samples:
            return False, {"reason": "Insufficient data"}
        
        price_mean = np.mean(self.price_history)
        price_std = np.std(self.price_history)
        volume_mean = np.mean(self.volume_history)
        volume_std = np.std(self.volume_history)
        
        price_z_score = 0 if price_std == 0 else abs((current_price - price_mean) / price_std)
        volume_z_score = 0 if volume_std == 0 else abs((current_volume - volume_mean) / volume_std)
        
        price_anomaly = price_z_score > self.price_z_threshold
        volume_anomaly = volume_z_score > self.volume_z_threshold
        
        is_anomaly = price_anomaly or volume_anomaly
        
        details = {
            "is_anomaly": is_anomaly,
            "price_z_score": round(price_z_score, 2),
            "volume_z_score": round(volume_z_score, 2),
            "price_anomaly": price_anomaly,
            "volume_anomaly": volume_anomaly,
            "current_price": current_price,
            "current_volume": current_volume,
            "price_mean": round(price_mean, 4),
            "price_std": round(price_std, 4),
            "volume_mean": round(volume_mean, 2),
            "volume_std": round(volume_std, 2),
            "last_normal_price": self.last_normal_price,
            "price_change_ratio": None
        }
        
        if self.last_normal_price and self.last_normal_price != 0:
            details["price_change_ratio"] = round(current_price / self.last_normal_price, 4)
        
        if is_anomaly:
            logger.info(f"Anomaly detected: {details}")
        
        return is_anomaly, details
    
    def get_target_price(self, multiplier: float = 3.0) -> Optional[float]:
        if self.last_normal_price is None:
            return None
        return self.last_normal_price * multiplier
    
    def reset(self) -> None:
        self.price_history.clear()
        self.volume_history.clear()
        self.last_normal_price = None
        self.last_normal_volume = None
    
    def get_statistics(self) -> Dict[str, Any]:
        if len(self.price_history) == 0:
            return {"status": "No data"}
        
        return {
            "samples": len(self.price_history),
            "price_mean": round(np.mean(self.price_history), 4) if self.price_history else None,
            "price_std": round(np.std(self.price_history), 4) if self.price_history else None,
            "volume_mean": round(np.mean(self.volume_history), 2) if self.volume_history else None,
            "volume_std": round(np.std(self.volume_history), 2) if self.volume_history else None,
            "last_normal_price": self.last_normal_price,
            "last_normal_volume": self.last_normal_volume
        }