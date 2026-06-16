# AI 교육팀 (AI Education Team) — 프로젝트 플랜

> Claude Code로 구현하는 멀티 에이전트 AI 교육팀.
> 이 문서는 CLAUDE.md 또는 초기 시스템 프롬프트로 활용 가능.

---

## 팀 목표

최신 AI 트렌드와 툴을 수집하고, 누구나(중학생도) 이해할 수 있는 교육 자료로 만들어
사용자가 AI를 실질적으로 활용할 수 있도록 돕는 자동화된 교육팀을 구성한다.

---

## 에이전트 구성

### 1. 팀장 에이전트 (Team Lead)
**역할**: 사용자와의 유일한 소통 창구. 전체 워크플로우 조율.

- 사용자와 대화하며 현재 사용 중인 AI 툴 파악
- 새로운 툴 추천 및 학습 우선순위 결정
- 주간/월간 스터디 플랜 관리
- 다른 에이전트들에게 태스크 위임 및 결과 취합
- 최종 산출물을 사용자에게 전달

**스킬**: orchestration, memory, task_routing

---

### 2. 리서처 에이전트 (Researcher)
**역할**: 최신 AI 정보 수집 전담.

**현재 (Phase 1)**
- web_search로 최신 AI 뉴스, 논문, 툴 업데이트 수집
- 주요 키워드: "AI tools", "LLM updates", "prompt engineering", 한국어 AI 트렌드

**예정 (Phase 2~3)**
- RSS 피드 연결 (HuggingFace, AI Twitter/X 인플루언서, Towards Data Science 등)
- Reddit 연결 (r/MachineLearning, r/LocalLLaMA, r/artificial 등)
- 인플루언서 피드 연결 (Andrej Karpathy, Yann LeCun, Sam Altman 등)
- 직접 크롤링 + API 연결 (arXiv, ProductHunt AI 카테고리 등)

**출력**: 원자료 리포트 (제목, 출처, 요약, 중요도 태그)

**스킬**: web_search, browser, rss_reader(예정), crawling(예정)

---

### 3. 교육자 에이전트 (Educator)
**역할**: 수집된 정보를 실제 교육 자료로 변환. 팀의 핵심 산출물 생산자.

**콘텐츠 기준**
- "중학생도 이해할 수 있도록" — 전문 용어는 반드시 쉬운 비유와 함께
- 단계별 설명, 시각적 구성, 예시 중심

**산출물 종류**
- PPT 슬라이드 (Canva 또는 Google Slides 연동)
- 문서 정리 (Google Docs / Notion 형태)
- 요약 카드 (핵심만 뽑은 1페이지 요약)
- 실습 가이드 (따라하기 형식)

**현재 (Phase 1)**
- Canva MCP 연결로 슬라이드 자동 생성
- Google Workspace(Docs/Slides) 연동으로 문서화

**스킬**: canva_mcp, gdrive, file_create, formatting

---

### 4. 큐레이터 에이전트 (Curator)
**역할**: 툴 DB 관리 및 학습 자료 분류.

- 사용자가 현재 쓰는 툴 목록 유지 및 업데이트
- 새 툴 등록 시 카테고리, 난이도, 용도 태깅
- 팀장이 툴 추천 요청 시 DB 조회 및 후보 제공
- 생성된 교육 자료를 주제별/난이도별로 분류 저장

**스킬**: memory, file_read/write, search_index

---

### 5. QA 에이전트 (Quality Assurance)
**역할**: 교육자 산출물의 품질 검토.

- 난이도 체크: 실제로 중학생이 이해할 수 있는가?
- 정확성 체크: 사실 오류, 오래된 정보 없는가?
- 일관성 체크: 팀 톤앤매너, 포맷 기준 준수 여부
- 검토 통과 실패 시 교육자에게 피드백 + 재작성 요청

**스킬**: critique, fact_check, style_guide_enforcement

---

### 6. (예정) 스케줄러 에이전트 (Scheduler)
**역할**: 학습 플랜 자동화.

- 주간 스터디 커리큘럼 자동 생성
- 사용자 진도 추적
- 다음 학습 주제 자동 제안

---

### 7. (예정) 번역/로컬라이저 에이전트 (Localizer)
**역할**: 영문 원자료 한국어화.

- 리서처 원자료(대부분 영어)를 자연스러운 한국어로 변환
- 한국 AI 생태계 맥락 추가

---

## 워크플로우

```
사용자
  │
  ▼
팀장 에이전트 ──────────────────────────────┐
  │                                          │
  ├──▶ 리서처 ──▶ (원자료)                  │
  │         │                                │
  │         ▼                                │
  ├──▶ 교육자 ──▶ (PPT/문서/카드)           │
  │         │                                │
  │         ▼                                │
  │      QA 에이전트 ──(피드백)──▶ 교육자   │
  │         │ (통과)                         │
  │         ▼                                │
  └──▶ 큐레이터 ──▶ (분류/저장)             │
            │                                │
            └────────────────────────────────┘
                      최종 전달 → 사용자
```

---

## 공유 스킬 레이어

모든 에이전트가 필요에 따라 접근 가능:

| 스킬 | 설명 | Phase |
|------|------|-------|
| web_search | 웹 검색 | 현재 |
| file_create | 파일 생성/저장 | 현재 |
| memory | 이전 대화/정보 기억 | 현재 |
| browser | 브라우저 자동화 | 현재 |
| canva_mcp | Canva 슬라이드 생성 | 현재 |
| gdrive | Google Docs/Slides 연동 | 현재 |
| rss_reader | RSS 피드 구독 | Phase 2 |
| reddit_api | Reddit 크롤링 | Phase 2 |
| crawling | 커스텀 크롤러 | Phase 3 |
| influencer_feed | SNS 인플루언서 피드 | Phase 3 |

---

## 구현 단계

### Phase 1 — 뼈대 구축 (지금 시작)
- [ ] 팀장 에이전트 프롬프트 설계
- [ ] 리서처 에이전트 (web_search 기반)
- [ ] 교육자 에이전트 (Canva MCP + Google Workspace 연동)
- [ ] QA 에이전트 기본 검토 로직
- [ ] 큐레이터 에이전트 툴 DB 초기화

### Phase 2 — 정보 수집 확장
- [ ] RSS 피드 연결 (HuggingFace, arXiv 등)
- [ ] Reddit API 연동
- [ ] 스케줄러 에이전트 추가
- [ ] 번역/로컬라이저 에이전트 추가

### Phase 3 — 자동화 완성
- [ ] 인플루언서 피드 연결
- [ ] 커스텀 크롤러 구축
- [ ] 전체 파이프라인 자동 실행 (트리거 기반)

---

## 핵심 원칙

1. **중학생 기준** — 모든 교육 자료는 비전공자가 이해할 수 있어야 함
2. **팀장 단일 창구** — 사용자는 팀장하고만 대화, 나머지는 내부 처리
3. **점진적 확장** — Phase 1을 탄탄히 하고 스킬/에이전트 추가
4. **산출물 중심** — 대화로 끝내지 않고 반드시 파일/슬라이드로 남김

---

*최종 수정: 2026-06-11 | 버전: 0.1 (Phase 1 설계)*
