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

### 입력 소스로 지식 모으기 (RSS · 웹검색 · 전문가 SNS)

수집물은 전부 `data/inbox/`로 들어가 위 **기본 정리** 워크플로(교육자 → QA → 큐레이터)를 그대로 탄다.
워치리스트는 `data/sources.json`, 함수는 `tools/sources.py`. **새 API 키 없이** 동작한다.

```
"RSS 새로 가져와줘"
  → sources.pull_all_rss() → 신규 항목만 inbox 적재(중복 자동 방지) → "정리해줘"

"RSS 피드 추가: [URL]"
  → sources.add_rss(title, url, category)

"[주제] 최신 자료 찾아 정리해줘"
  → 팀장이 WebSearch / just-scrape 스킬로 수집
  → sources.save_research(title, url, content) → inbox → 교육자·QA·큐레이터

"[전문가/게시물 링크] 의견 정리해줘"
  → sources.fetch_social_post(url)로 og 캡션 추출 (인스타·X·링크드인은 일부만 잡힐 수 있음)
  → 캡션이 부실하면 just-scrape 스킬로 재수집 → inbox → 교육자

"[전문가] 워치리스트에 추가"
  → sources.add_expert(name, platform, url, note)
  → 유튜브 채널이면 add_expert가 RSS 피드로 자동 변환·연결(feed_url 기록) → 자동수집 대상이 됨
```

- 앱 **📡 소스** 탭에서 RSS/전문가 등록·관리 (RSS 수집은 **📰 최근 뉴스** 탭이 담당)
- 인스타/X **전체 크롤링은 하지 않는다**(ToS·차단 위험). 고른 전문가 게시물 링크만 추적한다.

#### 전문가 자동수집(RSS) 규칙 — 플랫폼별로 다름

전문가를 등록하면 플랫폼에 따라 **자동수집 여부가 갈린다.** 핵심: 자동 팔로우업은 `rss`만 돈다.

| 플랫폼 | 자동 RSS | 방식 |
|--------|:--------:|------|
| **YouTube 채널** | ✅ | `add_expert`가 channelId 추출 → `feeds/videos.xml?channel_id=`로 변환·연결 (등록 즉시) |
| **블로그**(티스토리·브런치·Medium·Substack 등) | ✅ 대체로 | `/rss`·`/feed`를 `add_rss`로 등록 |
| Instagram / X / Threads / LinkedIn | ❌ | 공식 RSS 없음 → `save_social_post(url)`로 **게시물 링크 수동 수집** |

- `sources.youtube_channel_to_feed(url)` 채널→피드 변환, `auto_collect_kind(url)` 가능 종류 판정(`youtube`/`web`/`None`).
- `sources.sync_expert_feeds()` — 유튜브인데 `feed_url` 미연결인 전문가를 일괄 RSS화(백필). **매주 월 09:15** 작업 스케줄러 `AI교육팀_전문가피드동기화`(`tools/expert_feed_sync.ps1`)가 호출 → 09:23 뉴스 브리핑 직전이라 그 회차 수집에 포함된다.
- 앱 소스 탭의 전문가 카드는 상태 배지(✅ 자동수집 중 / 🔗 RSS 연결 가능 / ⚠️ 자동수집 불가)를 RSS 연결 전까지 표시한다.

### 최근 뉴스 & 주간 브리핑

RSS 뉴스는 `inbox`(정리 대상 문서)와 분리된 **뉴스 스트림**(`data/news.json`)으로 흐른다.
`inbox`는 파일·메모·SNS·웹검색 자료 전용. 함수는 `tools/news.py`.

```
뉴스 수집 (하루 1회 자동 + 수동)
  → 앱 📰 최근 뉴스 탭 진입 시 하루 1회 자동(collect_news_daily)
  → "뉴스 수집해줘" 또는 탭의 '지금 수집' 버튼 → news.collect_news()
  → news.json에 기록만 함(개별 지식 문서로 변환하지 않음), 중복 자동 방지

"이번 주 뉴스 정리해줘"  (주간 통합 요약 — 뉴닉 스타일, 수동 트리거)
  1. news.build_digest_source(days=7) 로 최근 항목을 카테고리별로 받음
  2. **핵심 3건** 선정 → fetch_url/just-scrape로 **원문 전문 보강** → 길게(여러 문단) +
     **생각해볼 질문** 작성
  3. **자투리 10건**(전 소스 핵심) + **필요 기술/공부거리** 정리.
     자투리 blurb는 **1~2문장**으로 충실히 써서 클릭 없이도 내용이 이해되게 한다.
  4. 구조화 dict 구성:
     {title, period, intro, deep_dives[3]{emoji,title,body,question,sources[]},
      shorts[~10]{title, blurb(1~2문장), source, link}, skills[], study[]}
  5. news.save_digest(digest, ids)
     → digest_to_markdown()로 지식베이스 문서 저장 + news.json digests 등록 + in_digest=True
  6. 앱 📰 최근 뉴스 탭 상단 '이번 주 통합 요약' 카드로 렌더 (지난 브리핑은 아카이브)
```

