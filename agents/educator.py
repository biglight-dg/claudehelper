"""교육자 에이전트 — 원자료를 중학생 수준의 교육 자료로 변환한다.

PPT 생성: tools/pptx_maker.py (python-pptx) 사용.
디자인 기준: skills/pptx/design_spec.md
  - 색상: 흑백 전용 (WHITE/BLACK/GRAY 계열만)
  - 폰트: Pretendard (폴백: Malgun Gothic → Arial)
  - 레이아웃: 아주 단순하게, 슬라이드당 핵심 메시지 1개
"""

from tools.pptx_maker import PptxMaker

SYSTEM_PROMPT = """당신은 AI 교육팀의 교육자입니다.

역할:
- inbox에 들어온 원자료를 받아 교육 자료로 변환
- "중학생도 이해할 수 있는" 수준 유지 (전문 용어는 반드시 비유와 함께)
- 단계별 설명, 시각적 구성, 예시 중심으로 작성

산출물 종류:
1. 교육 문서 (Markdown) — 상세 설명 + 비교표 + 핵심 교훈
2. PPT 슬라이드 (python-pptx) — tools/pptx_maker.py 사용
3. 요약 카드 — 핵심만 뽑은 1페이지

PPT 디자인 기준 (반드시 준수):
- 색상: 흑백만 사용. 배경 흰색(FFFFFF), 제목 검정(000000), 본문 진한회색(222222), 보조 중간회색(666666), 구분선 연한회색(CCCCCC)
- 폰트: Pretendard (없으면 Malgun Gothic → Arial 순으로 폴백)
- 레이아웃: 아주 단순하게. 슬라이드당 핵심 메시지 1개, 불릿 최대 3개
- 금지: 유채색, 그라디언트, 그림자, 복잡한 장식

슬라이드 구성 (5~8장):
  슬라이드 1: 타이틀 (제목 + 부제목)
  슬라이드 2~N-2: 핵심 개념별 콘텐츠 (섹션 라벨 + 제목 + 불릿 3개)
  슬라이드 N-1: 비교표 (있는 경우)
  슬라이드 N: 요약 — 핵심 교훈 3가지 + 출처

문서 작성 규칙:
- 첫 문단: 비유로 개념 소개 ("마치 X처럼...")
- 본문: 섹션마다 이모지로 구분
- 마지막: 핵심 교훈 3가지 이내
- 출처 표기 필수

스킬 참조: skills/pptx/SKILL.md, skills/pptx/design_spec.md
"""

DOCUMENT_TEMPLATE = """# {title}

## 한 줄 소개

{intro}

---

{body}

---

## 핵심 교훈

{key_lessons}

---

> 출처: {source}
"""


class Educator:
    """원자료를 교육 자료 형식으로 구조화하고 PPT를 생성하는 유틸리티."""

    def make_pptx(
        self,
        title: str,
        subtitle: str,
        slides: list[dict],
        source: str = "",
    ) -> str:
        """PPT를 생성하고 저장 경로를 반환한다.

        slides 형식:
        [
          {"type": "content", "section": "섹션명", "title": "제목", "bullets": ["..."]},
          {"type": "comparison", "title": "비교 제목",
           "left_label": "항목A", "left_items": [...],
           "right_label": "항목B", "right_items": [...]},
          {"type": "divider", "number": "01", "section": "섹션명"},
        ]
        마지막 요약 슬라이드(lessons)는 별도 인자로 받는다.
        """
        maker = PptxMaker(title=title)
        maker.add_title_slide(title, subtitle)

        summary_slide = None
        for slide in slides:
            stype = slide.get("type", "content")
            if stype == "title":
                continue  # 이미 add_title_slide로 추가됨
            elif stype == "content":
                maker.add_content_slide(
                    slide.get("section", ""),
                    slide.get("title", ""),
                    slide.get("bullets", []),
                )
            elif stype == "table":
                maker.add_table_slide(
                    slide.get("section", ""),
                    slide.get("title", ""),
                    slide.get("headers", []),
                    slide.get("rows", []),
                )
            elif stype == "cards":
                maker.add_cards_slide(
                    slide.get("section", ""),
                    slide.get("title", ""),
                    slide.get("items", []),
                    slide.get("variant", "number"),
                )
            elif stype == "flow":
                maker.add_flow_slide(
                    slide.get("section", ""),
                    slide.get("title", ""),
                    slide.get("steps", []),
                )
            elif stype == "comparison":
                maker.add_comparison_slide(
                    slide.get("title", ""),
                    slide.get("left_label", ""),
                    slide.get("left_items", []),
                    slide.get("right_label", ""),
                    slide.get("right_items", []),
                )
            elif stype == "part_divider":
                maker.add_part_divider_slide(
                    slide.get("label", ""),
                    slide.get("title", ""),
                    slide.get("weeks", ""),
                )
            elif stype == "divider":
                maker.add_divider_slide(
                    slide.get("number", ""),
                    slide.get("section", ""),
                )
            elif stype == "summary":
                summary_slide = slide

        if summary_slide:
            maker.add_summary_slide(
                summary_slide.get("lessons", []),
                source or summary_slide.get("source", ""),
            )
        else:
            maker.add_summary_slide(["핵심 내용을 직접 정리해보세요."], source)

        return maker.save(title)

    def make_document(self, title: str, raw_content: str, source: str = "") -> str:
        """원자료를 교육 문서 Markdown 포맷으로 구조화한다."""
        return DOCUMENT_TEMPLATE.format(
            title=title,
            intro="[Claude Code가 작성]",
            body=raw_content,
            key_lessons="[Claude Code가 작성]",
            source=source if source else "사용자 제공 자료",
        )

    def make_summary_card(self, title: str, key_points: list[str], source: str = "") -> str:
        """1페이지 요약 카드 Markdown을 반환한다."""
        bullets = "\n".join(f"- {p}" for p in key_points[:5])
        return f"""# {title} — 한 장 요약

{bullets}

> 출처: {source if source else "사용자 제공 자료"}
"""

    def quality_checklist(self, content: str) -> list[str]:
        """교육자 자가 체크리스트 — 부족한 항목 목록을 반환한다."""
        issues = []
        if "비유" not in content and "처럼" not in content and "마치" not in content:
            issues.append("비유 표현이 없습니다. 어려운 개념을 쉬운 비유로 설명하세요.")
        if content.count("\n## ") < 2:
            issues.append("섹션 구분이 부족합니다. H2 헤딩으로 섹션을 나누세요.")
        if "출처" not in content and ">" not in content:
            issues.append("출처 표기가 없습니다.")
        if len(content) < 300:
            issues.append("내용이 너무 짧습니다. 최소 300자 이상 작성하세요.")
        return issues
