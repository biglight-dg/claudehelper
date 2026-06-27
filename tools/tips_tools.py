"""AI 사용 꿀팁 카탈로그 — 짧고 즉시 따라할 수 있는 사용법·노하우 모음.

보조 프로그램(외부 도구 링크)과 분리된 전역 컬렉션(data/ai_tips.json).
도구가 아니라 '사용법·노하우'를 짧은 카드로 모은다(예: '/goal 로 목표 고정하기').
앱의 '💡 AI 꿀팁' 탭과 Claude Code(팀장)가 함께 사용한다.
"""

from datetime import datetime

from tools import storage

TIPS_REL = "ai_tips.json"

# 카테고리 표준값 (자유 입력도 허용하되 UI 기본 분류로 사용)
TIP_CATEGORIES = [
    "Claude Code",
    "프롬프트",
    "워크플로우",
    "ChatGPT·제미나이",
    "자동화·MCP",
    "토큰 절약",
    "일반",
]


def load_tips_db() -> dict:
    return storage.read_json(TIPS_REL, {"items": []})


def save_tips_db(db: dict) -> None:
    storage.write_json(TIPS_REL, db)


def add_tip(title: str, body: str, example: str = "",
            category: str = "일반", tags: list[str] | None = None,
            source: str = "") -> dict:
    """꿀팁을 카탈로그에 추가하고 추가된 항목 dict를 반환한다.

    같은 제목(title)이 이미 있으면 새로 만들지 않고 기존 항목을 갱신한다.
    """
    db = load_tips_db()
    title = (title or "").strip()
    now = datetime.now().isoformat()

    existing = next(
        (i for i in db["items"] if (i.get("title") or "").strip() == title and title),
        None,
    )
    if existing:
        existing.update({
            "body": body.strip(),
            "example": (example or "").strip(),
            "category": category or existing.get("category", "일반"),
            "tags": tags or existing.get("tags", []),
            "source": (source or "").strip() or existing.get("source", ""),
            "updated_at": now,
        })
        save_tips_db(db)
        return existing

    item = {
        "id": f"tip_{datetime.now().strftime('%Y%m%d_%H%M%S%f')[:18]}",
        "title": title,
        "body": body.strip(),
        "example": (example or "").strip(),
        "category": category or "일반",
        "tags": tags or [],
        "source": (source or "").strip(),
        "added_at": now,
    }
    db["items"].append(item)
    save_tips_db(db)
    return item


def delete_tip(tip_id: str) -> bool:
    """id로 꿀팁을 삭제한다. 성공 여부 반환."""
    db = load_tips_db()
    before = len(db["items"])
    db["items"] = [i for i in db["items"] if i.get("id") != tip_id]
    if len(db["items"]) == before:
        return False
    save_tips_db(db)
    return True


def list_tips(category: str | None = None) -> list[dict]:
    """꿀팁 목록을 반환한다. category 지정 시 해당 분류만."""
    items = load_tips_db().get("items", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    return items
