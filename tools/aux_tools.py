"""보조 프로그램 카탈로그 — 확장프로그램·단축키 사이트·유용한 툴 전역 관리.

커리큘럼과 독립된 전역 카탈로그(data/aux_programs.json)에 제목/설명/링크/분류로
저장한다. 앱의 '보조 프로그램' 탭과 Claude Code(팀장)가 함께 사용한다.
"""

import json
from datetime import datetime
from pathlib import Path

AUX_DB_PATH = Path(__file__).parent.parent / "data" / "aux_programs.json"

# 카테고리 표준값 (자유 입력도 허용하되 UI 기본 분류로 사용)
CATEGORIES = ["크롬확장", "단축키", "웹툴", "데스크톱앱", "기타"]


def load_aux_db() -> dict:
    if not AUX_DB_PATH.exists():
        return {"items": []}
    with open(AUX_DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_aux_db(db: dict) -> None:
    AUX_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUX_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def add_aux_program(title: str, description: str, url: str,
                    category: str = "기타", tags: list[str] | None = None,
                    curriculum_id: str | None = None) -> dict:
    """보조 프로그램을 카탈로그에 추가하고 추가된 항목 dict를 반환한다.

    같은 URL이 이미 있으면 새로 만들지 않고 기존 항목을 갱신한다.
    """
    db = load_aux_db()
    url = (url or "").strip()
    now = datetime.now().isoformat()

    existing = next((i for i in db["items"] if (i.get("url") or "").strip() == url and url), None)
    if existing:
        existing.update({
            "title": title.strip() or existing.get("title", ""),
            "description": description.strip(),
            "category": category or existing.get("category", "기타"),
            "tags": tags or existing.get("tags", []),
            "curriculum_id": curriculum_id if curriculum_id is not None else existing.get("curriculum_id"),
            "updated_at": now,
        })
        save_aux_db(db)
        return existing

    item = {
        "id": f"aux_{datetime.now().strftime('%Y%m%d_%H%M%S%f')[:18]}",
        "title": title.strip(),
        "description": description.strip(),
        "url": url,
        "category": category or "기타",
        "tags": tags or [],
        "curriculum_id": curriculum_id,
        "added_at": now,
    }
    db["items"].append(item)
    save_aux_db(db)
    return item


def delete_aux_program(aux_id: str) -> bool:
    """id로 보조 프로그램을 삭제한다. 성공 여부 반환."""
    db = load_aux_db()
    before = len(db["items"])
    db["items"] = [i for i in db["items"] if i.get("id") != aux_id]
    if len(db["items"]) == before:
        return False
    save_aux_db(db)
    return True


def list_aux_programs(category: str | None = None) -> list[dict]:
    """보조 프로그램 목록을 반환한다. category 지정 시 해당 분류만."""
    items = load_aux_db().get("items", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    return items
