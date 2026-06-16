# AI 영상 제작 기초 — Image-to-Video 워크플로우

## 한 줄 소개

스토리보드 이미지를 AI로 만들고 영상으로 바꾼다 — 15~30초 광고 영상을 혼자 만드는 방법.

---

## 4주차 커리큘럼 개요

| 주차 | 주제 |
|------|------|
| 1주차 | AI 이미지 생성 기초 (이미지→스토리보드) |
| 2주차 | AI 영상 제작 기초 (스토리보드→영상) |
| 3주차 | 편집/합성 기초 (영상 편집 + 사운드) |
| 4주차 | 팀 프로젝트 발표 (제작 + 상영) |

---

## Image-to-Video 워크플로우

`
아이디어 → AI 이미지(스토리보드 생성) → 영상 클립 생성 → 영상 편집 → 최종 결과물
`

### 추천 도구

| 도구 | 용도 |
|------|------|
| Google Flow | 이미지/영상 생성 |
| Kling AI | 프롬프트 기반 영상 생성 |
| Freepik / Nano Banana | 보조 이미지 생성 |
| HiggsField | 고품질 영상 |
| Veo3 | Google 최신 영상 AI |
| ComfyUI | 오픈소스 고급 워크플로우 |
| CapCut | 편집 (타임라인/자막/BGM) |

---

## Kling AI 프롬프트 5칸 공식

| 칸 | 항목 | 예시 |
|----|------|------|
| ① | **피사체 + 동작** | 하얀 캔들이 타오르는 모습 |
| ② | **카메라 무브** | dolly in |
| ③ | **속도 + 분위기** | slow motion, cinematic |
| ④ | **재생시간** | 5초 |
| ⑤ | **끝 상태** | 불꽃이 크게 흔들리며 마무리 |

### 카메라 무브 종류

| 종류 | 설명 |
|------|------|
| static | 고정 |
| dolly in / out | 앞뒤로 이동 |
| pan left / right | 좌우 수평 |
| tilt up / down | 상하 각도 |
| crane up / down | 위아래 이동 |
| orbit | 피사체 주위 회전 |

### 속도 키워드
- slow motion, smooth, time-lapse

### 분위기 키워드
- cinematic, luxurious, warm, moody

---

## 실습 씬 예시

### 캔들 씬
`
Wax candle with a burning wick, placed on a wooden table,
dolly in, slow motion, cinematic, 5 seconds,
끝: 불꽃이 흔들리며 마무리
`

### 텀블러 씬
`
Coffee tumbler on a misty morning desk,
pan right, smooth, warm mood, 4 seconds,
끝: 텀블러 전면 클로즈업
`

### 인물 씬
`
20대 한국인 여성이 카페에서 커피를 마시는 모습,
orbit, slow motion, moody, 6 seconds,
끝: 미소 짓는 표정 클로즈업
`

---

## GPT 활용 스토리보드 자동 생성

GPT에게 씬 묘사를 넘기면 스토리보드 프롬프트를 자동으로 작성해준다.

---

## CapCut 편집 기본 흐름

1. 영상 클립 타임라인 배치
2. 트랜지션 추가 (cut / fade)
3. 자막 삽입
4. BGM 추가
5. MP4 출력 (15~30초)

---

> 출처: AI영상_제작_2회차_김도희.pdf / 강사: 김도희
