"""커리큘럼 에이전트.

build_slides_data() → 수업 PPT용 (짧은 불릿, 표 활용, 명사형 어투)
build_doc_content()  → 교재용 Markdown (완전한 문장, 교재 어투)
"""

import re
from pathlib import Path

from tools.curriculum_tools import (
    build_markdown_doc, load_curriculum, load_curriculum_db, save_slides,
)

SYSTEM_PROMPT = """당신은 AI 교육팀의 커리큘럼 담당자입니다.

역할:
- 지식베이스 문서들을 묶어 주차별 학습 커리큘럼 관리
- 사용자 명령에 따라 세션 추가/수정/삭제, 슬라이드 재생성
- 커리큘럼은 data/curricula/ 폴더의 JSON 파일로 저장

핵심 원칙:
- 매 수정 후 반드시 save_curriculum() 호출 (updated_at 자동 갱신)
- 슬라이드는 커리큘럼이 바뀔 때마다 "슬라이드 업데이트해줘" 명령 시 재생성
- 지식 파일 참조 시 data/knowledge/ 경로 사용

명령어 패턴:
  "[제목] 커리큘럼 만들어줘"
    → new_curriculum(title) + save_curriculum()

  "[N]주차 세션 추가: [제목]"
    → new_session(week=N, title) + curriculum["sessions"].append() + save_curriculum()

  "[N]주차에 [파일명/제목] 연결해줘"
    → knowledge_refs에 파일 경로 추가 + save_curriculum()

  "[N]주차 목표 바꿔줘: [새 목표]"
    → 해당 세션 objectives 수정 + save_curriculum()

  "[N]주차 활동 추가: [활동]"
    → activities 리스트에 추가 + save_curriculum()

  "[N]주차 삭제해줘"
    → sessions에서 해당 week 제거 + save_curriculum()

  "커리큘럼 슬라이드 업데이트해줘"
    → build_slides_data(curriculum) → save_slides() → PptxMaker로 PPTX 재생성

  "커리큘럼 목록 보여줘"
    → load_curriculum_db() 출력

  "[제목] 커리큘럼 삭제해줘"
    → delete_curriculum(id)
"""


# ── PPT 슬라이드 생성 ──────────────────────────────────────────────

