"""큐레이터 에이전트 — 지식베이스 DB를 관리하고 자료를 분류/태깅한다."""

import json
from pathlib import Path

SYSTEM_PROMPT = """당신은 AI 교육팀의 큐레이터입니다.

역할:
- 교육자가 만든 자료를 분류하고 태깅해 knowledge_db.json에 저장
- 사용자가 툴이나 자료를 찾을 때 DB를 검색해 추천
- 중복 자료가 있으면 병합하거나 최신 것으로 교체
- 태그 체계를 일관되게 유지

태그 분류 체계:
- 난이도: 입문 / 중급 / 고급
- 형식: 문서 / 슬라이드 / 요약카드
- 주제: AI비교 / 프롬프트 / 도구활용 / 트렌드 / 실습
- 도구명: ChatGPT / Gemini / Claude / Midjourney / Cursor 등

검색 시 우선순위:
1. 제목 일치
2. 태그 일치
3. 생성일 최신순
"""

DB_PATH = Path(__file__).parent.parent / "data" / "knowledge_db.json"

# 키워드 → 태그 자동 매핑 규칙
TAG_RULES: dict[str, list[str]] = {
    "chatgpt": ["ChatGPT", "AI비교"],
    "gpt": ["ChatGPT"],
    "gemini": ["Gemini", "AI비교"],
    "claude": ["Claude", "AI비교"],
    "프롬프트": ["프롬프트"],
    "cursor": ["Cursor", "도구활용"],
    "미드저니": ["Midjourney", "도구활용"],
    "midjourney": ["Midjourney", "도구활용"],
    "입문": ["입문"],
    "초보": ["입문"],
    "중학생": ["입문"],
    "비교": ["AI비교"],
    "트렌드": ["트렌드"],
    "뉴스": ["트렌드"],
    "실습": ["실습"],
    "따라하기": ["실습"],
    "슬라이드": ["슬라이드"],
    "ppt": ["슬라이드"],
    "요약": ["요약카드"],
}


class Curator:
    def load_db(self) -> dict:
        if not DB_PATH.exists():
            return {"items": []}
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)

    def save_db(self, db: dict) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

    def auto_tag(self, title: str, content: str) -> list[str]:
        """제목과 내용에서 태그를 자동 추출한다."""
        combined = (title + " " + content).lower()
        tags: set[str] = set()
        for keyword, mapped_tags in TAG_RULES.items():
            if keyword in combined:
                tags.update(mapped_tags)
        # 난이도 태그가 없으면 기본값 입문
        if not tags.intersection({"입문", "중급", "고급"}):
            tags.add("입문")
        return sorted(tags)

    def search(self, query: str) -> list[dict]:
        """제목 또는 태그로 지식베이스를 검색한다."""
        db = self.load_db()
        query_lower = query.lower()
        results = []
        for item in db.get("items", []):
            title_match = query_lower in item.get("title", "").lower()
            tag_match = any(query_lower in t.lower() for t in item.get("tags", []))
            if title_match or tag_match:
                results.append(item)
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_all_tags(self) -> list[str]:
        """DB에 등록된 모든 태그 목록을 반환한다."""
        db = self.load_db()
        tags: set[str] = set()
        for item in db.get("items", []):
            tags.update(item.get("tags", []))
        return sorted(tags)

    def find_duplicate(self, title: str) -> dict | None:
        """같은 제목의 기존 항목이 있으면 반환한다."""
        db = self.load_db()
        for item in db.get("items", []):
            if item.get("title", "").strip() == title.strip():
                return item
        return None

    def add_or_update(self, title: str, path: str, tags: list[str], created_at: str) -> str:
        """항목을 추가하거나 기존 항목을 업데이트한다. 'added' 또는 'updated' 반환."""
        db = self.load_db()
        for item in db["items"]:
            if item.get("title", "").strip() == title.strip():
                item["path"] = path
                item["tags"] = tags
                item["updated_at"] = created_at
                self.save_db(db)
                return "updated"
        db["items"].append(
            {"title": title, "path": path, "tags": tags, "created_at": created_at}
        )
        self.save_db(db)
        return "added"

    def get_stats(self) -> dict:
        """DB 통계를 반환한다."""
        db = self.load_db()
        items = db.get("items", [])
        all_tags = [t for item in items for t in item.get("tags", [])]
        return {
            "total_items": len(items),
            "total_tags": len(set(all_tags)),
            "tag_counts": {t: all_tags.count(t) for t in set(all_tags)},
        }
