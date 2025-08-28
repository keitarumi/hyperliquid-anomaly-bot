# Hyperliquid Anomaly Detection Trading Bot

Hyperliquid永続先物の価格・出来高異常を検知し、自動トレードを実行するボット

## 機能

- 🔍 **リアルタイム監視**: 設定した銘柄を定期的に監視（全銘柄対応可）
- 📊 **異常検知**: 出来高と価格の統計的異常をZ-scoreで検知
- 💰 **複数注文対応**: 異常検知時に複数の価格レベルで指値注文を発注
- 📈 **ポジション管理**:
  - 未約定注文は設定時間後に自動キャンセル
  - 保有ポジションは設定時間後に自動でマーケットクローズ
  - 同時保有は設定数まで制限可能
- 💬 **Discord通知**: 異常検知、注文、キャンセル、ポジションクローズを即座に通知

## セットアップ

### 1. 環境構築

```bash
# リポジトリをクローン
git clone https://github.com/keitarumi/hyperliquid-anomaly-bot.git
cd hyperliquid-anomaly-bot

# 依存関係をインストール
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーして編集：

```bash
cp .env.example .env
vi .env  # お好みのエディタで編集
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

## 📋 パラメータ詳細解説

### 🔑 必須設定（API認証）

| パラメータ | 説明 | 例 |
|----------|------|-----|
| `HYPERLIQUID_PRIVATE_KEY` | APIウォレットの秘密鍵<br>・Hyperliquidで生成したAPI専用ウォレットの秘密鍵<br>・`0x`で始まる64文字の16進数文字列<br>・**絶対に他人と共有しない** | `0x1234...abcd` |
| `HYPERLIQUID_API_WALLET_ADDRESS` | APIウォレットのアドレス<br>・秘密鍵に対応するウォレットアドレス<br>・注文の署名に使用 | `0xAbC...123` |
| `HYPERLIQUID_MAIN_WALLET_ADDRESS` | メインウォレットアドレス<br>・実際の資金が入っているウォレット<br>・APIウォレットから参照される | `0xDeF...456` |
| `DISCORD_WEBHOOK_URL` | Discord通知用のWebhook URL<br>・Discord設定から生成<br>・異常検知や注文状況を通知 | `https://discord.com/api/webhooks/...` |

### 💰 トレード設定

| パラメータ | デフォルト値 | 説明 | 使用例 |
|----------|------------|------|--------|
| `MONITORING_INTERVAL` | 10秒 | 市場データの取得間隔<br>・短すぎるとAPI制限に注意<br>・長すぎると異常検知が遅れる | `5` = 5秒ごとに監視 |
| `ORDER_TIMEOUT` | 600秒<br>(10分) | 未約定注文の自動キャンセル時間<br>・指値が約定しない場合の撤退時間<br>・市場の流動性に応じて調整 | `120` = 2分でキャンセル |
| `POSITION_CLOSE_TIMEOUT` | 1800秒<br>(30分) | ポジション自動クローズ時間<br>・異常検知からの経過時間<br>・短期取引向けの安全装置 | `300` = 5分でクローズ |
| `PRICE_MULTIPLIERS` | 3.0 | **複数注文の価格倍率**（カンマ区切り）<br>・異常検知前価格に対する倍率<br>・`> 1.0` = 売り注文（ショート）<br>・`< 1.0` = 買い注文（ロング）<br>・複数指定で段階的な注文 | `1.5,2.0,3.0` = 3段階の売り注文<br>`0.95,0.9,0.85` = 3段階の買い注文 |
| `ORDER_AMOUNTS_USDC` | 100 | **各注文のサイズ**（USDC建て、カンマ区切り）<br>・PRICE_MULTIPLIERSと同じ数だけ指定<br>・注文ごとに異なる金額設定可能 | `1000,500,500` = 合計2000 USDC<br>1つ目1000、2-3つ目各500 |
| `MAX_CONCURRENT_ORDERS` | 1 | 同時に保有できる銘柄数の上限<br>・リスク管理のための制限<br>・1 = 1銘柄のみ（安全）<br>・複数 = 分散投資 | `3` = 最大3銘柄同時保有 |

### 🎯 銘柄フィルター

| パラメータ | デフォルト値 | 説明 | 使用例 |
|----------|------------|------|--------|
| `SYMBOLS` | (空) | 監視する銘柄リスト<br>・カンマ区切りで複数指定<br>・空欄 = 全銘柄監視（200+銘柄）<br>・メジャー銘柄のみ推奨 | `BTC,ETH,SOL`<br>`DOGE,PEPE,WIF` |

### 📊 異常検知パラメータ

| パラメータ | デフォルト値 | 説明 | 推奨設定 |
|----------|------------|------|---------|
| `DETECTOR_WINDOW_SIZE` | 60 | 統計計算用の履歴サンプル数<br>・各銘柄ごとに保持<br>・大きいほど安定、小さいほど敏感 | `30` = 短期的な変化に敏感<br>`120` = より安定した検知 |
| `VOLUME_Z_THRESHOLD` | 3.0 | **出来高異常のZ-score閾値**<br>・標準偏差の倍数<br>・`0` = すべての変化を検知<br>・`3` = 99.7%の確率で異常 | `0` = 最も敏感<br>`2` = 95%信頼区間外<br>`3` = 99.7%信頼区間外 |
| `PRICE_Z_THRESHOLD` | 3.0 | **価格異常のZ-score閾値**<br>・標準偏差の倍数<br>・価格の急変を検知 | `2` = 価格2σ異常<br>`3` = 価格3σ異常 |
| `DETECTION_MODE` | vol_only | **検知モード**<br>・`vol_only` = 出来高のみ<br>・`price_only` = 価格のみ<br>・`vol_and_price` = 両方必要<br>・`vol_or_price` = どちらか一方 | `vol_or_price` = 出来高または価格の異常<br>`vol_and_price` = 両方同時の場合のみ |

