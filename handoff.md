# AI 교육팀 프로젝트 — Handoff 문서

> 마지막 업데이트: 2026-06-12

---

## 🔴 [이어서 할 작업] 커리큘럼 6종 확장 — 중단 지점

**사용자에게 바로 안내할 것:** "지난번 커리큘럼 확장 작업을 이어서 진행할까요?" 라고 먼저 물어보기.
계획서: `C:\Users\chris\.claude\plans\reflective-swimming-fox.md`

### ✅ 완료된 부분
- **지식 파일 18개 전부 작성 완료** (`data/knowledge/20260612_*.md`) + `data/knowledge_db.json` 등록 완료
  - ② 6개(AI도구지형도/마크다운/터미널/ClaudeCode·Cowork/커스텀AI/Agent·Hook)
  - ③ 3개(프롬프트/업무마크다운/토큰·컨텍스트)
  - ④ 6개(클라이언트·서버/API/HTML·CSS/언어/Git·GitHub/용어사전)
  - ⑤ 3개(환각/저작권·개인정보/회사보안)
  - ⑥ 5개(자동화사고법/MCP/노코드/Agent설계/사례모음)
  - ① 1개(이미지·영상 트러블슈팅)
- **커리큘럼 ② "AI 업무 기초"** JSON 생성 + `curriculum_db.json` 등록 + 빌드 검증 완료(6세션, 슬라이드 29장)

### ⏳ 남은 작업 (여기서 재개)
1. 커리큘럼 JSON 생성 4개 — **③ AI 멋지게 사용하기(3주)**, **④ 개발 배경 지식(6주)**, **⑤ AI 안전·저작권·보안(3주)**, **⑥ AI 업무 자동화 실전(5주)**. 각각 세션의 `knowledge_refs`에 위 지식파일 연결 + `curriculum_db.json` 등록.
2. **① 기존 "이미지/동영상 제작 기초" 강화** — 5개 세션 `notes`(강사노트) 채우기 + 트러블슈팅 파일(`20260612_AI 이미지 영상 실전 팁과 트러블슈팅.md`)을 W2·W4·W5에 연결 + 5주차 자기점검 추가.
3. 전체 로드/빌드 검증(`load_curriculum`→`build_markdown_doc`→`build_slides_data`, 참조 누락 0 확인).
4. (선택) 슬라이드·PPTX 생성.

### 작업 방식(확정 사항)
- 대상: **비개발 실무자**, 톤: 친근+비유, QA형식(이모지섹션·비유·비교표·핵심교훈·출처) 준수
- 콘텐츠는 Claude가 전부 작성 → 사용자가 나중에 자료 모아 검토/업데이트
- "cowork" = **Claude Cowork**. Cowork/GPTs/Gem/요금 등 변동잦은 부분은 `⚠️ 검토 요청` 표시해둠
- 커리큘럼 추가 = ①지식.md ②knowledge_db.json ③커리큘럼.json ④curriculum_db.json 4개 레이어. ② "AI 업무 기초.json"을 템플릿으로 참고.
- 검증 시 파이썬: `C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`, 한글출력 시 `$env:PYTHONIOENCODING="utf-8"`, here-string 한글 깨지므로 임시 .py 파일로 실행

---

## 프로젝트 한 줄 요약

최신 AI 트렌드 수집 + 사용자가 요청하는 기본 개념/인사이트 정리 → 나만의 AI 지식 베이스를 자동으로 쌓아주는 멀티 에이전트 시스템. `C:\Users\chris\claudehelper\` 에 위치.

---

## 현재 완성된 것 (Phase 1 완료)

### 에이전트 5개
| 에이전트 | 파일 | 역할 |
|----------|------|------|
| 팀장 | `agents/team_lead.py` | 사용자 소통 + Gemini function calling 오케스트레이션 |
| 리서처 | `agents/researcher.py` | Google Custom Search로 최신 AI 뉴스 수집 |
| 교육자 | `agents/educator.py` | 뉴스/개념을 교육 자료(doc/card/slide)로 변환 |
| QA | `agents/qa.py` | 난이도·정확성·일관성 3단계 품질 검토 |
| 큐레이터 | `agents/curator.py` | knowledge_db.json에 자료 저장/검색 |

### UI
- `app.py` — Streamlit 브라우저 UI (localhost:8501)
- 사이드바: 빠른 시작 버튼 6개 + 저장된 자료 목록
- 처리 중 어떤 에이전트가 일하는지 실시간 표시

### 데이터
- `data/knowledge_db.json` — AI 툴 DB(5개 시드) + 자료 인덱스
- `data/outputs/` — 생성된 Markdown 교육 자료 저장

---

## 기술 스택 및 주요 결정사항

| 항목 | 결정 | 이유 |
|------|------|------|
| AI API | Gemini 2.0 Flash (`google-genai`) | 무료 (1,500회/일) — Anthropic API 대신 선택 |
| 웹 검색 | Google Custom Search API | 무료 100회/일 |
| UI | Streamlit | 빠른 구축, 채팅 UI 내장 |
| 저장 | 로컬 JSON + Markdown | 단순성 우선 |
| 팀장 모델 | gemini-2.0-flash | function calling 지원 |

---

## 환경 변수 (.env)

```
GEMINI_API_KEY=AQ.Ab8R...   ← Google AI Studio (aistudio.google.com/apikey)
GOOGLE_API_KEY=AIzaSy...    ← Google Cloud Console Custom Search용
GOOGLE_CSE_ID=173ed...      ← Programmable Search Engine ID
```

---

## 실행 방법

```powershell
# Streamlit UI (브라우저)
C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m streamlit run C:\Users\chris\claudehelper\app.py

# 터미널 CLI (대안)
C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe C:\Users\chris\claudehelper\main.py
```

---

## 다음 작업 (Phase 2 예정)

- [ ] RSS 피드 연결 (HuggingFace, arXiv)
- [ ] Reddit API 연동 (r/MachineLearning 등)
- [ ] 스케줄러 에이전트 (주간 학습 플랜 자동 생성)
- [ ] 번역/로컬라이저 에이전트 (영문 원자료 한국어화)
- [ ] Canva MCP 연동으로 슬라이드 실제 생성

---

## 알려진 이슈 / 주의사항

- Python이 PATH에 없어서 항상 전체 경로 사용 필요
- `.env` 파일을 `.env.example`로 실수로 수정하는 일 없도록 주의
- Google Custom Search 무료 한도: 하루 100회
