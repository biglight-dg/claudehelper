"""커리큘럼·지식 인덱스를 표 형태(행/열)로 빌드한다.

데이터 생성 로직(build_*)을 분리해 CSV 내보내기와 Google Sheets 동기화
(gsheet_sync.py)가 함께 쓴다.

CSV로 내보내려면:
    python tools/export_sheets_csv.py
출력은 data/outputs/sheets/ (공유 드라이브 동기화).
"""
import csv
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
CURRICULA_DIR = BASE / "data" / "curricula"
KNOWLEDGE_DB = BASE / "data" / "knowledge_db.json"
OUT_DIR = BASE / "data" / "outputs" / "sheets"


def build_curriculum_rows() -> tuple[list[str], list[dict]]:
    """커리큘럼 세션 표: 커리큘럼/주차/제목/목표/활동/소요시간/강사노트."""
    db = json.loads((CURRICULA_DIR / "curriculum_db.json").read_text(encoding="utf-8"))
    rows = []
    for c in db.get("curricula", []):
        path = Path(c["path"])
        if not path.exists():
            print(f"  [건너뜀] 파일 없음: {path}")
            continue
        cur = json.loads(path.read_text(encoding="utf-8"))
        for s in cur.get("sessions", []):
            rows.append({
                "커리큘럼": cur.get("title", ""),
                "주차": s.get("week", ""),
                "세션 제목": s.get("title", ""),
                "목표": "\n".join(s.get("objectives", [])),
                "활동": "\n".join(s.get("activities", [])),
                "소요시간": s.get("duration", ""),
                "강사노트": s.get("notes", ""),
            })
    rows.sort(key=lambda r: (r["커리큘럼"], r["주차"] if isinstance(r["주차"], int) else 0))
    fields = ["커리큘럼", "주차", "세션 제목", "목표", "활동", "소요시간", "강사노트"]
    return fields, rows


def build_knowledge_rows() -> tuple[list[str], list[dict]]:
    """지식 자료 목록: 제목/태그/생성일."""
    db = json.loads(KNOWLEDGE_DB.read_text(encoding="utf-8"))
    rows = []
    for it in db.get("items", []):
        rows.append({
            "제목": it.get("title", ""),
            "태그": ", ".join(it.get("tags", [])),
            "생성일": (it.get("created_at", "") or "")[:10],
        })
    fields = ["제목", "태그", "생성일"]
    return fields, rows


def _write_csv(filename: str, fields: list[str], rows: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / filename
    # utf-8-sig: Google Sheets/엑셀이 한글을 깨짐 없이 인식하도록 BOM 포함
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return out


if __name__ == "__main__":
    p1 = _write_csv("커리큘럼_세션.csv", *build_curriculum_rows())
    p2 = _write_csv("지식_자료.csv", *build_knowledge_rows())
    print("생성 완료:")
    print(f"  - {p1}")
    print(f"  - {p2}")
