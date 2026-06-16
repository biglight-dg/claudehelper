"""팀장 에이전트 — 사용자 요청을 분석하고 다른 에이전트에게 작업을 위임한다."""

SYSTEM_PROMPT = """당신은 AI 교육팀의 팀장입니다.

역할:
- 사용자와 대화하는 유일한 창구
- inbox에 들어온 자료를 보고 어떤 처리가 필요한지 판단
- 교육자, 큐레이터, QA 에이전트에게 작업을 위임
- 최종 결과물을 사용자에게 보고

판단 기준:
- "정리해줘" → 교육자가 문서 형식으로 변환 후 큐레이터가 저장
- "PPT 만들어줘" / "슬라이드" → 교육자가 Canva 슬라이드 생성
- "태그 정리" / "분류" → 큐레이터가 DB 정리
- "검토해줘" / "QA" → QA 에이전트가 기존 지식 파일 검토
- "저장된 거 찾아줘" → 큐레이터가 검색

항상 처리 완료 후 다음을 보고하라:
1. 어떤 에이전트가 무엇을 했는지
2. 저장된 파일 경로
3. 다음 추천 액션
"""


class TeamLead:
    """사용자 요청을 파싱해 작업 라우팅 정보를 반환한다."""

    TASK_KEYWORDS = {
        "document": ["정리", "요약", "문서", "설명"],
        "slides": ["ppt", "슬라이드", "발표", "canva", "프레젠테이션"],
        "curate": ["태그", "분류", "저장", "등록"],
        "search": ["찾아", "검색", "있어?", "뭐 있"],
        "qa": ["검토", "확인", "qa", "품질"],
    }

    def route(self, user_input: str) -> str:
        """사용자 입력을 분석해 작업 유형 반환."""
        lower = user_input.lower()
        for task, keywords in self.TASK_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return task
        return "document"  # 기본값

    def build_summary(
        self,
        task: str,
        inbox_count: int,
        output_path: str | None = None,
        qa_passed: bool | None = None,
    ) -> str:
        """처리 완료 후 사용자에게 보여줄 요약 메시지를 만든다."""
        lines = [f"## 팀장 보고"]
        lines.append(f"- inbox에서 {inbox_count}개 파일 처리")
        lines.append(f"- 작업 유형: **{task}**")

        if output_path:
            lines.append(f"- 저장 위치: `{output_path}`")

        if qa_passed is True:
            lines.append("- QA 검토: ✅ 통과")
        elif qa_passed is False:
            lines.append("- QA 검토: ⚠️ 피드백 있음 — 교육자가 수정 후 재저장")

        lines.append("\n다음 추천:")
        if task == "document":
            lines.append("- `PPT 만들어줘`로 슬라이드 생성")
        elif task == "slides":
            lines.append("- Canva에서 디자인 편집 후 공유")

        return "\n".join(lines)
