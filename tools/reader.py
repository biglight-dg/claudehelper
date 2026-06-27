import io
import re
import requests
from bs4 import BeautifulSoup

from tools import storage

INBOX_REL = "inbox"


def read_pdf(source) -> str:
    """PDF에서 텍스트를 추출한다. source는 파일 경로 또는 bytes.

    텍스트 기반 PDF만 지원. 스캔 PDF(이미지 기반)는 OCR이 없어
    텍스트를 추출할 수 없으며 안내 메시지를 반환한다.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return "[PDF 읽기 실패: pypdf가 설치되지 않았습니다. pip install pypdf]"

    try:
        src = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source)
        reader = PdfReader(src)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- {i + 1}페이지 ---\n{text.strip()}")

        if not pages:
            return (
                "[스캔 PDF로 보입니다]\n"
                "이 파일은 이미지 기반 PDF라 텍스트를 자동으로 읽을 수 없습니다.\n"
                "내용을 직접 복사해서 '직접 메모' 탭에 붙여넣으시거나, "
                "텍스트 기반 PDF로 변환 후 다시 업로드해 주세요."
            )

        return "\n\n".join(pages)
    except Exception as e:
        return f"[PDF 읽기 실패: {e}]"


def read_inbox_files() -> list[dict]:
    """inbox 폴더의 txt, md, pdf 파일을 모두 읽어 반환(로컬 또는 드라이브)."""
    results = []
    for rel in storage.list_dir(INBOX_REL, (".txt", ".md", ".pdf")):
        name = rel.rsplit("/", 1)[-1]
        suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        try:
            if suffix in (".txt", ".md"):
                content = storage.read_text(rel) or ""
            elif suffix == ".pdf":
                content = read_pdf(storage.read_bytes(rel) or b"")
            else:
                continue
            results.append({"filename": name, "path": rel, "content": content})
        except Exception as e:
            results.append({"filename": name, "path": rel, "content": f"[읽기 실패: {e}]"})
    return results


def fetch_url(url: str) -> dict:
    """URL에서 본문 텍스트를 추출해 반환."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string.strip() if soup.title else url
        return {"title": title, "url": url, "content": text}
    except Exception as e:
        return {"title": url, "url": url, "content": f"[가져오기 실패: {e}]"}


def _normalize_youtube_url(url: str) -> str:
    """다양한 유튜브 링크 형태를 표준 watch URL로 정규화한다.

    지원: youtube.com/watch?v=, youtu.be/, youtube.com/shorts/, /embed/.
    영상 ID를 못 찾으면 원본 URL을 그대로 반환한다.
    """
    patterns = [
        r"(?:youtube\.com/watch\?(?:.*&)?v=)([\w-]{11})",
        r"(?:youtu\.be/)([\w-]{11})",
        r"(?:youtube\.com/shorts/)([\w-]{11})",
        r"(?:youtube\.com/embed/)([\w-]{11})",
        r"(?:youtube\.com/live/)([\w-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url


def fetch_youtube_meta(url: str) -> dict:
    """유튜브 링크에서 제목·설명·채널만 추출한다 (영상은 다운로드/시청하지 않음).

    API 키 없이 동작:
    - 제목·채널: oEmbed 엔드포인트(공식, 키 불필요)
    - 설명: watch 페이지의 og:description / meta description 태그

    반환: {"type": "youtube", "title", "description", "channel", "url"}
    어떤 단계가 실패해도 가능한 값만 채워 반환한다(최소한 제목=URL).
    """
    watch_url = _normalize_youtube_url(url)
    result = {"type": "youtube", "title": "", "description": "", "channel": "", "url": watch_url}
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1) oEmbed로 제목·채널
    try:
        oe = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": watch_url, "format": "json"},
            timeout=10, headers=headers,
        )
        if oe.ok:
            data = oe.json()
            result["title"] = (data.get("title") or "").strip()
            result["channel"] = (data.get("author_name") or "").strip()
    except Exception:
        pass

    # 2) watch 페이지에서 설명(og:description) + 제목 보강
    try:
        resp = requests.get(watch_url, timeout=10, headers=headers)
        if resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")
            og_desc = soup.find("meta", property="og:description")
            meta_desc = soup.find("meta", attrs={"name": "description"})
            desc = ""
            if og_desc and og_desc.get("content"):
                desc = og_desc["content"].strip()
            elif meta_desc and meta_desc.get("content"):
                desc = meta_desc["content"].strip()
            result["description"] = desc
            if not result["title"]:
                og_title = soup.find("meta", property="og:title")
                if og_title and og_title.get("content"):
                    result["title"] = og_title["content"].strip()
                elif soup.title and soup.title.string:
                    result["title"] = soup.title.string.replace(" - YouTube", "").strip()
    except Exception:
        pass

    if not result["title"]:
        result["title"] = watch_url
    return result


def save_to_inbox(filename: str, content: str) -> str:
    """텍스트를 inbox 에 저장하고 상대경로를 반환(로컬 또는 드라이브)."""
    safe = "".join(c if c.isalnum() or c in " ._-" else "_" for c in filename)
    name = safe if safe.endswith((".txt", ".md")) else safe + ".txt"
    relpath = f"{INBOX_REL}/{name}"
    storage.write_text(relpath, content)
    return relpath
