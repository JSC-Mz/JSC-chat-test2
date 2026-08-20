import os
import re
from pathlib import Path
from typing import List, Dict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from knowledge_loader import load_all

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE: List[Dict] = load_all()

app = FastAPI(title="Z-GUARD Support Chat")

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


def tokenize_ja(text: str) -> set[str]:
    text = (text or "").lower()
    chunks = re.findall(r"[a-z0-9\-]+|[一-龠ぁ-んァ-ヶー]{2,}", text)
    terms = set(chunks)
    for chunk in chunks:
        if re.search(r"[一-龠ぁ-んァ-ヶー]", chunk):
            for n in (2, 3):
                if len(chunk) >= n:
                    terms.update(chunk[i:i+n] for i in range(len(chunk)-n+1))
    return terms


def retrieve(query: str, history: list[dict], top_k: int = 10) -> list[dict]:
    recent = " ".join(m.get("content", "") for m in history[-6:])
    full_query = f"{recent} {query}".strip()
    q = tokenize_ja(full_query)
    scored = []
    for item in KNOWLEDGE:
        blob = " ".join([item.get("source", ""), item.get("section", ""), item.get("content", "")])
        t = tokenize_ja(blob)
        score = len(q & t)
        for phrase in [
            "z-guardを探しています", "autoモード", "manualモード", "iphone", "android",
            "オプションリモコン", "cr2016", "bluetooth", "qrコード", "ペアリング",
            "バッテリー", "売却", "保証", "適合", "販売店", "アプリ"
        ]:
            if phrase in full_query.lower() and phrase in blob.lower():
                score += 10
        if item.get("kind") == "manual":
            score += 1
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]

SYSTEM_PROMPT = """あなたは株式会社JSCのZ-GUARDサポートチャットボットです。
回答根拠として使用してよい情報源は次の2種類だけです。
A. 株式会社JSC公式WEBサイト（jp-jsc.co.jp）から取得した情報
B. 管理者が登録したZ-GUARDのユーザーマニュアルPDF

重要ルール:
1. 上記資料にないことを一般知識で補って断定しない。
2. 資料間で内容が異なる場合は、勝手に統合せず違いを明示する。
3. トラブル対応は、最初から大量の手順を並べず、症状に応じて1〜2項目ずつ確認する。
4. 一般ユーザーが実施できる操作と、販売店・施工店で行う作業を明確に分ける。
5. バッテリー端子脱着、配線、カプラー、車両診断などの専門作業は一般ユーザーへ実施を指示しない。
6. WEB上の販売店向けトラブルシューティングを根拠にする場合は『取付販売店で確認してください』と案内する。
7. 回答できない場合は推測せず、取付販売店またはJSCへの問い合わせを案内する。
8. 日本語で一般ユーザー向けに簡潔で分かりやすく回答する。
9. 回答末尾に『参照：』として、使った資料名またはWEBページ名を簡潔に示す。
10. 車種適合・価格・販売店・アプリ更新情報などWEBで更新される情報は、取得したJSC公式WEB情報を優先して案内する。
"""

@app.post("/api/chat")
def chat(req: ChatRequest):
    hits = retrieve(req.message, req.history)
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        if not hits:
            answer = "JSC公式WEBサイトおよび登録済みユーザーマニュアルから該当情報を確認できませんでした。取付販売店またはJSCへお問い合わせください。"
        else:
            answer = "関連資料を確認しました。\n" + "\n".join(f"・{h['content'][:400]}（{h['source']}）" for h in hits[:3])
        return {"answer": answer, "sources": [{"source": h["source"], "section": h["section"], "url": h.get("url", "")} for h in hits[:4]], "mode": "fallback"}

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    context = "\n\n".join(
        f"[種別] {h.get('kind')}\n[資料] {h.get('source')}\n[URL] {h.get('url','')}\n[箇所] {h.get('section')}\n[内容] {h.get('content')}"
        for h in hits
    ) or "該当資料なし"

    history_text = "\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in req.history[-10:])
    user_input = f"""これまでの会話:
{history_text}

今回の質問:
{req.message}

検索されたJSC公式資料:
{context}

必ず上記資料だけを根拠に回答してください。"""

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        instructions=SYSTEM_PROMPT,
        input=user_input,
    )

    return {"answer": response.output_text, "sources": [{"source": h["source"], "section": h["section"], "url": h.get("url", "")} for h in hits[:5]], "mode": "openai"}

app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
