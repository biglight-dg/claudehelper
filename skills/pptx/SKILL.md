# PPTX Skill

PowerPoint 프레젠테이션을 처음부터 생성하거나 기존 파일을 편집하는 스킬.

## 생성 방법 (tools/pptx_maker.py 사용)

이 프로젝트에서는 python-pptx 기반의 `tools/pptx_maker.py`로 PPT를 생성한다.

```python
from tools.pptx_maker import PptxMaker

maker = PptxMaker(title="발표 제목")
maker.add_title_slide("제목", "부제목")
maker.add_content_slide("섹션명", "슬라이드 제목", ["불릿1", "불릿2", "불릿3"])
maker.add_comparison_slide("비교 제목", "왼쪽 항목", [...], "오른쪽 항목", [...])
maker.add_summary_slide(["교훈1", "교훈2", "교훈3"], "출처")
path = maker.save("파일명")
```

## 편집 방법 (XML 워크플로우)

기존 .pptx 파일 수정 시:

```bash
# 1. 압축 해제
Expand-Archive file.pptx unpacked/ -Force

# 2. XML 편집 (Edit 도구 사용)

# 3. 슬라이드 추가
python skills/pptx/scripts/add_slide.py unpacked/ slide1.xml

# 4. 정리
python skills/pptx/scripts/clean.py unpacked/

# 5. 재압축
Compress-Archive unpacked/* output.pptx
```

## QA 프로세스

생성 후 `skills/pptx/scripts/thumbnail.py`로 시각적 확인 (LibreOffice + pdftoppm 필요).

## 설계 원칙

- 하나의 슬라이드 = 하나의 핵심 메시지
- 불릿은 최대 3개
- 이 프로젝트의 디자인 기준은 `skills/pptx/design_spec.md` 참고
