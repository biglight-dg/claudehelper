"""뉴스 스트림 — 구독 RSS를 모아 기록하고, 주간 브리핑으로 정리한다.

inbox(정리 대상 문서)와 분리된 '흘러가는 뉴스' 저장소다.
  - 수집: collect_news()  (앱 열 때 하루 1회 자동 + 버튼/명령)
  - 열람: 앱 '📰 최근 뉴스' 탭
  - 정리: 팀장(Claude Code)이 "이번 주 뉴스 정리해줘"로 build_digest_source()를
          읽고 브리핑을 작성 → save_digest()로 지식 문서 + 뉴스 탭에 등록

저장소: data/news.json (data는 Google 공유 드라이브 정션)
RSS 워치리스트·파싱은 tools/sources.py를 재사용한다(새 API 키 없음).
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from tools.sources import load_sources, fetch_rss
from tools.file_tools import save_knowledge_file

NEWS_FILE = Path(__file__).parent.parent / "data" / "news.json"


# ── 저장소 ────────────────────────────────────────────────────────

def load_news() -> dict:
    """data/news.json 로드. 없으면 빈 구조 반환."""
    if not NEWS_FILE.exists():
        return {"last_collected": "", "items": [], "digests": []}
    with open(NEWS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("last_collected", "")
    data.setdefault("items", [])
    data.setdefault("digests", [])
    return data


def save_news(data: dict) -> None:
    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _item_id(guid: str, link: str) -> str:
    """guid(없으면 link)로 안정적인 짧은 id를 만든다."""
    key = (guid or link or "").strip()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ── 수집 ──────────────────────────────────────────────────────────

def collect_news(limit_each: int = 8) -> int:
    """구독 RSS 전체에서 신규 항목만 news.json에 기록한다.

    news.json 자체의 id 집합으로 중복을 판정한다(입력 흐름의 sources `seen`·inbox와 독립).
    반환: 새로 추가한 항목 수.
    """
    data = load_news()
    known = {it["id"] for it in data["items"]}
    now = datetime.now().isoformat(timespec="seconds")
    added = 0
    for feed in load_sources()["rss"]:
        for entry in fetch_rss(feed["url"], limit=limit_each):
            iid = _item_id(entry.get("guid", ""), entry.get("link", ""))
            if iid in known or not (entry.get("title") or "").strip():
                continue
            data["items"].append({
                "id": iid,
                "title": entry["title"],
                "source": feed.get("title") or feed["url"],
                "category": feed.get("category", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "collected_at": now,
                "in_digest": False,
            })
            known.add(iid)
            added += 1
    data["last_collected"] = datetime.now().strftime("%Y-%m-%d")
    save_news(data)
    return added


def collect_news_daily() -> int | None:
    """그날 첫 호출이면 수집하고 건수를 반환, 이미 오늘 수집했으면 None.

    앱 열 때 하루 1회 자동 수집용.
    """
    data = load_news()
    if data.get("last_collected") == datetime.now().strftime("%Y-%m-%d"):
        return None
    return collect_news()


# ── 열람 ──────────────────────────────────────────────────────────

def _within_days(iso_ts: str, days: int) -> bool:
    try:
        ts = datetime.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return True  # 시각 파싱 실패 시 일단 포함
    return ts >= datetime.now() - timedelta(days=days)


def recent_items(days: int = 7, source: str | None = None) -> list[dict]:
    """collected_at 기준 최근 N일 항목을 최신순으로 반환."""
    items = [
        it for it in load_news()["items"]
        if _within_days(it.get("collected_at", ""), days)
        and (source is None or it.get("source") == source)
    ]
    return sorted(items, key=lambda it: it.get("collected_at", ""), reverse=True)


def sources_in_news() -> list[str]:
    """현재 뉴스에 등장한 출처 목록(필터용)."""
    return sorted({it.get("source", "") for it in load_news()["items"] if it.get("source")})


# ── 주간 브리핑 ────────────────────────────────────────────────────

def build_digest_source(days: int = 7) -> dict:
    """최근 N일 항목을 카테고리/출처별로 묶어 브리핑 작성용 원자료로 반환한다.

    팀장(Claude Code)이 이 결과를 읽고 '전 소스에서 핵심만' 브리핑을 작성한다.
    반환: {"period", "count", "ids", "by_category": {cat: [item, ...]}}
    """
    items = recent_items(days=days)
    by_category: dict[str, list[dict]] = {}
    for it in items:
        by_category.setdefault(it.get("category") or "기타", []).append(it)
    today = datetime.now()
    period = f"{(today - timedelta(days=days)).strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}"
    return {
        "period": period,
        "count": len(items),
        "ids": [it["id"] for it in items],
        "by_category": by_category,
    }


def digest_to_markdown(digest: dict) -> str:
    """구조화 브리핑(dict)을 뉴닉 구성 그대로 마크다운으로 직렬화한다.

    지식베이스에 검색 가능한 문서로 저장하기 위한 형식.
    인트로 → 핵심 3건(질문 포함) → 자투리 → 필요 기술 → 공부거리 순.
    """
    lines = [f"# {digest.get('title', '주간 AI 뉴스 브리핑')}", ""]
    if digest.get("period"):
        lines += [f"> 기간: {digest['period']}", ""]
    if digest.get("intro"):
        lines += ["## 📋 이번 주 AI 한 편으로", "", digest["intro"], ""]

    for i, d in enumerate(digest.get("deep_dives", []), 1):
        emoji = d.get("emoji", "🔥")
        lines += [f"## {emoji} 핵심 {i}. {d.get('title', '')}", ""]
        if d.get("body"):
            lines += [d["body"], ""]
        if d.get("question"):
            lines += [f"> ❔ **생각해볼 질문** — {d['question']}", ""]
        srcs = d.get("sources", [])
        if srcs:
            cited = " · ".join(
                f"[{s.get('name', '출처')}]({s['url']})" if s.get("url") else s.get("name", "")
                for s in srcs
            )
            lines += [f"출처: {cited}", ""]

    shorts = digest.get("shorts", [])
    if shorts:
        lines += ["## 📌 자투리 뉴스", ""]
        for s in shorts:
            title = s.get("title", "")
            link = s.get("link", "")
            head = f"[{title}]({link})" if link else title
            blurb = f" — {s['blurb']}" if s.get("blurb") else ""
            src = f" ({s['source']})" if s.get("source") else ""
            lines += [f"- **{head}**{blurb}{src}"]
        lines += [""]

    if digest.get("skills"):
        lines += ["## 🛠 필요 기술 · 알아두면 좋은 개념", ""]
        lines += [f"- {x}" for x in digest["skills"]] + [""]
    if digest.get("study"):
        lines += ["## 📚 이번 주 공부거리", ""]
        lines += [f"- {x}" for x in digest["study"]] + [""]

    return "\n".join(lines)


def save_digest(digest: dict, ids: list[str]) -> str:
    """구조화 브리핑(dict)을 지식 문서로 저장하고 news.json에 등록한다.

    - digest_to_markdown()로 마크다운 본문 생성 → file_tools.save_knowledge_file()로 지식베이스 저장
    - 구조화 dict에 knowledge_path·created_at·item_count를 채워 news.json digests에 insert(0)
    - 대상 항목 in_digest=True 표시
    반환: 저장된 지식 문서 경로.
    """
    md = digest_to_markdown(digest)
    path = save_knowledge_file(digest.get("title", "주간 AI 뉴스 브리핑"), md,
                               tags=["주간 브리핑", "AI 뉴스", "트렌드"])
    entry = dict(digest)
    entry["knowledge_path"] = path
    entry["created_at"] = datetime.now().isoformat(timespec="seconds")
    entry["item_count"] = len(ids)

    data = load_news()
    id_set = set(ids)
    for it in data["items"]:
        if it["id"] in id_set:
            it["in_digest"] = True
    data["digests"].insert(0, entry)
    save_news(data)
    return path


def latest_digest() -> dict | None:
    """가장 최근 브리핑(구조화 dict)을 반환. 없으면 None."""
    digests = load_news().get("digests", [])
    return digests[0] if digests else None
