# PptxGenJS Reference (Node.js 대안)

이 프로젝트는 Python 기반이므로 기본적으로 `tools/pptx_maker.py` (python-pptx)를 사용한다.
Node.js 환경이 있다면 pptxgenjs를 쓸 수 있다.

---

## Core Setup

```javascript
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();

pres.layout = "LAYOUT_16x9";
pres.author = "AI 교육팀";
pres.title = "프레젠테이션 제목";

await pres.writeFile({ fileName: "output.pptx" });
```

## Text

```javascript
slide.addText("제목", {
  x: 0.5, y: 0.5, w: 9, h: 1.2,
  fontSize: 36, bold: true,
  fontFace: "Pretendard",
  color: "000000",
});
```

## Shapes (divider line)

```javascript
slide.addShape(pptxgen.ShapeType.line, {
  x: 0.5, y: 1.5, w: 9, h: 0,
  line: { color: "CCCCCC", width: 1 },
});
```

## Bullets

```javascript
slide.addText([
  { text: "항목 1", options: { bullet: true, breakLine: true } },
  { text: "항목 2", options: { bullet: true, breakLine: true } },
], {
  x: 0.5, y: 2.0, w: 9, h: 3,
  fontSize: 20, fontFace: "Pretendard", color: "222222",
});
```

## Critical Rules

- 색상에 "#" 붙이지 말 것 → `"000000"` (O), `"#000000"` (X)
- 8자리 색상 문자열 사용 금지 (불투명도는 별도 처리)
- option 객체를 여러 함수에서 재사용하지 말 것 (파일 손상)
