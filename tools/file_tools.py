from datetime import datetime

from tools import storage

DB_REL = "knowledge_db.json"
KNOWLEDGE_DIR_REL = "knowledge"


def load_db() -> dict:
    return storage.read_json(DB_REL, {"items": []})


def save_db(db: dict) -> None:
    storage.write_json(DB_REL, db)


def save_knowledge_file(title: str, content: str, tags: list[str] | None = None) -> str:
    """정리된 지식을 knowledge/ 에 Markdown으로 저장하고 상대경로를 반환."""
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{safe_title[:40].strip()}.md"
    relpath = f"{KNOWLEDGE_DIR_REL}/{filename}"

    storage.write_text(relpath, content)

    db = load_db()
    db["items"].append({
        "title": title,
        "path": relpath,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    })
    save_db(db)

    return relpath