## 🎮 使用方法

### ボットの起動

```bash
python main.py
```

### 設定例

#### 例1: 保守的な設定（初心者向け）
```env
MONITORING_INTERVAL=10
PRICE_MULTIPLIERS=2.0
ORDER_AMOUNTS_USDC=100
VOLUME_Z_THRESHOLD=3.0
DETECTION_MODE=vol_only
SYMBOLS=BTC,ETH,SOL
```
- 主要銘柄のみ監視
- 出来高3σ異常のみ検知
- 2倍の価格で100 USDCの売り注文1つ

#### 例2: 積極的な設定（上級者向け）
```env
MONITORING_INTERVAL=5
PRICE_MULTIPLIERS=1.2,1.5,2.0
ORDER_AMOUNTS_USDC=500,300,200
VOLUME_Z_THRESHOLD=2.0
PRICE_Z_THRESHOLD=2.0
DETECTION_MODE=vol_or_price
SYMBOLS=
```
- 全銘柄監視
- 出来高または価格の2σ異常を検知
- 3段階の売り注文（合計1000 USDC）

#### 例3: 下落狙いの買い設定
```env
PRICE_MULTIPLIERS=0.95,0.9,0.85
ORDER_AMOUNTS_USDC=300,300,400
DETECTION_MODE=price_only
PRICE_Z_THRESHOLD=2.5
```
- 価格異常のみ監視
- 価格下落時に買い注文
- 0.95倍、0.9倍、0.85倍で段階的に買い

## 📈 動作フロー

### 1. 初期化フェーズ
- APIウォレット接続確認
- Discord Webhook接続テスト
- パラメータ検証（倍率と金額の数が一致するか等）

### 2. データ収集フェーズ（最初の約50秒）
- 各銘柄の履歴データを蓄積
- 最低10サンプル必要（`MONITORING_INTERVAL` × 10）
- この間は異常検知されない

### 3. 監視・検知フェーズ
```
[5秒ごと] → データ取得 → Z-score計算 → 異常判定
                ↓                           ↓
            履歴更新                    異常あり
                                           ↓
                                      複数注文発注
```

### 4. 注文管理
- **複数価格での同時発注**: 設定した倍率ごとに注文
- **個別管理**: 各注文は独立してタイムアウト管理
- **自動キャンセル**: ORDER_TIMEOUT後に未約定注文をキャンセル

### 5. ポジション管理
- **自動クローズ**: POSITION_CLOSE_TIMEOUT後にマーケット注文で決済
- **損益通知**: クローズ時にPnLをDiscordに通知

## 🔧 価格・数量の処理ロジック

### 価格の丸め処理
- **方式**: APIから取得した現在価格の小数点桁数を検出し、同じ精度で丸め
- **例**: 
  - ARK: API価格 $0.5573 → 4桁精度
  - BTC: API価格 $112939.5 → 1桁精度
  - SOL: API価格 $211.26 → 2桁精度

### 数量（サイズ）の切り捨て処理
- **方式**: Hyperliquidメタデータの`szDecimals`に従って切り捨て
- **例**:
  - ARK: szDecimals=0 → 181.198 → 181（整数）
  - BTC: szDecimals=5 → 0.000897 → 0.00089
  - SOL: szDecimals=2 → 0.487 → 0.48

## 🚨 エラーとトラブルシューティング

### よくあるエラー

| エラーメッセージ | 原因 | 解決方法 |
|---------------|------|---------|
| `Configuration error: Price multipliers count does not match` | 倍率と金額の数が不一致 | PRICE_MULTIPLIERSとORDER_AMOUNTS_USDCの要素数を合わせる |
| `Post only order would have immediately matched` | 指値価格が現在価格と交差 | 倍率を調整するか、post_onlyを無効化 |
| `Missing required environment variables` | 必須設定が不足 | .envファイルの必須項目を確認 |
| `No market data received` | API接続エラー | ネットワーク接続とAPI状態を確認 |
| `Low account balance` | 残高不足 | メインウォレットに資金を追加 |

### デバッグ方法

1. **ログファイル確認**
```bash
tail -f trading_bot_*.log
```

2. **テストスクリプト実行**
```bash
# SOLのデータ取得テスト
python analyze_sol.py

# 異常検知テスト
python test_detection.py
```

## ⚠️ 重要な注意事項

### リスクに関する警告
- **投資リスク**: 暗号資産取引は高リスクであり、投資元本の全額を失う可能性があります
- **技術的リスク**: ボットの不具合により予期しない損失が発生する可能性があります
- **市場リスク**: 急激な価格変動により想定外の損失が発生する可能性があります

### セキュリティ
- 秘密鍵は絶対に他人と共有しない
- .envファイルは絶対にGitにコミットしない
- APIウォレットには必要最小限の資金のみを入れる
- 定期的にログを確認し、異常な動作がないか監視する

### 免責事項
本ソフトウェアは「現状のまま」提供され、いかなる保証もありません。使用は自己責任で行ってください。