def build_slides_data(curriculum: dict) -> list[dict]:
    """커리큘럼 JSON → 수업 PPT용 슬라이드 list[dict].

    슬라이드 원칙:
    - 불릿은 짧게 (명사형, 30자 이내)
    - 비교/목록 데이터는 table 슬라이드로
    - 슬라이드당 메시지 1개
    """
    slides = []
    slide_num = 1
    seen_tables: set[tuple] = set()  # (file_path, table_title) 중복 방지

    # 타이틀 — 부제 앞에 학습 경로(순서·선수) 한 줄을 덧붙인다
    subtitle = curriculum.get("description", "")
    path_line = _learning_path_line(curriculum)
    if path_line:
        subtitle = f"{path_line}\n{subtitle}" if subtitle else path_line
    slides.append({
        "slide_number": slide_num,
        "type": "title",
        "title": curriculum["title"],
        "subtitle": subtitle,
    })
    slide_num += 1

    sessions = sorted(curriculum.get("sessions", []), key=lambda s: s["week"])

    # 파트별 주차 범위 (예: "Part A · ..." → "1~6주차") 미리 계산
    part_weeks: dict[str, list[int]] = {}
    for ses in sessions:
        part = ses.get("part")
        if part:
            part_weeks.setdefault(part, []).append(ses["week"])

    current_part = None

    for ses in sessions:
        week_label = f"{ses['week']}주차"

        # 파트 전환 시 파트 구분 슬라이드 삽입 (Part A/B …)
        part = ses.get("part")
        if part and part != current_part:
            current_part = part
            label, _, ptitle = part.partition("·")
            weeks = part_weeks.get(part, [])
            week_range = (f"{min(weeks)}~{max(weeks)}주차"
                          if weeks and min(weeks) != max(weeks)
                          else (f"{weeks[0]}주차" if weeks else ""))
            slides.append({
                "slide_number": slide_num,
                "type": "part_divider",
                "label": label.strip().upper(),
                "title": ptitle.strip() or label.strip(),
                "weeks": week_range,
            })
            slide_num += 1

        week_no = ses["week"]

        # 주차 구분 슬라이드
        slides.append({
            "slide_number": slide_num,
            "type": "divider",
            "week": week_no,
            "number": f"{ses['week']:02d}",
            "section": f"{ses['week']}주차: {ses['title']}",
        })
        slide_num += 1

        # 개념 설명 슬라이드 (선택) — 용어를 비개발 실무자용으로 풀어 설명 + 비유.
        # 세션 JSON에 concepts 필드가 있을 때만 생성(없으면 건너뜀, 하위 호환).
        for con in ses.get("concepts", [])[:3]:
            term = _clean_inline_md(con.get("term", "")).strip()
            explain = _clean_inline_md(con.get("explain", "")).strip()
            if not term or not explain:
                continue
            slides.append({
                "slide_number": slide_num,
                "type": "concept",
                "week": week_no,
                "section": week_label,
                "term": term,
                "explain": explain,
                "analogy": _clean_inline_md(con.get("analogy", "")).strip(),
            })
            slide_num += 1

        # 지식 파일에서 표 미리 수집 (세션당 최대 2개) — flow 핵심개념에도 재사용
        session_tables: list[dict] = []
        for ref_path in ses.get("knowledge_refs", []):
            path = Path(ref_path)
            if not path.exists():
                path = Path(__file__).parent.parent / ref_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for tbl in _extract_tables_from_md(text):
                key = (str(path), tbl["title"])
                if key in seen_tables or len(session_tables) >= 2:
                    continue
                seen_tables.add(key)
                session_tables.append(tbl)

        # 구조도(flow) 슬라이드 — 목표 → 핵심 개념 → 실습 한눈에
        concept_items = [_flow_item(t["title"]) for t in session_tables][:3]
        if not concept_items:
            concept_items = ["핵심 개념 정리"]
        steps = [
            {"label": "목표", "items": [_flow_item(o) for o in ses.get("objectives", [])][:3]},
            {"label": "핵심 개념", "items": concept_items},
            {"label": "실습", "items": [_flow_item(a) for a in ses.get("activities", [])][:3]},
        ]
        slides.append({
            "slide_number": slide_num,
            "type": "flow",
            "week": week_no,
            "section": week_label,
            "title": "이번 주차 한눈에",
            "steps": steps,
        })
        slide_num += 1

        # 학습 목표 — 번호 카드
        if ses.get("objectives"):
            short_objs = [_to_ppt_bullet(o) for o in ses["objectives"][:4]]
            slides.append({
                "slide_number": slide_num,
                "type": "cards",
                "week": week_no,
                "section": week_label,
                "title": "이번 주차 목표",
                "variant": "number",
                "items": short_objs,
            })
            slide_num += 1

        # 표 슬라이드
        for tbl in session_tables:
            slides.append({
                "slide_number": slide_num,
                "type": "table",
                "week": week_no,
                "section": week_label,
                "title": tbl["title"],
                "headers": tbl["headers"],
                "rows": tbl["rows"],
            })
            slide_num += 1

        # 활동 — 번호 카드
        if ses.get("activities"):
            short_acts = [_to_ppt_bullet(a) for a in ses["activities"][:4]]
            slides.append({
                "slide_number": slide_num,
                "type": "cards",
                "week": week_no,
                "section": week_label,
                "title": "실습 활동",
                "variant": "number",
                "items": short_acts,
            })
            slide_num += 1

    # 전체 요약 슬라이드
    all_weeks = [f"{s['week']}주차: {s['title']}" for s in sessions]
    slides.append({
        "slide_number": slide_num,
        "type": "summary",
        "lessons": all_weeks,
        "source": curriculum.get("description", "AI 교육팀"),
    })

    return slides


# ── 헬퍼 함수 ──────────────────────────────────────────────────────

def _learning_path_line(curriculum: dict) -> str:
    """타이틀 슬라이드 부제에 넣을 학습 경로 한 줄(순서·단계·선수)."""
    track = curriculum.get("track", "main")
    order = curriculum.get("order")
    level = curriculum.get("level", "")
    prereq = curriculum.get("prerequisites", [])

    if track == "elective":
        head = "독립 선택 트랙"
    elif order:
        head = f"학습 순서 {order}단계"
    else:
        head = ""
    if level:
        head = f"{head} · {level}" if head else level

    if prereq:
        id_to_title = {c["id"]: c["title"]
                       for c in load_curriculum_db().get("curricula", [])}
        names = ", ".join(id_to_title.get(pid, pid) for pid in prereq)
        head = f"{head} · 선수: {names}" if head else f"선수: {names}"
    return head


