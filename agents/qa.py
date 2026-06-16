"""QA 에이전트 — 교육자 산출물의 품질을 검토하고 피드백을 제공한다."""

SYSTEM_PROMPT = """당신은 AI 교육팀의 QA 담당자입니다.

역할:
- 교육자가 만든 문서/슬라이드를 세 가지 기준으로 검토
- 통과 못하면 구체적인 수정 지침과 함께 교육자에게 피드백
- 통과하면 큐레이터에게 저장 요청

검토 기준:

1. 난이도 (Difficulty) — 중학생이 이해할 수 있는가?
   - 전문 용어가 나오면 반드시 쉬운 설명이 뒤따라야 함
   - 비유, 예시, 이야기 방식 사용
   - 합격 기준: 어려운 용어 100% 설명됨

2. 정확성 (Accuracy) — 사실 오류가 없는가?
   - AI 도구 이름, 기능, 회사명 정확히 표기
   - 과장이나 오해 소지 있는 표현 없음
   - 합격 기준: 명백한 오류 0개

3. 일관성 (Consistency) — 팀 기준을 따르는가?
   - 이모지 사용 (섹션 구분)
   - 출처 표기
   - 핵심 교훈 섹션 포함
   - 합격 기준: 3개 항목 모두 충족

점수 계산: 각 기준 0~10점, 합산 21점 이상 = 통과
"""

# 검토 기준 상수
PASSING_SCORE = 21
MAX_SCORE = 30

# 어려운 용어 목록 (설명 없이 쓰면 감점)
JARGON_TERMS = [
    "LLM", "파인튜닝", "파라미터", "토큰", "임베딩", "API", "RAG",
    "멀티모달", "추론", "컨텍스트", "프롬프트 엔지니어링",
]

# 필수 포함 요소
REQUIRED_ELEMENTS = ["출처", "##", "핵심"]


class QA:
    def check_difficulty(self, content: str) -> dict:
        """어려운 용어가 설명 없이 사용됐는지 확인한다."""
        unexplained = []
        for term in JARGON_TERMS:
            if term.lower() in content.lower():
                # 용어 바로 뒤 50자 안에 설명 표현이 있는지 확인
                idx = content.lower().find(term.lower())
                window = content[idx : idx + 80].lower()
                has_explanation = any(
                    marker in window for marker in ["(", "—", ":", "란", "은", "는", "이란"]
                )
                if not has_explanation:
                    unexplained.append(term)

        score = max(0, 10 - len(unexplained) * 2)
        return {
            "score": score,
            "passed": len(unexplained) == 0,
            "unexplained_terms": unexplained,
            "feedback": (
                f"다음 용어에 설명이 없습니다: {', '.join(unexplained)}"
                if unexplained
                else "모든 전문 용어가 적절히 설명됐습니다."
            ),
        }

    def check_accuracy(self, content: str) -> dict:
        """명백한 사실 오류를 탐지한다."""
        known_errors = {
            "OpenAI가 만든 Claude": "Claude는 Anthropic이 만들었습니다.",
            "Google이 만든 ChatGPT": "ChatGPT는 OpenAI가 만들었습니다.",
            "Meta가 만든 Gemini": "Gemini는 Google이 만들었습니다.",
            "Anthropic이 만든 ChatGPT": "ChatGPT는 OpenAI가 만들었습니다.",
        }
        errors = []
        for wrong, correction in known_errors.items():
            if wrong in content:
                errors.append(f"오류: '{wrong}' → {correction}")

        score = max(0, 10 - len(errors) * 5)
        return {
            "score": score,
            "passed": len(errors) == 0,
            "errors": errors,
            "feedback": (
                "\n".join(errors) if errors else "명백한 사실 오류가 없습니다."
            ),
        }

    def check_consistency(self, content: str) -> dict:
        """팀 포맷 기준을 확인한다."""
        missing = []
        for element in REQUIRED_ELEMENTS:
            if element not in content:
                missing.append(element)

        has_emoji = any(ord(c) > 127 and ord(c) > 9000 for c in content)
        if not has_emoji:
            missing.append("이모지(섹션 구분용)")

        score = max(0, 10 - len(missing) * 2)
        return {
            "score": score,
            "passed": len(missing) == 0,
            "missing_elements": missing,
            "feedback": (
                f"다음 항목이 없습니다: {', '.join(missing)}"
                if missing
                else "모든 포맷 기준을 충족합니다."
            ),
        }

    def review(self, content: str) -> dict:
        """전체 QA 검토를 실행하고 결과를 반환한다."""
        difficulty = self.check_difficulty(content)
        accuracy = self.check_accuracy(content)
        consistency = self.check_consistency(content)

        total = difficulty["score"] + accuracy["score"] + consistency["score"]
        passed = total >= PASSING_SCORE

        feedback_lines = []
        if not difficulty["passed"]:
            feedback_lines.append(f"[난이도] {difficulty['feedback']}")
        if not accuracy["passed"]:
            feedback_lines.append(f"[정확성] {accuracy['feedback']}")
        if not consistency["passed"]:
            feedback_lines.append(f"[일관성] {consistency['feedback']}")

        return {
            "passed": passed,
            "total_score": total,
            "max_score": MAX_SCORE,
            "grade": "통과" if passed else "재작성 필요",
            "details": {
                "difficulty": difficulty,
                "accuracy": accuracy,
                "consistency": consistency,
            },
            "feedback_for_educator": feedback_lines,
            "summary": (
                f"QA 점수: {total}/{MAX_SCORE} — {'✅ 통과' if passed else '⚠️ 재작성 필요'}\n"
                + ("\n".join(feedback_lines) if feedback_lines else "수정 사항 없음")
            ),
        }

    def format_report(self, review_result: dict) -> str:
        """QA 결과를 사람이 읽기 좋은 Markdown으로 포맷한다."""
        r = review_result
        d = r["details"]
        lines = [
            f"## QA 검토 결과: {r['grade']}",
            f"**총점**: {r['total_score']}/{r['max_score']}",
            "",
            f"| 항목 | 점수 | 상태 |",
            f"|------|------|------|",
            f"| 난이도 | {d['difficulty']['score']}/10 | {'✅' if d['difficulty']['passed'] else '❌'} |",
            f"| 정확성 | {d['accuracy']['score']}/10 | {'✅' if d['accuracy']['passed'] else '❌'} |",
            f"| 일관성 | {d['consistency']['score']}/10 | {'✅' if d['consistency']['passed'] else '❌'} |",
        ]
        if r["feedback_for_educator"]:
            lines += ["", "### 교육자에게 피드백"] + r["feedback_for_educator"]
        return "\n".join(lines)
