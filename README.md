# Hyperliquid Anomaly Trading Bot

異常値検知に基づくHyperliquid自動取引ボット

## 機能

- Hyperliquid APIを使用したperp価格と出来高の10秒ごとの監視
- Z-scoreベースの異常値検知アルゴリズム
- 異常値検出時に前回正常価格の3倍で自動指値注文
- Discord webhookによるリアルタイム通知
- 10分後の自動注文キャンセル機能

## セットアップ

### 1. 必要なライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example`を`.env`にコピーして、必要な情報を入力してください：

```bash
cp .env.example .env
```

以下の項目を設定：
- `HYPERLIQUID_API_KEY`: Hyperliquid APIキー
- `HYPERLIQUID_API_SECRET`: Hyperliquid APIシークレット
- `HYPERLIQUID_WALLET_ADDRESS`: ウォレットアドレス
- `DISCORD_WEBHOOK_URL`: Discord通知用のWebhook URL

### 3. Discord Webhook設定

1. Discord サーバーの設定から「連携サービス」→「ウェブフック」を選択
2. 「新しいウェブフック」をクリック
3. 名前とチャンネルを設定
4. Webhook URLをコピーして`.env`ファイルに設定

## 実行方法

```bash
python trading_bot.py
```

## 設定パラメータ

### トレーディング設定
- `TRADING_SYMBOL`: 取引対象シンボル（デフォルト: BTC）
- `MONITORING_INTERVAL`: 市場監視間隔（秒）（デフォルト: 10）
- `ORDER_TIMEOUT`: 注文タイムアウト時間（秒）（デフォルト: 600）
- `PRICE_MULTIPLIER`: 指値価格の倍率（デフォルト: 3.0）
- `ORDER_SIZE`: 注文サイズ（デフォルト: 0.01）

### 異常値検知設定
- `DETECTOR_WINDOW_SIZE`: 統計計算用のウィンドウサイズ（デフォルト: 60）
- `PRICE_Z_THRESHOLD`: 価格異常値のZ-score閾値（デフォルト: 3.0）
- `VOLUME_Z_THRESHOLD`: 出来高異常値のZ-score閾値（デフォルト: 3.0）

## ファイル構成

- `trading_bot.py`: メインボットロジック
- `hyperliquid_client.py`: Hyperliquid APIクライアント
- `anomaly_detector.py`: 異常値検知アルゴリズム
- `discord_notifier.py`: Discord通知機能
- `requirements.txt`: 必要なライブラリ一覧
- `.env.example`: 環境変数のテンプレート

## 動作フロー

1. **監視フェーズ**: 10秒ごとに価格と出来高を取得
2. **異常値検知**: Z-scoreベースで価格/出来高の異常を検出
3. **注文発注**: 異常検出時、前回正常価格の3倍で指値注文
4. **通知**: Discord webhookで注文情報を通知
5. **タイムアウト管理**: 10分後に自動で注文キャンセル
6. **監視再開**: キャンセル後、監視フェーズに戻る

## 注意事項

- APIキーとシークレットは安全に管理してください
- 本番環境で使用する前に、テスト環境で十分に検証してください
- 市場の状況により損失が発生する可能性があります
- ログファイル（`trading_bot.log`）で詳細な動作を確認できます

## トラブルシューティング

### ボットが起動しない
- `.env`ファイルの設定を確認
- 必要なライブラリがインストールされているか確認

### Discord通知が届かない
- Webhook URLが正しいか確認
- Discordサーバーの権限設定を確認

### 注文が発注されない
- APIキーの権限を確認
- ウォレットの残高を確認
- ログファイルでエラー詳細を確認