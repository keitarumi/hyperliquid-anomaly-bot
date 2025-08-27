# Hyperliquid Anomaly Detection Trading Bot

Hyperliquidの全perp銘柄を監視し、出来高や価格の異常を検知して自動取引を行うボットです。

## 機能

- 🔍 **リアルタイム監視**: 全perp銘柄の価格と出来高を10秒ごとに監視
- 📊 **異常検知**: 統計的手法による価格・出来高スパイクの検出
- 💰 **自動注文**: 異常検知時に異常前価格の3倍で指値注文（100 USDC）
- ⏰ **自動キャンセル**: 10分後に約定していない注文を自動キャンセル
- 💬 **Discord通知**: 異常検知と取引実行をDiscordに通知

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example`をコピーして`.env`を作成し、以下の情報を設定：

```bash
cp .env.example .env
```

`.env`ファイルの内容：
```
# Hyperliquid API credentials
HYPERLIQUID_PRIVATE_KEY=your_private_key_here
HYPERLIQUID_WALLET_ADDRESS=your_wallet_address_here

# Discord webhook for notifications
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here

# Trading configuration (optional)
TRADING_SYMBOL=BTC
MONITORING_INTERVAL=10
ORDER_TIMEOUT=600
```

### 3. Hyperliquid APIキーの取得

1. [Hyperliquid](https://app.hyperliquid.xyz)にアクセス
2. APIセクションでAPI Walletを作成
3. プライベートキーを`.env`に設定

**重要**: プライベートキーとウォレットアドレスは同じウォレットのものである必要があります。

## 実行方法

### ボットの起動
```bash
python volume_trading_bot.py
```

### 動作確認

```bash
# 注文機能のテスト（実際に注文を出します）
python test/test_exchange_client.py

# 異常検知のテスト
python test/test_anomaly_detector.py
```

## ファイル構成

```
hyper_adl/
├── volume_trading_bot.py      # メインの取引ボット
├── hyperliquid_client.py       # Hyperliquid API クライアント（情報取得用）
├── hyperliquid_exchange.py     # Hyperliquid取引クライアント（注文実行用）
├── volume_anomaly_detector.py  # 出来高異常検知
├── price_anomaly_detector.py   # 価格異常検知
├── discord_notifier.py         # Discord通知
├── test/                        # テストスクリプト
├── requirements.txt            # 依存関係
├── .env.example               # 環境変数テンプレート
└── README.md                  # このファイル
```

## 設定パラメータ

### 異常検知の閾値

`volume_anomaly_detector.py`で調整可能：
- `spike_threshold`: 出来高スパイクの閾値（デフォルト: 2.0 = 200%）
- `drop_threshold`: 出来高急落の閾値（デフォルト: 0.5 = 50%）
- `history_window`: 履歴保持期間（デフォルト: 100）

### 取引パラメータ

`volume_trading_bot.py`で調整可能：
- `price_multiplier`: 異常前価格の倍率（デフォルト: 3.0）
- `order_amount_usdc`: 注文金額（デフォルト: 100 USDC）
- `cancel_after_seconds`: 自動キャンセルまでの時間（デフォルト: 600秒）

## 注意事項

- **リアルマネー**: このボットは実際の資金で取引を行います
- **リスク管理**: 適切な資金管理とリスク設定を行ってください
- **API制限**: Hyperliquidのレート制限に注意してください
- **監視**: ボットの動作を定期的に確認してください

## トラブルシューティング

### "Order has invalid price" エラー
- ウォレットに十分な資金があるか確認
- 価格のtick sizeが正しいか確認（BTCは$1単位）

### "Account value: $0" エラー
- プライベートキーとウォレットアドレスが一致しているか確認
- Hyperliquidに資金が入金されているか確認

### 認証エラー
- プライベートキーが正しいフォーマットか確認（0xで始まる66文字）
- API Walletが有効化されているか確認

## ライセンス

MIT