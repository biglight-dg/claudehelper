import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "knowledge_db.json"
KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "knowledge"


def load_db() -> dict:
    if not DB_PATH.exists():
        return {"items": []}
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def save_knowledge_file(title: str, content: str, tags: list[str] | None = None) -> str:
    """정리된 지식을 data/knowledge/ 에 Markdown으로 저장하고 경로를 반환."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{safe_title[:40].strip()}.md"
    filepath = KNOWLEDGE_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    db = load_db()
    db["items"].append({
        "title": title,
        "path": str(filepath),
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    })
    save_db(db)

    return str(filepath)
