"""
Price anomaly detection module using statistical methods
"""
import numpy as np
from collections import deque
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PriceAnomalyDetector:
    """
    Detects price anomalies using Z-score method
    """
    
    def __init__(self, window_size: int = 60, z_threshold: float = 3.0):
        """
        Initialize the price anomaly detector
        
        Args:
            window_size: Number of historical data points to keep
            z_threshold: Z-score threshold for anomaly detection
        """
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.price_history: Dict[str, deque] = {}
        
    def add_data(self, symbol: str, price: float):
        """
        Add price data for a symbol
        
        Args:
            symbol: Trading symbol
            price: Current price
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.window_size)
        
        self.price_history[symbol].append(price)
        
    def check_anomaly(self, symbol: str, current_price: float) -> bool:
        """
        Check if current price is an anomaly
        
        Args:
            symbol: Trading symbol
            current_price: Current price to check
            
        Returns:
            True if anomaly detected, False otherwise
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            # Not enough data
            self.add_data(symbol, current_price)
            return False
        
        prices = np.array(self.price_history[symbol])
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        
        if std_price == 0:
            # No variation in prices
            self.add_data(symbol, current_price)
            return False
        
        # Calculate Z-score
        z_score = abs((current_price - mean_price) / std_price)
        
        # Add current price to history
        self.add_data(symbol, current_price)
        
        # Check if anomaly
        is_anomaly = z_score > self.z_threshold
        
        if is_anomaly:
            logger.info(f"Price anomaly detected for {symbol}: "
                       f"Current=${current_price:.2f}, Mean=${mean_price:.2f}, "
                       f"Z-score={z_score:.2f}")
        
        return is_anomaly
    
    def get_last_normal_price(self, symbol: str) -> Optional[float]:
        """
        Get the last normal price before anomaly
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Last normal price or None if no history
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 2:
            return None
        
        # Return the second last price (before the anomaly)
        return self.price_history[symbol][-2]
    
    def get_statistics(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get price statistics for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with statistics or None if no data
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) == 0:
            return None
        
        prices = np.array(self.price_history[symbol])
        
        return {
            'mean': np.mean(prices),
            'std': np.std(prices),
            'min': np.min(prices),
            'max': np.max(prices),
            'count': len(prices)
        }
    
    def reset(self, symbol: Optional[str] = None):
        """
        Reset history for a symbol or all symbols
        
        Args:
            symbol: Trading symbol to reset, or None to reset all
        """
        if symbol:
            if symbol in self.price_history:
                self.price_history[symbol].clear()
        else:
            self.price_history.clear()