- **매주 자동 생성**: Windows 작업 스케줄러 `AI교육팀_주간뉴스브리핑`이 매주 월요일 09:23에 `tools/weekly_digest.ps1`을 실행 → `claude -p --dangerously-skip-permissions`로 위 절차를 무인 수행(PC가 꺼져 있었으면 켜진 직후 실행). 로그: `C:\Users\chris\.claude\weekly_digest.log`. 수동 트리거(`이번 주 뉴스 정리해줘`)도 그대로 가능.

### 유튜브 영상을 커리큘럼 참고자료로 넣기

1. Claude Code에 `"이 유튜브 [링크] 커리큘럼에 넣어줘"` 요청
2. 팀장이 `reader.fetch_youtube_meta(url)`로 **제목/설명만** 추출 (영상 시청·다운로드 안 함)
3. 팀장이 제목·설명을 보고 **맞는 커리큘럼 + 적당한 강(N강)**을 판단해 사용자에게 알림
4. `curriculum_tools.add_session_reference(curriculum, week, ref)` → `save_curriculum()`
5. 앱 **커리큘럼 > 교재**에서 참고자료 링크 확인 (클릭 시 브라우저로 열림)

### 보조 프로그램(확장·단축키·툴) 등록

1. Claude Code에 `"[툴/확장 링크] 보조 프로그램에 추가해줘"` 요청 (또는 앱 탭의 추가 폼)
2. 팀장이 `aux_tools.add_aux_program(title, description, url, category, tags, curriculum_id)` 호출
   - `category`: `크롬확장 · 단축키 · 웹툴 · 데스크톱앱 · 기타`
   - 특정 과정과 관련되면 `curriculum_id`로 연결
3. 앱 **보조 프로그램** 탭에서 분류별 카드로 관리 (열기 ↗ → 브라우저)

### AI 꿀팁(사용 노하우) 등록

1. Claude Code에 `"[내용] 꿀팁 추가해줘"` 요청 (또는 앱 탭의 추가 폼)
2. 팀장이 `tips_tools.add_tip(title, body, example, category, tags, source)` 호출
   - `category`: `Claude Code · 프롬프트 · 워크플로우 · ChatGPT·제미나이 · 자동화·MCP · 토큰 절약 · 일반`
   - `example`은 바로 따라 할 명령·프롬프트(선택), `source`는 출처(선택)
3. 앱 **💡 AI 꿀팁** 탭에서 분류별 카드로 관리 (제목 + 핵심 + 사용 예시 박스 + 태그)

- 보조 프로그램(외부 도구 링크)과 분리된 **사용 노하우 컬렉션**(`data/ai_tips.json`). URL이 필요 없는 짧고 즉시 따라할 수 있는 팁 전용.
- 같은 `title`이 있으면 새로 만들지 않고 갱신한다(`add_tip`이 자동 처리).

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

"[N]강 세션 추가: [제목]"
  → new_session(week=N, title) + add_session(curriculum, ses) + save_curriculum()
  (※ 내부 week 필드/파라미터는 그대로, 사용자 표기만 "N강")

"[N]강 둘로/여러 개로 쪼개줘"   (한 강이 너무 길 때 — 교재 본문은 그대로!)
  1. 원본 강의 knowledge_refs/objectives/concepts/activities를 보고 어떻게
     나눌지 parts 명세를 만든다 (교재 .md는 절대 안 줄이고 경로만 재배분)
  2. split_session(curriculum, week=N, parts=[{title, knowledge_refs, objectives,
     concepts, activities, ...}, ...])
     → 뒤 강 week 자동 +shift, 원본 part(파트명)·duration 상속
     → 반환 dict의 cross_ref_warnings가 있으면 사용자에게 알리고 해당 참조 조정
  3. save_curriculum() → "슬라이드 업데이트 필요" 안내(build_slides_data 재생성)

"[N]강에 [파일명] 연결해줘"
  → data/knowledge/ 에서 파일 검색 → knowledge_refs에 경로 추가 + save_curriculum()

