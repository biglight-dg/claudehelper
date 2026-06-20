# AI 교육팀 프로젝트 — Handoff 문서

> 마지막 업데이트: 2026-06-20

> 세부 작동 규칙·워크플로는 항상 `CLAUDE.md`가 최종 기준. 이 문서는 세션 시작 시 빠른 현황 파악용 요약이다.

---

## 🟢 현재 상태

진행 중인 중단 작업 없음. 일상 요청(정리·뉴스·커리큘럼·PPT 등)을 바로 받으면 된다.

---

## 프로젝트 한 줄 요약

**외부 API 없는 로컬 지식 관리 도구.** Claude Code 세션이 **팀장** 역할로 에이전트들을 오케스트레이션해, 사용자가 모은 자료를 교육 문서·슬라이드·커리큘럼으로 정리하고 AI 지식 베이스를 쌓는다.
위치: `C:\Users\chris\Claude\Projects\claudehelper\`

---

## 아키텍처 (현재)

Claude Code = 팀장. Gemini/외부 LLM API 의존 없음(과거 구조에서 전환됨).

| 에이전트 | 파일 | 역할 |
|----------|------|------|
| 팀장 | `agents/team_lead.py` | 요청 분석 + 작업 라우팅 (Claude Code 본인) |
| 교육자 | `agents/educator.py` | 원자료 → 교육 문서/슬라이드 변환 |
| 큐레이터 | `agents/curator.py` | 태깅, DB 저장/검색 |
| QA | `agents/qa.py` | 난이도·정확성·일관성 3단계 검토 (21/30점 이상 통과) |
| 커리큘럼 | `agents/curriculum.py` | 커리큘럼 생성·관리, 슬라이드 데이터 빌드 |
| ~~리서처~~ | (사용자가 담당) | inbox에 직접 자료 입력 |

---

## 주요 기능

- **기본 정리**: inbox 자료 → 교육자 문서화 → QA → 큐레이터 저장 (`"inbox 정리해줘"`)
- **입력 소스**: RSS 워치리스트 · 웹검색 · 전문가 SNS/유튜브 (`tools/sources.py`). 유튜브 전문가는 등록 시 자동 RSS화.
- **뉴스 스트림 + 주간 브리핑**: `tools/news.py`. inbox와 분리된 `data/news.json` 스트림. 뉴닉 스타일 주간 통합 요약.
- **커리큘럼 관리**: 명령 한 번으로 강(N강) 추가·수정·삭제, 슬라이드 재생성. `/커리큘럼` 슬래시 커맨드. (용어 '주차→강' 전환, 내부 `week` 필드는 유지) + 특별 강의 special 트랙 8종.
- **유튜브 → 커리큘럼 참고자료**: `reader.fetch_youtube_meta`로 제목/설명만 추출 후 연결.
- **보조 프로그램 카탈로그**: 확장·단축키·툴 등록 (`tools/aux_tools.py`).
- **PPT 슬라이드**: Canva MCP 또는 `tools/pptx_maker.py`(python-pptx, 흑백, Pretendard).

---

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

스크립트/검증/PPTX 실행용 파이썬은 codex 런타임 사용 (PATH python엔 의존성 없음):
```
C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```
한글 출력 시 `$env:PYTHONIOENCODING="utf-8"`, here-string 한글 깨지면 임시 .py 파일로 실행.

---

## 데이터 · 경로

- `data/`는 **정션** → `G:\공유 드라이브\Chapterkorean-claude-cowork\claudehelper\data` (팀 협업용 Google 공유 드라이브). 실제 파일은 클라우드에 있음.
- 주요 데이터: `data/inbox/`(원본), `data/knowledge/`(정리본 .md), `data/knowledge_db.json`(인덱스), `data/curricula/`(커리큘럼 JSON+슬라이드), `data/news.json`, `data/sources.json`, `data/aux_programs.json`, `data/outputs/`(PPTX).
- GitHub private 버전관리: `chapterkorean/claudehelper` (`.env` 보호).

---

## 자동화 (Windows 작업 스케줄러, 모두 새 경로로 등록됨)

| 작업 | 시각 | 스크립트 |
|------|------|----------|
| `AI교육팀_전문가피드동기화` | 매주 월 09:15 | `tools/expert_feed_sync.ps1` (유튜브 전문가 RSS 백필) |
| `AI교육팀_주간뉴스브리핑` | 매주 월 09:23 | `tools/weekly_digest.ps1` (`claude -p` 무인 브리핑) |
| `AI교육팀_시트동기화` | 매주 월 09:40 | `tools/sheets_sync.ps1` (커리큘럼·지식·소스 → Google Sheets) |

로그: `C:\Users\chris\.claude\weekly_digest.log`

---

## 공유 / 배포

- 지인 10명 공유용 비밀번호 게이트 + 역할 가드(손님 = 보기·입력만), Cloudflare Tunnel 호스팅.
- 배포용 스킬: `teach-me-a-lesson`(초급자용 친절 설명, `/tl-*` 커맨드).

---

## 주의사항

- Python이 PATH에 없음 → 항상 codex 런타임 전체 경로 사용.
- `.env`를 `.env.example`로 실수로 덮어쓰지 않도록 주의.
- 인스타/X 전체 크롤링 금지(ToS·차단 위험). 고른 전문가 게시물 링크만 추적.
- 세션 시작 시 이 문서는 `scripts/handoff_hook.ps1` 훅이 자동 출력한다.