def _truncate_at_word(text: str, max_len: int) -> str:
    """max_len을 넘으면 마지막 어절 경계에서 자르고 …를 붙인다.

    단어 중간에서 끊어 의미가 깨지는 것을 막는다(공백이 없으면 그대로 절단).
    """
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    sp = cut.rfind(" ")
    if sp >= max_len * 0.6:  # 어절 경계가 너무 앞이 아니면 그 지점에서 자른다
        cut = cut[:sp]
    return cut.rstrip(" ,·-—") + "…"


def _flow_item(text: str, max_len: int = 34) -> str:
    """구조도(flow) 박스에 들어갈 짧은 키워드로 정리한다.

    인라인 마크다운 제거 후, 괄호·구분기호 앞부분만 남겨 명사형 키워드로 줄인다.
    엔진이 자동 줄바꿈/축소하므로 과거보다 넉넉히 둔다.
    """
    text = _clean_inline_md(text)
    for sep in (" — ", " – ", " (", "(", " · ", ": ", "—"):
        if sep in text:
            text = text.split(sep)[0]
            break
    return _truncate_at_word(text, max_len)


def _clean_inline_md(text: str) -> str:
    """셀·불릿 텍스트의 인라인 마크다운 기호를 제거한다.

    PPTX는 마크다운을 렌더링하지 않으므로 **굵게**·`코드`·[링크] 기호가
    그대로 노출돼 가독성을 해친다. 표시용 텍스트만 남긴다.
    """
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **굵게** → 굵게
    text = re.sub(r'\*(.+?)\*', r'\1', text)         # *기울임* → 기울임
    text = text.replace('`', '').replace('**', '').replace('*', '')
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)  # [텍스트](링크) → 텍스트
    return text.strip()


def _to_ppt_bullet(text: str) -> str:
    """텍스트를 PPT 불릿에 맞게 정리한다.

    본문 영역에 줄바꿈(word_wrap)이 적용되고 세로로 골고루 분포되므로,
    의미가 깨지는 공격적 절단(→ 앞에서 자르기 등)은 하지 않는다.
    두 줄까지 자연스럽게 들어가도록 길이만 넉넉히 제한한다.
    """
    text = _clean_inline_md(text)
    # 불필요한 주어 제거
    for prefix in ('이번 주차에서는 ', '학습자는 ', '수강생은 ', '학생은 '):
        if text.startswith(prefix):
            text = text[len(prefix):]
    # 엔진이 자동 줄바꿈/축소하므로 넉넉히 허용(약 3줄 분량), 넘치면 어절 경계에서.
    return _truncate_at_word(text.strip(), 90)


def _extract_tables_from_md(text: str) -> list[dict]:
    """마크다운에서 테이블을 추출한다. 직전 헤딩을 제목으로 사용."""
    tables = []
    lines = text.splitlines()
    last_heading = ""
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 헤딩 추적
        if line.startswith('#'):
            last_heading = line.lstrip('#').strip()
            i += 1
            continue

        # 테이블 헤더 행 감지 (| col | col | 형식, 구분선 아님)
        if (line.startswith('|') and line.endswith('|')
                and '---' not in line and len(line) > 3):
            headers = [_clean_inline_md(h.strip()) for h in line.split('|')[1:-1] if h.strip()]
            if not headers:
                i += 1
                continue

            # 다음 줄이 구분선인지 확인
            next_i = i + 1
            if next_i < len(lines) and '---' in lines[next_i]:
                rows = []
                next_i += 1  # 구분선 skip
                while (next_i < len(lines)
                       and lines[next_i].strip().startswith('|')
                       and '---' not in lines[next_i]):
                    row_cells = [_clean_inline_md(c.strip()) for c in lines[next_i].split('|')[1:-1]]
                    if any(c for c in row_cells):
                        rows.append(row_cells)
                    next_i += 1

                if rows:
                    tables.append({
                        'title': last_heading or '핵심 정리',
                        'headers': headers[:5],
                        'rows': rows[:8],
                    })
                i = next_i
                continue

        i += 1

    return tables
