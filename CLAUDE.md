# 나만의 지식 베이스 — AI 교육팀

외부 API 없는 로컬 지식 관리 도구. **Claude Code 세션이 팀장 역할을 하며 에이전트들을 오케스트레이션한다.**

---

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 에이전트 구성

| 에이전트 | 파일 | 역할 |
|----------|------|------|
| 팀장 | `agents/team_lead.py` | 사용자 요청 분석 + 작업 라우팅 (Claude Code = 팀장) |
| 교육자 | `agents/educator.py` | 원자료 → 교육 문서/슬라이드 변환 |
| 큐레이터 | `agents/curator.py` | 태깅, DB 저장/검색 |
| QA | `agents/qa.py` | 난이도·정확성·일관성 3단계 품질 검토 |
| ~~리서처~~ | (사용자가 담당) | inbox에 직접 자료 입력 |

---

## 사용 흐름

### 기본 정리 (문서화)

1. 앱 **받은 문서** / **직접 메모** 탭에서 자료 입력 → `data/inbox/` 저장
2. Claude Code에 `"inbox 정리해줘"` 요청
3. Claude Code(팀장) → 교육자가 문서 작성 → QA 검토 → 큐레이터가 저장
4. 앱 **지식 베이스** 탭에서 결과 확인

### PPT 슬라이드 만들기 (Canva MCP)

1. inbox에 자료 입력 또는 지식베이스의 기존 문서 지정
2. Claude Code에 `"PPT 만들어줘"` 또는 `"슬라이드로 만들어줘"` 요청
3. 아래 **Canva 슬라이드 생성 절차** 참고

### 유튜브 영상을 커리큘럼 참고자료로 넣기

1. Claude Code에 `"이 유튜브 [링크] 커리큘럼에 넣어줘"` 요청
2. 팀장이 `reader.fetch_youtube_meta(url)`로 **제목/설명만** 추출 (영상 시청·다운로드 안 함)
3. 팀장이 제목·설명을 보고 **맞는 커리큘럼 + 적당한 주차**를 판단해 사용자에게 알림
4. `curriculum_tools.add_session_reference(curriculum, week, ref)` → `save_curriculum()`
5. 앱 **커리큘럼 > 교재**에서 참고자료 링크 확인 (클릭 시 브라우저로 열림)

### 보조 프로그램(확장·단축키·툴) 등록

1. Claude Code에 `"[툴/확장 링크] 보조 프로그램에 추가해줘"` 요청 (또는 앱 탭의 추가 폼)
2. 팀장이 `aux_tools.add_aux_program(title, description, url, category, tags, curriculum_id)` 호출
   - `category`: `크롬확장 · 단축키 · 웹툴 · 데스크톱앱 · 기타`
   - 특정 과정과 관련되면 `curriculum_id`로 연결
3. 앱 **보조 프로그램** 탭에서 분류별 카드로 관리 (열기 ↗ → 브라우저)

---

## Canva 슬라이드 생성 절차

Claude Code가 교육자 역할로 Canva MCP를 사용해 슬라이드를 생성한다.

```
1. educator.make_canva_outline(title, content) 으로 아웃라인 생성
2. mcp__claude_ai_Canva__generate-design 또는
   mcp__claude_ai_Canva__generate-design-structured 호출
3. 생성된 디자인 URL/ID를 사용자에게 전달
4. 필요하면 mcp__claude_ai_Canva__perform-editing-operations 으로 수정
```

**슬라이드 구성 기준 (교육자 규칙)**

| 슬라이드 | 내용 |
|----------|------|
| 1 | 제목 + 한 줄 요약 |
| 2~N-1 | 핵심 개념별 (불릿 3개 이하, 비유 포함) |
| N-1 | 비교표 (있는 경우) |
| N | 핵심 교훈 3가지 + 출처 |

---

## 워크플로우 다이어그램

```
사용자 (리서처)
    │ inbox에 자료 입력
    ▼
팀장 (Claude Code)
    │ 요청 분석 → route()
    ├──▶ 교육자 ──▶ 문서 또는 슬라이드 생성
    │         │
    │         ▼
    │      QA ──(피드백)──▶ 교육자 재작성
    │         │ (통과)
    │         ▼
    └──▶ 큐레이터 ──▶ DB 저장 + 태깅
                 │
                 ▼
            지식베이스 (data/knowledge/)
```

---

## 커리큘럼 관리

명령 한 번에 세션 추가·수정·삭제, 슬라이드 재생성이 되는 "살아있는 커리큘럼".
파일: `agents/curriculum.py`, `tools/curriculum_tools.py`
슬래시 커맨드: `/커리큘럼` (`.claude/commands/커리큘럼.md`)

### 커리큘럼 명령어

