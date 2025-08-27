#!/bin/bash
# Hyperliquid Anomaly Detection Bot - Run Script

echo "🚀 Starting Hyperliquid Anomaly Detection Bot..."
echo "================================================"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✅ Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy config/.env.example to .env and configure it."
    exit 1
fi

# Run the bot
echo "🤖 Starting bot..."
python main.py