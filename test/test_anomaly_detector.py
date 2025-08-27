"""
Test script for anomaly detection functionality
"""
import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volume_anomaly_detector import VolumeAnomalyDetector
from price_anomaly_detector import PriceAnomalyDetector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_volume_anomaly():
    """Test volume anomaly detection"""
    detector = VolumeAnomalyDetector(
        spike_threshold=2.0,  # 200% spike
        drop_threshold=0.5,   # 50% drop
        history_window=10
    )
    
    logger.info("Testing Volume Anomaly Detection")
    logger.info("=" * 50)
    
    # Add normal data
    symbol = "TEST"
    for i in range(10):
        detector.add_data(symbol, 1000.0 + i * 10)
        logger.info(f"Added volume: {1000.0 + i * 10:.2f}")
    
    # Test spike detection
    spike_volume = 3000.0
    is_anomaly, anomaly_type = detector.check_anomaly(symbol, spike_volume)
    logger.info(f"\nSpike test - Volume: {spike_volume}, Anomaly: {is_anomaly}, Type: {anomaly_type}")
    
    # Test drop detection
    drop_volume = 200.0
    is_anomaly, anomaly_type = detector.check_anomaly(symbol, drop_volume)
    logger.info(f"Drop test - Volume: {drop_volume}, Anomaly: {is_anomaly}, Type: {anomaly_type}")
    
    # Test normal
    normal_volume = 1100.0
    is_anomaly, anomaly_type = detector.check_anomaly(symbol, normal_volume)
    logger.info(f"Normal test - Volume: {normal_volume}, Anomaly: {is_anomaly}, Type: {anomaly_type}")


async def test_price_anomaly():
    """Test price anomaly detection"""
    detector = PriceAnomalyDetector()
    
    logger.info("\n" + "=" * 50)
    logger.info("Testing Price Anomaly Detection")
    logger.info("=" * 50)
    
    # Add normal price data
    symbol = "TEST"
    base_price = 100.0
    
    for i in range(30):
        price = base_price + (i % 5) - 2  # Small variations
        detector.add_data(symbol, price)
    
    logger.info(f"Added 30 normal prices around ${base_price}")
    
    # Test normal price
    normal_price = base_price + 1
    is_anomaly = detector.check_anomaly(symbol, normal_price)
    logger.info(f"\nNormal test - Price: ${normal_price}, Anomaly: {is_anomaly}")
    
    # Test price spike
    spike_price = base_price * 1.5
    is_anomaly = detector.check_anomaly(symbol, spike_price)
    logger.info(f"Spike test - Price: ${spike_price}, Anomaly: {is_anomaly}")
    
    # Test price drop
    drop_price = base_price * 0.5
    is_anomaly = detector.check_anomaly(symbol, drop_price)
    logger.info(f"Drop test - Price: ${drop_price}, Anomaly: {is_anomaly}")
    
    # Get statistics
    stats = detector.get_statistics(symbol)
    if stats:
        logger.info(f"\nStatistics for {symbol}:")
        logger.info(f"  Mean: ${stats['mean']:.2f}")
        logger.info(f"  Std Dev: ${stats['std']:.2f}")
        logger.info(f"  Min: ${stats['min']:.2f}")
        logger.info(f"  Max: ${stats['max']:.2f}")


async def main():
    """Run all anomaly detection tests"""
    await test_volume_anomaly()
    await test_price_anomaly()
    
    logger.info("\n" + "=" * 50)
    logger.info("All tests completed!")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())