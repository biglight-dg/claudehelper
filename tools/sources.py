"""입력 소스 커넥터 — RSS 피드 · 전문가 SNS · 웹검색 결과를 inbox로 모은다.

모든 수집물은 reader.save_to_inbox()로 data/inbox/ 에 저장돼,
기존 "정리해줘" 워크플로(교육자 → QA → 큐레이터)를 그대로 탄다.

설계 원칙: 새 API 키를 만들지 않는다.
  - RSS: feedparser, 키 불필요
  - 전문가 SNS: og 메타 best-effort (부실하면 팀장이 just-scrape 스킬로 재수집)
  - 웹검색: 팀장(Claude Code)이 WebSearch/just-scrape로 모은 텍스트를 save_research()로 적재

워치리스트 저장소: data/sources.json (data는 Google 공유 드라이브 정션 → 팀 공동 편집)
"""
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from tools import storage
from tools.reader import save_to_inbox

SOURCES_REL = "sources.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


# ── 워치리스트 저장소 ─────────────────────────────────────────────

def load_sources() -> dict:
    """sources.json 로드(로컬 또는 드라이브). 없으면 빈 구조 반환."""
    data = storage.read_json(SOURCES_REL, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("rss", [])
    data.setdefault("experts", [])
    data.setdefault("seen", {})
    return data


def save_sources(data: dict) -> None:
    storage.write_json(SOURCES_REL, data)


def add_rss(title: str, url: str, category: str = "") -> dict:
    """RSS 피드를 워치리스트에 추가(중복 URL은 무시)."""
    data = load_sources()
    if not any(r["url"] == url for r in data["rss"]):
        data["rss"].append({"title": title.strip(), "url": url.strip(), "category": category.strip()})
        save_sources(data)
    return data


def remove_rss(url: str) -> dict:
    data = load_sources()
    data["rss"] = [r for r in data["rss"] if r["url"] != url]
    data["seen"].pop(url, None)
    save_sources(data)
    return data


def add_expert(name: str, platform: str, url: str, note: str = "") -> dict:
    """전문가를 SNS 워치리스트에 추가(중복 URL은 무시).

    유튜브 채널이면 RSS 피드로 자동 변환해 add_rss()로 연결하고,
    그 주소를 expert["feed_url"]에 기록한다(= 자동수집 대상이 됨).
    RSS가 불가능한 SNS(인스타·X·스레드·링크드인)는 feed_url=None.
    """
    name, platform, url, note = name.strip(), platform.strip(), url.strip(), note.strip()
    data = load_sources()
    if not any(e["url"] == url for e in data["experts"]):
        feed_url = youtube_channel_to_feed(url) if _is_youtube(url) else None
        data["experts"].append({
            "name": name, "platform": platform,
            "url": url, "note": note, "feed_url": feed_url,
        })
        save_sources(data)
        if feed_url:
            add_rss(name, feed_url, category="전문가 유튜브")
    return data


def remove_expert(url: str) -> dict:
    data = load_sources()
    data["experts"] = [e for e in data["experts"] if e["url"] != url]
    save_sources(data)
    return data


# ── 유튜브 채널 → RSS 변환 / 자동수집 판정 ───────────────────────

def _is_youtube(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return "youtube.com" in host or "youtu.be" in host


def youtube_channel_to_feed(url: str) -> str | None:
    """유튜브 채널 URL(@handle 또는 /channel/UC...)을 RSS 피드 URL로 변환한다.

    - /channel/UC... 형태면 네트워크 없이 바로 구성
    - @handle 등은 채널 페이지 HTML에서 channelId를 추출
    실패하면 None (영상 단일 링크·비유튜브 등).
    """
    if not _is_youtube(url):
        return None
    m = re.search(r"/channel/(UC[\w-]{22})", url)
    if m:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
    try:
        html = requests.get(url, timeout=10, headers=HEADERS).text
        m = (re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', html)
             or re.search(r'youtube\.com/channel/(UC[\w-]{22})', html))
        if m:
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
    except Exception:
        pass
    return None


def auto_collect_kind(url: str) -> str | None:
    """자동수집(RSS) 가능 종류를 판정한다.

    "youtube" = 유튜브 채널(자동 RSS), "web" = 블로그 등 RSS 후보,
    None = 인스타·X·스레드·링크드인(공식 RSS 없음 → 수동 수집).
    """
    if _is_youtube(url):
        return "youtube"
    if _platform_of(url) in ("instagram", "x", "linkedin", "threads"):
        return None
    return "web"


def sync_expert_feeds() -> dict:
    """전문가 중 유튜브인데 아직 feed_url이 없는 항목을 RSS로 자동 연결한다.

    등록 즉시 자동화(add_expert)의 안전망 + 기존 전문가 1회 백필 겸용.
    매주 스케줄러(AI교육팀_전문가피드동기화)가 호출한다.
    반환: {"linked": [{name, feed}], "skipped": [{name, platform, url}]}
    """
    data = load_sources()
    linked, skipped = [], []
    for e in data["experts"]:
        if e.get("feed_url"):
            continue
        feed = youtube_channel_to_feed(e["url"]) if _is_youtube(e["url"]) else None
        if feed:
            e["feed_url"] = feed
            linked.append({"name": e["name"], "feed": feed})
        else:
            e.setdefault("feed_url", None)
            skipped.append({"name": e["name"], "platform": e.get("platform"), "url": e["url"]})
    save_sources(data)
    for item in linked:
        add_rss(item["name"], item["feed"], category="전문가 유튜브")
    return {"linked": linked, "skipped": skipped}


# ── RSS (자동, 키 불필요) ─────────────────────────────────────────

def fetch_rss(feed_url: str, limit: int = 5) -> list[dict]:
    """RSS/Atom 피드에서 최신 N개 항목을 추출한다.

    반환: [{"title", "link", "summary", "published", "guid"}, ...]
    """
    try:
        import feedparser
    except ImportError:
        return [{"title": "[feedparser 미설치: pip install feedparser]",
                 "link": "", "summary": "", "published": "", "guid": ""}]

    parsed = feedparser.parse(feed_url)
    items = []
    for entry in parsed.entries[:limit]:
        summary = entry.get("summary", "") or entry.get("description", "")
        if summary:
            summary = BeautifulSoup(summary, "html.parser").get_text(separator="\n", strip=True)
        items.append({
            "title": (entry.get("title", "") or "").strip(),
            "link": entry.get("link", ""),
            "summary": summary,
            "published": entry.get("published", "") or entry.get("updated", ""),
            "guid": entry.get("id", "") or entry.get("link", ""),
        })
    return items


def pull_all_rss(limit_each: int = 5) -> list[Path]:
    """워치리스트의 모든 피드를 돌며 신규 항목만 inbox에 저장한다.

    이미 본(seen) guid는 건너뛰어 중복을 막는다.
    반환: 새로 저장한 파일 경로 리스트.
    """
    data = load_sources()
    saved: list[Path] = []
    for feed in data["rss"]:
        feed_url = feed["url"]
        seen = set(data["seen"].get(feed_url, []))
        for item in fetch_rss(feed_url, limit=limit_each):
            guid = item["guid"]
            if not guid or guid in seen:
                continue
            header = (
                f"출처(RSS): {feed.get('title') or feed_url}\n"
                f"제목: {item['title']}\n"
                f"링크: {item['link']}\n"
                f"발행: {item['published']}\n\n"
            )
            filename = f"rss_{item['title'][:40]}".strip() or "rss_item"
            path = save_to_inbox(filename, header + item["summary"])
            saved.append(path)
            seen.add(guid)
        data["seen"][feed_url] = list(seen)
    save_sources(data)
    return saved


# ── 전문가 SNS (best-effort, 폴백) ────────────────────────────────

def _platform_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "instagram" in host:
        return "instagram"
    if "twitter" in host or host.endswith("x.com") or host == "x.com":
        return "x"
    if "linkedin" in host:
        return "linkedin"
    if "threads" in host:
        return "threads"
    return "web"


def fetch_social_post(url: str) -> dict:
    """SNS 게시물 링크에서 og 메타(제목·캡션·이미지)를 best-effort로 추출한다.

    인스타·X·링크드인은 로그인 벽/봇 차단으로 캡션 일부만 잡히거나 비어 있을 수 있다.
    본문이 부실하면 팀장(Claude Code)이 just-scrape 스킬로 재수집하는 것을 권장한다.
    실패해도 예외 없이 가능한 값만 채워 반환한다.

    반환: {"type": "social", "platform", "title", "caption", "image", "url"}
    """
    result = {"type": "social", "platform": _platform_of(url),
              "title": "", "caption": "", "image": "", "url": url}
    try:
        resp = requests.get(url, timeout=10, headers=HEADERS)
        if resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")

            def _og(prop, name=None):
                tag = soup.find("meta", property=prop)
                if not tag and name:
                    tag = soup.find("meta", attrs={"name": name})
                return (tag.get("content") or "").strip() if tag and tag.get("content") else ""

            result["title"] = _og("og:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
            result["caption"] = _og("og:description", "description")
            result["image"] = _og("og:image")
    except Exception:
        pass
    return result


def save_social_post(url: str) -> Path:
    """전문가 SNS 게시물을 추출해 inbox에 저장하고 경로를 반환."""
    post = fetch_social_post(url)
    header = (
        f"출처(SNS/{post['platform']}): {url}\n"
        f"제목: {post['title']}\n\n"
    )
    body = post["caption"] or "[캡션을 가져오지 못했습니다 — 본문이 필요하면 Claude Code에 'just-scrape로 가져와줘'라고 요청하세요]"
    filename = f"sns_{post['platform']}_{(post['title'] or 'post')[:30]}".strip()
    return save_to_inbox(filename, header + body)


# ── 웹검색 결과 적재 헬퍼 ─────────────────────────────────────────

def save_research(title: str, url: str, content: str) -> Path:
    """팀장이 WebSearch/just-scrape로 모은 자료를 표준 헤더와 함께 inbox에 저장한다."""
    header = (
        f"출처(웹검색): {url}\n"
        f"제목: {title}\n"
        f"수집일: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    )
    filename = f"web_{title[:40]}".strip() or "web_research"
    return save_to_inbox(filename, header + content)
