import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
WEB_CACHE = CACHE_DIR / "website.json"
MANUAL_CACHE = CACHE_DIR / "manuals.json"

START_URL = "https://www.jp-jsc.co.jp/"
DOMAIN = "www.jp-jsc.co.jp"
MAX_PAGES = 250
SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip", ".mp4", ".mov", ".css", ".js", ".ico", ".woff", ".woff2", ".ttf"}
SKIP_PATH_PARTS = ("/wp-admin/", "/wp-login", "/feed/", "/tag/", "/author/")


def clean_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 180):
    text = clean_text(text)
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 <= max_chars:
            cur = (cur + "\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
            if len(p) <= max_chars:
                cur = p
            else:
                start = 0
                while start < len(p):
                    end = start + max_chars
                    chunks.append(p[start:end])
                    start = max(0, end - overlap)
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def allowed_url(url: str) -> bool:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or u.netloc != DOMAIN:
        return False
    path = u.path.lower()
    if any(part in path for part in SKIP_PATH_PARTS):
        return False
    if Path(path).suffix in SKIP_EXT:
        return False
    return True


def crawl_site(force: bool = False):
    if WEB_CACHE.exists() and not force:
        return json.loads(WEB_CACHE.read_text(encoding="utf-8"))

    session = requests.Session()
    session.headers.update({"User-Agent": "JSC-ZGUARD-SupportBot/1.0 (+https://www.jp-jsc.co.jp/)"})
    queue = [START_URL]
    seen = set()
    docs = []

    while queue and len(seen) < MAX_PAGES:
        url = urldefrag(queue.pop(0))[0]
        if url in seen or not allowed_url(url):
            continue
        seen.add(url)
        try:
            r = session.get(url, timeout=20)
            if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else url)
            main = soup.find("main") or soup.find("article") or soup.body
            text = clean_text(main.get_text("\n", strip=True) if main else "")
            for i, chunk in enumerate(chunk_text(text)):
                docs.append({
                    "id": f"web-{hashlib.sha1((url+str(i)).encode()).hexdigest()[:14]}",
                    "kind": "website",
                    "source": title,
                    "url": url,
                    "section": f"Web page chunk {i+1}",
                    "content": chunk,
                })
            for a in soup.find_all("a", href=True):
                nxt = urldefrag(urljoin(url, a["href"]))[0]
                if allowed_url(nxt) and nxt not in seen:
                    queue.append(nxt)
        except Exception:
            continue

    WEB_CACHE.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    return docs


def load_manuals(force: bool = False):
    if MANUAL_CACHE.exists() and not force:
        return json.loads(MANUAL_CACHE.read_text(encoding="utf-8"))

    docs = []
    manuals_dir = BASE_DIR / "manuals"
    for pdf in sorted(manuals_dir.glob("*.pdf")):
        try:
            reader = PdfReader(str(pdf))
            for pno, page in enumerate(reader.pages, start=1):
                text = clean_text(page.extract_text() or "")
                for i, chunk in enumerate(chunk_text(text)):
                    docs.append({
                        "id": f"pdf-{hashlib.sha1((pdf.name+str(pno)+str(i)).encode()).hexdigest()[:14]}",
                        "kind": "manual",
                        "source": pdf.name,
                        "url": "",
                        "section": f"PDF page {pno} / chunk {i+1}",
                        "content": chunk,
                    })
        except Exception:
            continue

    MANUAL_CACHE.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    return docs


def load_all(force_web: bool = False, force_manuals: bool = False):
    return crawl_site(force=force_web) + load_manuals(force=force_manuals)
