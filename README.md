# Z-GUARD WEBサポートチャットボット - JSC全サイト＋ユーザーマニュアル版

回答根拠を次の2種類に限定した版です。

1. 株式会社JSC公式WEBサイト `https://www.jp-jsc.co.jp/` の同一ドメイン内ページ
2. `manuals/` に登録したZ-GUARDユーザーマニュアルPDF

## 仕組み

- 起動時にJSC公式サイトを同一ドメイン内でクロール
- 添付ユーザーマニュアルPDF本文を抽出
- 質問と直近の会話から関連箇所を検索
- 検索された資料だけをOpenAI APIへ渡して回答
- FAQ、製品ページ、オプション、トラブルシューティング、販売店情報、適合関連ページ等を横断参照

## Render設定

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Environment Variables:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna
```

## 初回起動

初回はJSCサイトを取得するため通常より時間がかかります。取得結果は `data/cache/website.json` に保存され、以後はキャッシュを使います。

## JSCサイトを最新状態へ更新

Render Shellまたはローカルで以下を実行します。

```bash
python refresh_knowledge.py
```

## 安全ルール

- 一般ユーザーにバッテリー端子脱着・配線・カプラー作業を指示しません。
- 販売店向けトラブルシューティングは、ユーザーへ直接作業させず「販売店で確認」と案内します。
- JSC公式サイトまたは登録マニュアルに根拠がないことは推測回答しません。
- 車種適合、販売店、アプリ更新など変化する情報はWEB情報を優先します。

## 既存サイトへの埋め込み

同一ドメインの場合:

```html
<script src="/zguard-widget.js"></script>
```

別ドメインにAPIを置く場合:

```html
<script src="https://YOUR-RENDER-URL.onrender.com/zguard-widget.js"
        data-api-base="https://YOUR-RENDER-URL.onrender.com"
        data-title="Z-GUARD サポート"></script>
```
