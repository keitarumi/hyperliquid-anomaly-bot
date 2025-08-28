#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock the exchange class to test just the rounding logic
class MockExchange:
    def get_price_decimals(self, symbol):
        # Fallback function
        return 4
    
    def get_tick_size(self, symbol: str, price: float) -> float:
        """Get tick size for a symbol based on typical patterns"""
        if symbol == 'BTC':
            return 1.0
        elif symbol == 'ETH':
            return 0.1
        elif symbol == 'SOL':
            return 0.01
        elif symbol in ['DOGE', 'PEPE', 'WIF', 'BONK', 'FLOKI']:
            return 0.00001
        elif symbol == 'ARK':
            return 0.00002
        else:
            if price >= 10000:
                return 1.0
            elif price >= 1000:
                return 0.1
            elif price >= 100:
                return 0.01
            elif price >= 10:
                return 0.001
            elif price >= 1:
                return 0.0001
            else:
                return 0.00001
    
    def round_price(self, price: float, symbol: str) -> float:
        """Round price to match tick size requirements"""
        try:
            tick_size = self.get_tick_size(symbol, price)
            
            if tick_size > 0:
                rounded = round(price / tick_size) * tick_size
                # Clean up floating point artifacts
                if tick_size >= 1:
                    rounded = round(rounded)
                elif tick_size >= 0.1:
                    rounded = round(rounded, 1)
                elif tick_size >= 0.01:
                    rounded = round(rounded, 2)
                elif tick_size >= 0.001:
                    rounded = round(rounded, 3)
                elif tick_size >= 0.0001:
                    rounded = round(rounded, 4)
                else:
                    rounded = round(rounded, 5)
                
                return rounded
            else:
                decimals = self.get_price_decimals(symbol)
                rounded = round(price, decimals)
                return rounded
        except Exception as e:
            return round(price, 4)

def test_tick_rounding():
    """Test tick size rounding"""
    
    exchange = MockExchange()
    
    test_cases = [
        # (symbol, input_price, expected_price)
        ('BTC', 112767.33, 112767),
        ('BTC', 112767.77, 112768),
        ('ETH', 4574.234, 4574.2),
        ('ETH', 4574.567, 4574.6),
        ('SOL', 213.994, 213.99),
        ('SOL', 213.996, 214.00),
        ('DOGE', 0.223456, 0.22346),
        ('ARK', 0.456789, 0.45678),
        ('WIF', 0.843216, 0.84322),
    ]
    
    print(f"{'Symbol':<8} {'Input Price':<15} {'Rounded Price':<15} {'Status'}")
    print("-" * 60)
    
    for symbol, input_price, expected in test_cases:
        rounded = exchange.round_price(input_price, symbol)
        status = "✓" if abs(rounded - expected) < 0.000001 else "✗"
        print(f"{symbol:<8} {input_price:<15.6f} {rounded:<15.6f} {status}")
        
        if status == "✗":
            print(f"         Expected: {expected:.6f}")

if __name__ == "__main__":
    test_tick_rounding()