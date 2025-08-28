# テストスクリプト

このディレクトリには、ボットの動作確認用のテストスクリプトが含まれています。

## ファイル一覧

### 価格・数量精度チェック
- `check_precision.py` - 銘柄の価格精度チェック
- `check_price_precision.py` - オーダーブックから価格精度を推定
- `check_ark_full_metadata.py` - ARK銘柄の詳細メタデータ確認

### 丸め処理テスト
- `test_rounding_simple.py` - 価格・数量の丸め処理テスト（認証不要）
- `test_rounding.py` - 実際のExchangeクラスを使用したテスト（要認証）

## 使用方法

```bash
# 認証不要のテスト
python3 tests/test_rounding_simple.py

# 特定銘柄のメタデータ確認
python3 tests/check_ark_full_metadata.py
```

## 注意事項
- これらはデバッグ・動作確認用のスクリプトです
- 本番環境では使用しません
- `.env`ファイルの設定が必要な場合があります