"[N]강 목표 바꿔줘: [새 목표]"
  → 해당 세션 objectives 수정 + save_curriculum()

"[N]강 활동 추가: [활동]"
  → activities 리스트에 추가 + save_curriculum()

"[N]강 삭제해줘"
  → remove_session(curriculum, week=N) (뒤 강 week 자동 -1) + save_curriculum()

"커리큘럼 슬라이드 업데이트해줘"
  → build_slides_data(curriculum) → save_slides() → 화면 슬라이드 JSON 재생성 (PPTX 생성 안 함)
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
4. **강 분량 기준**: 한 강이 슬라이드 6~9장 / 교재 H3 소제목 5~6개를 넘으면 분할을 검토한다.
   분할 시 교재 본문(.md)은 한 글자도 줄이지 않고 강 사이에 **재배분만** 한다(`split_session`).
   강을 잘게 나누면 강당 슬라이드·교재가 짧아져 학습 화면에서 슬라이드와 교재를 1:1로 대조하기 쉬워진다.

---

## 파일 구조

| 경로 | 역할 |
|------|------|
| `app.py` | Streamlit UI (보라 테마·좌측 세로 네비; 지식 베이스·뉴스·커리큘럼·AI 꿀팁·보조 프로그램·소스·에이전트 탭). 본문 마크다운 렌더는 `_escape_tilde()`로 물결표(~) 취소선 깨짐 방지(범위는 엔대시 –) |
| `agents/team_lead.py` | 팀장: 요청 라우팅, 결과 요약 |
| `agents/educator.py` | 교육자: 문서/PPT 슬라이드 구조화 |
| `agents/curator.py` | 큐레이터: DB 관리, 자동 태깅, 검색 |
| `agents/qa.py` | QA: 난이도·정확성·일관성 검토 |
| `agents/curriculum.py` | 커리큘럼: 생성·관리, 슬라이드 데이터 빌드 |
| `tools/reader.py` | inbox 파일 읽기, URL → 텍스트 추출, 유튜브 메타(`fetch_youtube_meta`) |
| `tools/sources.py` | 입력 소스 커넥터: RSS 워치리스트·전문가 SNS(`fetch_social_post`)·웹검색 적재(`save_research`)·유튜브 채널 RSS 변환(`youtube_channel_to_feed`/`sync_expert_feeds`) |
| `tools/expert_feed_sync.ps1` | 유튜브 전문가 RSS 자동 연결 백필 래퍼 (작업 스케줄러 `AI교육팀_전문가피드동기화`, 매주 월 09:15) |
| `tools/news.py` | 뉴스 스트림: 수집(`collect_news`)·열람(`recent_items`)·주간 브리핑(`build_digest_source`/`save_digest`) |
| `tools/file_tools.py` | DB 로드/저장, 지식 파일 저장 |
| `tools/curriculum_tools.py` | 커리큘럼 CRUD, 슬라이드 JSON 저장, 세션 참고자료(`add_session_reference`) |
| `tools/aux_tools.py` | 보조 프로그램 카탈로그 CRUD (전역) |
| `tools/tips_tools.py` | AI 꿀팁 카탈로그 CRUD (전역, `add_tip`/`delete_tip`/`list_tips`) |
| `tools/pptx_maker.py` | python-pptx 기반 PPT 생성 (흑백, Pretendard) |
| `data/aux_programs.json` | 보조 프로그램(확장·단축키·툴) 전역 카탈로그 |
| `data/ai_tips.json` | AI 사용 꿀팁(사용 노하우) 전역 컬렉션 |
| `data/sources.json` | 입력 소스 워치리스트(RSS·전문가 SNS) + 수집 이력(`seen`) |
| `data/news.json` | 뉴스 스트림(수집된 RSS 항목) + 주간 브리핑 인덱스(`digests`) |
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
  → fetch_youtube_meta(제목/설명만) → 팀장이 커리큘럼·강(N강) 선택
  → add_session_reference() → save_curriculum() → 위치 요약

"https://chromewebstore... 보조 프로그램에 추가해줘"
  → aux_tools.add_aux_program(title, description, url, category)

"/goal 쓰는 법 꿀팁 추가해줘"
  → tips_tools.add_tip(title, body, example, category, tags, source)
```

---

## 품질 기준 (QA 통과 조건)

- **난이도**: 전문 용어 100% 설명됨 (비유 포함)
- **정확성**: 명백한 사실 오류 0개
- **일관성**: 출처 표기 + 이모지 섹션 구분 + 핵심 교훈 포함
- **합격 점수**: 21점 이상 / 30점 만점