```
"[제목] 커리큘럼 만들어줘"
  → new_curriculum(title) + save_curriculum()
  → data/curricula/{title}.json 생성 + curriculum_db.json 인덱스 등록

"[N]주차 세션 추가: [제목]"
  → new_session(week=N, title) + curriculum["sessions"].append() + save_curriculum()

"[N]주차에 [파일명] 연결해줘"
  → data/knowledge/ 에서 파일 검색 → knowledge_refs에 경로 추가 + save_curriculum()

"[N]주차 목표 바꿔줘: [새 목표]"
  → 해당 세션 objectives 수정 + save_curriculum()

"[N]주차 활동 추가: [활동]"
  → activities 리스트에 추가 + save_curriculum()

"[N]주차 삭제해줘"
  → sessions에서 해당 week 제거 + save_curriculum()

"커리큘럼 슬라이드 업데이트해줘"
  → build_slides_data(curriculum) → save_slides() → PptxMaker로 PPTX 재생성
  → curriculum.generated 업데이트 + save_curriculum()

"커리큘럼 목록 보여줘"
  → load_curriculum_db() → 제목·세션 수·업데이트 일자 출력

"[제목] 커리큘럼 삭제해줘"
  → delete_curriculum(id) → JSON 파일 + 슬라이드 파일 삭제 + 인덱스 제거
```

### 작업 원칙

1. 매 수정 후 **반드시 `save_curriculum(curriculum)` 호출** — updated_at 자동 갱신
2. 변경 내용 요약 출력
3. 슬라이드가 커리큘럼 수정 후 재생성 안 됐으면 "슬라이드 업데이트 필요" 안내

---

## 파일 구조

| 경로 | 역할 |
|------|------|
| `app.py` | Streamlit UI (파일 업로드 + 지식 베이스 + 커리큘럼 뷰어) |
| `agents/team_lead.py` | 팀장: 요청 라우팅, 결과 요약 |
| `agents/educator.py` | 교육자: 문서/PPT 슬라이드 구조화 |
| `agents/curator.py` | 큐레이터: DB 관리, 자동 태깅, 검색 |
| `agents/qa.py` | QA: 난이도·정확성·일관성 검토 |
| `agents/curriculum.py` | 커리큘럼: 생성·관리, 슬라이드 데이터 빌드 |
| `tools/reader.py` | inbox 파일 읽기, URL → 텍스트 추출, 유튜브 메타(`fetch_youtube_meta`) |
| `tools/file_tools.py` | DB 로드/저장, 지식 파일 저장 |
| `tools/curriculum_tools.py` | 커리큘럼 CRUD, 슬라이드 JSON 저장, 세션 참고자료(`add_session_reference`) |
| `tools/aux_tools.py` | 보조 프로그램 카탈로그 CRUD (전역) |
| `tools/pptx_maker.py` | python-pptx 기반 PPT 생성 (흑백, Pretendard) |
| `data/aux_programs.json` | 보조 프로그램(확장·단축키·툴) 전역 카탈로그 |
| `data/inbox/` | 사용자가 넣은 원본 문서 |
| `data/knowledge/` | 교육자가 정리한 Markdown |
| `data/knowledge_db.json` | 지식 메타데이터 인덱스 |
| `data/curricula/` | 커리큘럼 JSON 파일들 + 슬라이드 JSON |
| `data/curricula/curriculum_db.json` | 커리큘럼 인덱스 |
| `data/outputs/` | 생성된 PPTX 파일들 |
| `skills/pptx/` | PPTX 스킬 문서 + 디자인 명세 |
| `.claude/commands/커리큘럼.md` | `/커리큘럼` 슬래시 커맨드 |

---

## Claude Code 활용 예시

```
"inbox 정리해줘"
  → 팀장이 라우팅 → 교육자 문서화 → QA → 큐레이터 저장

"PPT 만들어줘"
  → 팀장이 라우팅 → 교육자 아웃라인 → Canva MCP 슬라이드 생성

"ChatGPT 관련 자료 찾아줘"
  → 큐레이터 search("ChatGPT") → 결과 목록 반환

"지식베이스 태그 정리해줘"
  → 큐레이터가 모든 항목 재태깅

"방금 만든 문서 검토해줘"
  → QA review() → 점수 + 피드백 → 필요시 교육자 재작성

"이 유튜브 https://youtu.be/... 커리큘럼에 넣어줘"
  → fetch_youtube_meta(제목/설명만) → 팀장이 커리큘럼·주차 선택
  → add_session_reference() → save_curriculum() → 위치 요약

"https://chromewebstore... 보조 프로그램에 추가해줘"
  → aux_tools.add_aux_program(title, description, url, category)
```

---

## 품질 기준 (QA 통과 조건)

- **난이도**: 전문 용어 100% 설명됨 (비유 포함)
- **정확성**: 명백한 사실 오류 0개
- **일관성**: 출처 표기 + 이모지 섹션 구분 + 핵심 교훈 포함
- **합격 점수**: 21점 이상 / 30점 만점
