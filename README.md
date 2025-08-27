# Hyperliquid Anomaly Detection Trading Bot

Hyperliquid永続先物の価格・出来高異常を検知し、自動トレードを実行するボット

## 機能

- 🔍 **リアルタイム監視**: 設定した銘柄を定期的に監視（全銘柄対応可）
- 📊 **Z-score異常検知**: 出来高の統計的異常をZ-scoreで検知（デフォルト: 3標準偏差）
- 💰 **自動注文実行**: 異常検知前の価格に対して指定倍率で指値注文を発注
- 📈 **ポジション管理**:
  - 未約定注文は設定時間後に自動キャンセル（デフォルト10分）
  - 保有ポジションは設定時間後に自動でマーケットクローズ（デフォルト30分）
  - 同時保有は1ポジションまでに制限（注文中・ポジション保有中は新規注文をブロック）
- 💬 **Discord通知**: 異常検知、注文、キャンセル、ポジションクローズを即座に通知

## セットアップ

### 1. 環境構築

```bash
# リポジトリをクローン
git clone https://github.com/keitarumi/hyper_adl.git
cd hyper_adl

# 依存関係をインストール
pip install -r requirements.txt
```

### 2. 環境変数の設定

`config/.env.example` を `.env` にコピーして編集：

```bash
cp config/.env.example .env
vi .env  # お好みのエディタで編集
```

```env
# Hyperliquid API credentials
HYPERLIQUID_PRIVATE_KEY=0x...  # APIウォレットの秘密鍵
HYPERLIQUID_API_WALLET_ADDRESS=0x...  # APIウォレットアドレス
HYPERLIQUID_MAIN_WALLET_ADDRESS=0x...  # メインウォレットアドレス（資金があるウォレット）

# Discord webhook for notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Trading configuration
MONITORING_INTERVAL=10  # 監視間隔（秒）
ORDER_TIMEOUT=600  # 注文タイムアウト（秒）- デフォルト10分
POSITION_CLOSE_TIMEOUT=1800  # ポジションクローズ（秒）- デフォルト30分
PRICE_MULTIPLIER=3.0  # 価格倍率
ORDER_AMOUNT_USDC=100  # 注文サイズ（USDC）
MAX_CONCURRENT_ORDERS=1  # 最大同時注文数
SYMBOLS=  # 監視銘柄（カンマ区切り、空=全銘柄）

# Anomaly detection parameters
DETECTOR_WINDOW_SIZE=60  # 検知ウィンドウサイズ
VOLUME_Z_THRESHOLD=3.0  # ボリューム異常検知のZ-score閾値（3.0 = 3標準偏差）
```

### 3. Hyperliquid APIウォレット設定

1. **APIウォレット作成**: https://app.hyperliquid.xyz/API
   - 「Generate API Wallet」をクリック
   - 秘密鍵をコピー（重要: 安全に保管）
   - ウォレットアドレスをメモ

2. **環境変数に設定**:
   - `HYPERLIQUID_PRIVATE_KEY`: APIウォレットの秘密鍵
   - `HYPERLIQUID_API_WALLET_ADDRESS`: APIウォレットのアドレス
   - `HYPERLIQUID_MAIN_WALLET_ADDRESS`: メインウォレット（資金がある）のアドレス

## 使用方法

### ボットの起動

```bash
# 実行権限を付与（初回のみ）
chmod +x run.sh

# 起動スクリプトで実行
./run.sh

# または直接実行
python main.py
```

## ファイル構成

```
hyper_adl/
├── main.py                    # メインボット実行ファイル
├── run.sh                     # 起動スクリプト
├── requirements.txt           # 依存パッケージ
├── .env                       # 環境変数（gitignore対象）
├── config/
│   └── .env.example          # 環境変数テンプレート
└── src/                       # ソースコード
    ├── __init__.py
    ├── hyperliquid_exchange.py    # 取引所API (注文実行)
    ├── hyperliquid_client.py      # 取引所API (データ取得)
    ├── volume_anomaly_detector.py # ボリューム異常検知
    └── discord_notifier.py        # Discord通知
```

## 動作フロー

1. **初期化**: APIウォレットとメインウォレットの接続確認
2. **監視ループ** (設定間隔ごと):
   - 設定銘柄の価格・ボリュームデータを取得
   - Z-scoreベースで統計的異常を検知
   - 異常検知時:
     - 異常検知前の価格 × 設定倍率で指値注文
     - ORDER_AMOUNT_USDC相当の数量を計算
     - Discord通知送信
3. **注文・ポジション管理**:
   - 未約定注文: 10分（デフォルト）経過後に自動キャンセル
   - 約定済みポジション: 30分（デフォルト）経過後に自動マーケットクローズ
   - 注文中・ポジション保有中は新規注文をブロック
   - 全イベントでDiscord通知

## パラメータ説明

### トレード設定
| パラメータ | デフォルト値 | 説明 |
|----------|------------|------|
| MONITORING_INTERVAL | 10秒 | 市場監視の間隔 |
| ORDER_TIMEOUT | 600秒（10分） | 未約定注文の自動キャンセルまでの時間 |
| POSITION_CLOSE_TIMEOUT | 1800秒（30分） | ポジション自動クローズまでの時間 |
| PRICE_MULTIPLIER | 3.0 | 異常検知前価格に対する注文価格倍率 |
| ORDER_AMOUNT_USDC | 100 | 各注文のサイズ（USDC建て） |
| MAX_CONCURRENT_ORDERS | 1 | 同時注文数の上限（1=同時に1つのみ） |
| SYMBOLS | (空) | 監視銘柄（カンマ区切り、空=全銘柄） |

### 異常検知設定
| パラメータ | デフォルト値 | 説明 |
|----------|------------|------|
| DETECTOR_WINDOW_SIZE | 60 | 異常検知の履歴ウィンドウサイズ（サンプル数） |
| VOLUME_Z_THRESHOLD | 3.0 | 出来高異常のZ-score閾値（3.0 = 3標準偏差） |

## エラー通知

ボットは以下のエラーを検知してDiscordに通知します：

- 💀 **Fatal Error**: 致命的エラー（ボット停止）
- ❌ **Order Error**: 注文失敗
- ❌ **Market Data Error**: データ取得エラー
- ❌ **Anomaly Detection Error**: 異常検知エラー
- ⚠️ **Warning**: 残高不足などの警告
- 🛑 **Bot Stopped**: ボット停止通知

## トラブルシューティング

| 問題 | 解決方法 |
|-----|---------|
| `Missing required environment variables` | `.env`ファイルの設定を確認 |
| `Order price cannot be more than 95% away` | APIウォレットの認証を確認 |
| `No market data received` | ネットワーク接続を確認 |
| `Low account balance` | メインウォレットに資金を追加 |

## 注意事項

- APIウォレットは署名専用（資金は不要）
- メインウォレットに取引資金が必要
- 本番環境では十分なテスト後に使用すること
- 秘密鍵は絶対に公開しないこと
