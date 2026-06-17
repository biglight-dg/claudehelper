from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from tools.file_tools import load_db, save_knowledge_file
from tools.reader import read_inbox_files, fetch_url, save_to_inbox, read_pdf
from tools.sources import (
    load_sources, add_rss, remove_rss, add_expert, remove_expert,
    pull_all_rss, save_social_post,
)
from tools.curriculum_tools import (
    load_curriculum_db, load_curriculum, load_slides,
    build_markdown_doc, build_session_doc,
)
from tools.aux_tools import (
    load_aux_db, add_aux_program, delete_aux_program, CATEGORIES,
)
from agents.curator import Curator
from agents.qa import QA

st.set_page_config(
    page_title="나만의 지식 베이스",
    page_icon="📚",
    layout="wide",
)

INBOX_DIR = Path("data/inbox")
KNOWLEDGE_DIR = Path("data/knowledge")


# 16:9 래퍼: aspect-ratio로 비율 고정, 내부 절대 위치
WRAP_OPEN = (
    '<div style="width:100%;aspect-ratio:16/9;position:relative;'
    'overflow:hidden;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.12);">'
    '<div style="position:absolute;inset:0;display:flex;flex-direction:column;">'
)
WRAP_CLOSE = "</div></div>"


def _slide_inner_html(slide: dict) -> str:
    """슬라이드 타입별 내부 패널 HTML(래퍼 제외)을 문자열로 반환한다."""
    stype = slide.get("type", "content")

    if stype == "title":
        inner = (
            '<div style="background:#111;width:100%;height:100%;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center;padding:6%;">'
            f'<div style="font-size:clamp(2rem,4vw,3.4rem);font-weight:800;'
            f'color:#fff;text-align:center;line-height:1.3;margin-bottom:1.2rem;">'
            f'{slide.get("title","")}</div>'
            '<div style="width:100px;height:3px;background:#555;margin-bottom:1.2rem;"></div>'
            f'<div style="font-size:clamp(1rem,1.8vw,1.6rem);color:#aaa;text-align:center;">'
            f'{slide.get("subtitle","")}</div>'
            '<div style="position:absolute;bottom:4%;right:4%;font-size:0.9rem;color:#555;">AI 교육팀</div>'
            '</div>'
        )
        return inner

    elif stype == "part_divider":
        weeks = slide.get("weeks", "")
        inner = (
            '<div style="background:#111;width:100%;height:100%;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center;padding:6%;">'
            f'<div style="font-size:clamp(2.6rem,6vw,4.6rem);font-weight:800;'
            f'color:#fff;text-align:center;letter-spacing:0.05em;margin-bottom:1rem;">'
            f'{slide.get("label","")}</div>'
            '<div style="width:100px;height:3px;background:#555;margin-bottom:1rem;"></div>'
            f'<div style="font-size:clamp(1.2rem,2.4vw,2.2rem);color:#ddd;text-align:center;'
            f'line-height:1.3;margin-bottom:0.6rem;">{slide.get("title","")}</div>'
            f'<div style="font-size:clamp(0.95rem,1.6vw,1.4rem);color:#888;">{weeks}</div>'
            '</div>'
        )
        return inner

    elif stype == "divider":
        inner = (
            '<div style="background:#fff;width:100%;height:100%;display:flex;'
            'align-items:center;padding:5% 7%;">'
            '<div style="width:8px;height:62%;background:#000;border-radius:4px;'
            'margin-right:5%;flex-shrink:0;"></div>'
            '<div>'
            f'<div style="font-size:clamp(3.5rem,9vw,7rem);font-weight:800;color:#e8e8e8;'
            f'line-height:1;margin-bottom:0.3rem;">{slide.get("number","")}</div>'
            f'<div style="font-size:clamp(1.6rem,3.4vw,2.8rem);font-weight:700;color:#111;">'
            f'{slide.get("section","")}</div>'
            '</div></div>'
        )
        return inner

    elif stype == "content":
        bullets_html = "".join(
            f'<div style="display:flex;align-items:flex-start;">'
            f'<span style="color:#555;margin-right:0.7rem;flex-shrink:0;'
            f'font-size:clamp(1.15rem,2.7vw,2.2rem);line-height:1.3;">▪</span>'
            f'<span style="font-size:clamp(1.15rem,2.7vw,2.2rem);color:#222;line-height:1.3;">{b}</span>'
            f'</div>'
            for b in slide.get("bullets", [])
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:5% 7%;display:flex;flex-direction:column;">'
            f'<div style="font-size:clamp(0.9rem,1.4vw,1.2rem);color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.4rem;">{slide.get("section","")}</div>'
            '<div style="height:1px;background:#e0e0e0;margin-bottom:0.8rem;"></div>'
            f'<div style="font-size:clamp(1.6rem,3.6vw,3rem);font-weight:800;color:#000;'
            f'margin-bottom:1.2rem;line-height:1.2;">{slide.get("title","")}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly;'
            f'overflow:hidden;">{bullets_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "cards":
        variant = slide.get("variant", "number")
        items = slide.get("items", [])
        cards_html = "".join(
            '<div style="display:flex;align-items:stretch;background:#f2f2f2;border:1px solid #ccc;'
            'border-radius:8px;flex:1;min-height:0;overflow:hidden;">'
            '<div style="background:#111;color:#fff;font-weight:800;display:flex;align-items:center;'
            'justify-content:center;min-width:clamp(2.6rem,4.5vw,4rem);'
            f'font-size:clamp(1.3rem,2.6vw,2.2rem);">{(i+1) if variant=="number" else "•"}</div>'
            '<div style="display:flex;align-items:center;padding:0.4rem 1.1rem;'
            f'font-size:clamp(1.1rem,2.5vw,2.1rem);color:#222;line-height:1.25;">{item}</div>'
            '</div>'
            for i, item in enumerate(items)
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:5% 7%;display:flex;flex-direction:column;">'
            f'<div style="font-size:clamp(0.9rem,1.4vw,1.2rem);color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.4rem;">{slide.get("section","")}</div>'
            '<div style="height:1px;background:#e0e0e0;margin-bottom:0.8rem;"></div>'
            f'<div style="font-size:clamp(1.6rem,3.6vw,3rem);font-weight:800;color:#000;'
            f'margin-bottom:1rem;line-height:1.2;">{slide.get("title","")}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:0.7rem;min-height:0;">{cards_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "flow":
        steps = slide.get("steps", [])
        boxes = []
        for idx, step in enumerate(steps):
            items_html = "".join(
                f'<div style="font-size:clamp(0.95rem,1.8vw,1.5rem);color:#222;'
                f'margin-bottom:0.5rem;line-height:1.3;">· {it}</div>'
                for it in step.get("items", [])
            )
            boxes.append(
                '<div style="flex:1;background:#f2f2f2;border:2px solid #111;border-radius:10px;'
                'padding:1.1rem 0.9rem;display:flex;flex-direction:column;min-width:0;">'
                '<div style="font-weight:800;text-align:center;color:#000;'
                'font-size:clamp(1.2rem,2.4vw,2rem);margin-bottom:0.9rem;">'
                f'{step.get("label","")}</div>'
                f'<div style="flex:1;">{items_html}</div></div>'
            )
            if idx < len(steps) - 1:
                boxes.append(
                    '<div style="display:flex;align-items:center;color:#777;'
                    'font-size:clamp(1.5rem,3vw,2.6rem);padding:0 0.35rem;">▶</div>'
                )
        boxes_html = "".join(boxes)
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:5% 7%;display:flex;flex-direction:column;">'
            f'<div style="font-size:clamp(0.9rem,1.4vw,1.2rem);color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.4rem;">{slide.get("section","")}</div>'
            '<div style="height:1px;background:#e0e0e0;margin-bottom:0.8rem;"></div>'
            f'<div style="font-size:clamp(1.6rem,3.6vw,3rem);font-weight:800;color:#000;'
            f'margin-bottom:1rem;line-height:1.2;">{slide.get("title","")}</div>'
            f'<div style="flex:1;display:flex;align-items:stretch;min-height:0;">{boxes_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "table":
        headers = slide.get("headers", [])
        rows = slide.get("rows", [])
        header_cells = "".join(
            f'<th style="background:#111;color:#fff;padding:11px 14px;font-size:clamp(1rem,1.8vw,1.6rem);'
            f'font-weight:700;text-align:left;white-space:nowrap;">{h}</th>'
            for h in headers
        )
        body_rows = ""
        for i, row in enumerate(rows):
            bg = "#fff" if i % 2 == 0 else "#f6f6f6"
            cells = "".join(
                f'<td style="padding:9px 14px;font-size:clamp(0.95rem,1.6vw,1.45rem);'
                f'color:#222;border-bottom:1px solid #eee;line-height:1.25;">{row[j] if j < len(row) else ""}</td>'
                for j in range(len(headers))
            )
            body_rows += f'<tr style="background:{bg};">{cells}</tr>'
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:4% 6%;display:flex;flex-direction:column;">'
            f'<div style="font-size:clamp(0.9rem,1.4vw,1.2rem);color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.4rem;">{slide.get("section","")}</div>'
            '<div style="height:1px;background:#e0e0e0;margin-bottom:0.7rem;"></div>'
            f'<div style="font-size:clamp(1.4rem,3vw,2.4rem);font-weight:800;color:#000;margin-bottom:0.8rem;">'
            f'{slide.get("title","")}</div>'
            '<div style="flex:1;overflow:auto;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr>{header_cells}</tr></thead>'
            f'<tbody>{body_rows}</tbody>'
            '</table></div></div>'
        )
        return inner

    elif stype == "comparison":
        left_html = "".join(
            f'<div style="margin-bottom:0.5rem;font-size:clamp(1rem,1.9vw,1.6rem);color:#222;">'
            f'▪ {item}</div>'
            for item in slide.get("left_items", [])
        )
        right_html = "".join(
            f'<div style="margin-bottom:0.5rem;font-size:clamp(1rem,1.9vw,1.6rem);color:#222;">'
            f'▪ {item}</div>'
            for item in slide.get("right_items", [])
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:5% 7%;display:flex;flex-direction:column;">'
            f'<div style="font-size:clamp(1.4rem,3vw,2.4rem);font-weight:800;color:#000;margin-bottom:0.8rem;">'
            f'{slide.get("title","")}</div>'
            '<div style="height:1px;background:#e0e0e0;margin-bottom:0.8rem;"></div>'
            '<div style="display:grid;grid-template-columns:1fr 1px 1fr;gap:0 1.5rem;flex:1;">'
            f'<div><div style="font-weight:700;margin-bottom:0.6rem;font-size:clamp(1.1rem,2vw,1.7rem);">'
            f'{slide.get("left_label","")}</div>{left_html}</div>'
            '<div style="background:#e0e0e0;"></div>'
            f'<div><div style="font-weight:700;margin-bottom:0.6rem;font-size:clamp(1.1rem,2vw,1.7rem);">'
            f'{slide.get("right_label","")}</div>{right_html}</div>'
            '</div></div>'
        )
        return inner

    elif stype == "summary":
        lessons_html = "".join(
            f'<div style="display:flex;align-items:flex-start;margin-bottom:0.7rem;">'
            f'<span style="font-weight:800;color:#000;margin-right:0.7rem;flex-shrink:0;'
            f'font-size:clamp(1.1rem,2vw,1.7rem);">{i+1}.</span>'
            f'<span style="font-size:clamp(1.05rem,2vw,1.6rem);color:#222;line-height:1.3;">{lesson}</span>'
            f'</div>'
            for i, lesson in enumerate(slide.get("lessons", []))
        )
        source = slide.get("source", "")
        inner = (
            '<div style="background:#f5f5f5;width:100%;height:100%;padding:5% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:clamp(1.5rem,3vw,2.4rem);font-weight:800;color:#000;margin-bottom:0.5rem;">'
            '커리큘럼 요약</div>'
            '<div style="height:1px;background:#ccc;margin-bottom:1rem;"></div>'
            f'<div style="flex:1;overflow:hidden;">{lessons_html}</div>'
            f'<div style="font-size:0.95rem;color:#999;margin-top:0.5rem;">출처: {source}</div>'
            '</div>'
        )
        return inner

    return ""


def _render_slide(slide: dict) -> None:
    """슬라이드를 16:9 고정 비율 HTML로 렌더링한다."""
    st.markdown(WRAP_OPEN + _slide_inner_html(slide) + WRAP_CLOSE, unsafe_allow_html=True)


# 클라이언트 덱: 좌우 화살표 이동 + 전체화면(브라우저 Fullscreen API)
_DECK_TEMPLATE = """
<style>
  *{box-sizing:border-box;}
  html,body{margin:0;padding:0;background:transparent;}
  #root{font-family:-apple-system,'Segoe UI',sans-serif;}
  #stage{display:flex;align-items:center;justify-content:center;}
  .slide{width:min(100%, calc((100vh - 64px) * 16 / 9));}
  .frame{position:relative;width:100%;aspect-ratio:16/9;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.15);display:flex;flex-direction:column;}
  #bar{display:flex;align-items:center;justify-content:center;gap:0.6rem;margin-top:0.6rem;}
  #bar button{border:1px solid #ccc;background:#fff;border-radius:6px;padding:0.3rem 0.85rem;
              cursor:pointer;font-size:0.9rem;color:#222;}
  #bar button:hover{background:#f2f2f2;}
  #bar button:disabled{opacity:0.4;cursor:default;}
  #counter{color:#666;font-size:0.9rem;min-width:74px;text-align:center;}
  #root.fs{background:#000;display:flex;flex-direction:column;justify-content:center;height:100vh;}
  #root.fs #stage{flex:1;}
  #root.fs .slide{width:min(100vw, calc((100vh - 64px) * 16 / 9));}
  #root.fs #counter{color:#bbb;}
  #root.fs #bar button{background:#222;border-color:#444;color:#eee;}
  #root.fs #bar{padding-bottom:0.6rem;}
</style>
<div id="root">
  <div id="stage">__SLIDES__</div>
  <div id="bar">
    <button id="prev">← 이전</button>
    <span id="counter"></span>
    <button id="next">다음 →</button>
    <button id="fs">⛶ 전체화면</button>
  </div>
</div>
<script>
(function(){
  var n = __N__, i = 0;
  var root = document.getElementById('root');
  var slides = root.querySelectorAll('.slide');
  var counter = document.getElementById('counter');
  var prev = document.getElementById('prev');
  var next = document.getElementById('next');
  var fs = document.getElementById('fs');
  function show(){
    for (var k=0;k<slides.length;k++){ slides[k].style.display = (k===i?'flex':'none'); }
    counter.textContent = (i+1)+' / '+n;
    prev.disabled = (i===0);
    next.disabled = (i===n-1);
  }
  prev.onclick = function(){ if(i>0){ i--; show(); } };
  next.onclick = function(){ if(i<n-1){ i++; show(); } };

  // srcdoc iframe은 부모와 동일 출처 → iframe 요소 자체를 전체화면으로(상위 문서 권한 사용)
  function frameEl(){ try { return window.frameElement; } catch(e){ return null; } }
  function parentDoc(){ try { return window.parent.document; } catch(e){ return null; } }
  function fsElement(){
    var pd = parentDoc();
    return (pd && pd.fullscreenElement) || document.fullscreenElement || null;
  }
  function syncFsClass(){
    var fe = frameEl();
    var on = !!fsElement() && (fsElement() === fe || fsElement() === root);
    root.classList.toggle('fs', on);
  }
  fs.onclick = function(){
    var cur = fsElement();
    if (cur){
      var pd = parentDoc();
      if (pd && pd.exitFullscreen) pd.exitFullscreen();
      else if (document.exitFullscreen) document.exitFullscreen();
      return;
    }
    var target = frameEl() || root;
    if (target.requestFullscreen){
      var p = target.requestFullscreen();
      if (p && p.catch) p.catch(function(){ if (root.requestFullscreen) root.requestFullscreen(); });
    }
  };
  var pd = parentDoc();
  if (pd) pd.addEventListener('fullscreenchange', syncFsClass);
  document.addEventListener('fullscreenchange', syncFsClass);

  document.addEventListener('keydown', function(e){
    if (e.key==='ArrowLeft'){ prev.onclick(); }
    else if (e.key==='ArrowRight'){ next.onclick(); }
  });
  show();
})();
</script>
"""


def _render_slide_deck(slides: list[dict], height: int = 560) -> None:
    """슬라이드 목록을 화살표 이동 + 전체화면 가능한 클라이언트 덱으로 렌더링한다."""
    boxes = []
    for i, s in enumerate(slides):
        disp = "flex" if i == 0 else "none"
        boxes.append(
            f'<div class="slide" style="display:{disp};">'
            f'<div class="frame">{_slide_inner_html(s)}</div>'
            f'</div>'
        )
    html = _DECK_TEMPLATE.replace("__SLIDES__", "".join(boxes)).replace("__N__", str(len(slides)))
    components.html(html, height=height, scrolling=False)


def _inbox_files() -> list[Path]:
    """inbox 안의 지원 파일 목록을 반환한다."""
    if not INBOX_DIR.exists():
        return []
    return sorted(
        list(INBOX_DIR.glob("*.txt")) + list(INBOX_DIR.glob("*.md")) + list(INBOX_DIR.glob("*.pdf"))
    )


def _is_processed(file_path: Path, db_items: list[dict]) -> bool:
    """inbox 파일이 지식 베이스에 정리돼 반영됐는지 휴리스틱으로 판정한다(표시용)."""
    stem = file_path.stem.lower().strip()
    if not stem:
        return False
    for item in db_items:
        title = item.get("title", "").lower()
        path = item.get("path", "").lower()
        if stem in title or title in stem or stem in path:
            return True
    return False


# ── 전역 헤더 ──────────────────────────────────────────────────
st.title("📚 나만의 지식 베이스")
st.caption("문서를 모아두면 Claude Code(팀장)가 교육 자료로 정리해 줍니다.")

# ── 사이드바: 상시 안내 ────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧭 사용 흐름")
    st.markdown(
        "**①** 문서·메모 입력  \n"
        "**②** Claude Code에 `\"정리해줘\"`  \n"
        "**③** 지식 베이스에서 확인"
    )
    st.divider()
    st.markdown("### 💬 자주 쓰는 명령어")
    st.code(
        "inbox 정리해줘\n"
        "PPT 만들어줘\n"
        "[제목] 커리큘럼 만들어줘\n"
        "방금 만든 문서 검토해줘\n"
        "ChatGPT 관련 자료 찾아줘",
        language="text",
    )
    st.divider()
    _sb_inbox = _inbox_files()
    _sb_db_items = load_db().get("items", [])
    _sb_pending = sum(1 for f in _sb_inbox if not _is_processed(f, _sb_db_items))
    sb_c1, sb_c2 = st.columns(2)
    sb_c1.metric("inbox 대기", _sb_pending)
    sb_c2.metric("지식 문서", len(_sb_db_items))


tab_inbox, tab_sources, tab_memo, tab_kb, tab_cur, tab_aux, tab_agents = st.tabs(
    ["📥 받은 문서", "📡 소스", "✏️ 직접 메모", "📚 지식 베이스", "📋 커리큘럼",
     "🧰 보조 프로그램", "🤖 에이전트"]
)

# ── 탭 1: 받은 문서 ────────────────────────────────────────────
with tab_inbox:
    st.markdown("## 📥 받은 문서")
    st.caption("파일을 올리거나 링크를 입력하면 inbox에 저장됩니다. 그 다음 Claude Code에 '정리해줘'라고 요청하세요.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 파일 업로드")
        st.caption("txt, md, pdf 파일을 지원합니다. 스캔 PDF(이미지 기반)는 텍스트 추출이 안 될 수 있어요.")
        uploaded = st.file_uploader("txt / md / pdf 파일", type=["txt", "md", "pdf"], accept_multiple_files=True)
        if st.button("inbox에 저장", key="upload_btn") and uploaded:
            saved, failed = [], []
            for f in uploaded:
                try:
                    if f.name.lower().endswith(".pdf"):
                        # PDF는 임시 저장 후 텍스트 추출
                        tmp_path = INBOX_DIR / f.name
                        INBOX_DIR.mkdir(parents=True, exist_ok=True)
                        tmp_path.write_bytes(f.read())
                        extracted = read_pdf(tmp_path)
                        tmp_path.unlink()  # 원본 PDF 삭제, 텍스트만 저장
                        txt_name = f.name.rsplit(".", 1)[0] + ".txt"
                        header = f"[원본 파일: {f.name}]\n\n"
                        save_to_inbox(txt_name, header + extracted)
                        if extracted.startswith("[스캔 PDF"):
                            failed.append(f.name)
                        else:
                            saved.append(f.name)
                    else:
                        content = f.read().decode("utf-8", errors="replace")
                        save_to_inbox(f.name, content)
                        saved.append(f.name)
                except Exception as e:
                    st.error(f"{f.name} 저장 실패: {e}")
            if saved:
                st.success(f"{len(saved)}개 파일 저장 완료: {', '.join(saved)}")
            if failed:
                st.warning(f"스캔 PDF라 텍스트 추출 실패 (내용 직접 입력 필요): {', '.join(failed)}")
            st.rerun()

    with col2:
        st.markdown("### URL 가져오기")
        url_input = st.text_input("링크를 입력하세요", placeholder="https://...")
        if st.button("가져오기", key="url_btn") and url_input.strip():
            with st.spinner("페이지 읽는 중..."):
                result = fetch_url(url_input.strip())
            if result["content"].startswith("[가져오기 실패"):
                st.error(result["content"])
            else:
                filename = result["title"][:50].replace("/", "_") + ".txt"
                header = f"출처: {result['url']}\n제목: {result['title']}\n\n"
                save_to_inbox(filename, header + result["content"])
                st.success(f"저장 완료: {filename}")
                st.rerun()

    st.divider()
    st.markdown("### inbox 파일 목록")
    inbox_files = _inbox_files()
    db_items = load_db().get("items", [])
    if inbox_files:
        for f in inbox_files:
            status_chip = "✅ 정리됨" if _is_processed(f, db_items) else "⏳ 대기"
            with st.expander(f"{f.name}  ·  {status_chip}"):
                if f.suffix.lower() == ".pdf":
                    st.caption("PDF 파일 — 아래 버튼으로 텍스트 미리보기")
                    prev_key = f"pdfprev_{f.name}"
                    if st.button("텍스트 추출 미리보기", key=f"prev_{f.name}"):
                        extracted = read_pdf(f)
                        st.session_state[prev_key] = (
                            extracted[:800] + ("..." if len(extracted) > 800 else "")
                        )
                    if prev_key in st.session_state:
                        st.text(st.session_state[prev_key])
                else:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    st.text(content[:500] + ("..." if len(content) > 500 else ""))

                # 삭제: 2단계 확인
                confirm_key = f"confirm_del_{f.name}"
                if st.session_state.get(confirm_key):
                    st.warning("⚠️ 정말 삭제할까요? 되돌릴 수 없습니다.")
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("삭제 확정", key=f"delyes_{f.name}", type="primary"):
                        f.unlink()
                        st.session_state.pop(confirm_key, None)
                        st.session_state.pop(f"pdfprev_{f.name}", None)
                        st.rerun()
                    if c_no.button("취소", key=f"delno_{f.name}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                else:
                    if st.button("삭제", key=f"del_{f.name}"):
                        st.session_state[confirm_key] = True
                        st.rerun()
    else:
        st.info("inbox가 비어 있습니다. 파일을 올리거나 URL을 입력해 보세요.")

# ── 탭: 소스 (RSS · 전문가 SNS) ─────────────────────────────────
with tab_sources:
    st.markdown("## 📡 소스")
    st.caption(
        "RSS 피드와 전문가 SNS를 등록해 자료를 inbox로 자동 수집합니다. "
        "웹 검색이나 SNS 본문 정리는 Claude Code에 '정리해줘'라고 요청하면 더 안정적입니다."
    )

    src = load_sources()

    col_rss, col_sns = st.columns(2)

    # ── RSS 피드 ──
    with col_rss:
        st.markdown("### 📰 RSS 피드")
        with st.form("add_rss_form", clear_on_submit=True):
            rss_title = st.text_input("피드 이름", placeholder="예: 한 AI 블로그")
            rss_url = st.text_input("피드 URL", placeholder="https://.../feed.xml")
            rss_cat = st.text_input("분류 (선택)", placeholder="예: 뉴스 / 연구")
            if st.form_submit_button("피드 추가") and rss_url.strip():
                add_rss(rss_title or rss_url, rss_url, rss_cat)
                st.success(f"피드 추가됨: {rss_title or rss_url}")
                st.rerun()

        if st.button("🔄 전체 새로고침 → inbox", key="pull_rss_btn"):
            if not src["rss"]:
                st.warning("등록된 피드가 없습니다. 먼저 피드를 추가하세요.")
            else:
                with st.spinner("피드를 가져오는 중..."):
                    saved = pull_all_rss()
                if saved:
                    st.success(f"새 항목 {len(saved)}개를 inbox에 저장했습니다.")
                else:
                    st.info("새로 가져온 항목이 없습니다 (이미 수집된 글).")
                st.rerun()

        if src["rss"]:
            st.caption(f"등록된 피드 {len(src['rss'])}개")
            for r in src["rss"]:
                c1, c2 = st.columns([5, 1])
                cat = f" · {r['category']}" if r.get("category") else ""
                c1.markdown(f"**{r['title']}**{cat}  \n<small>{r['url']}</small>", unsafe_allow_html=True)
                if c2.button("삭제", key=f"delrss_{r['url']}"):
                    remove_rss(r["url"])
                    st.rerun()
        else:
            st.info("아직 등록된 RSS 피드가 없습니다.")

    # ── 전문가 SNS ──
    with col_sns:
        st.markdown("### 👤 전문가 SNS")
        with st.form("add_expert_form", clear_on_submit=True):
            ex_name = st.text_input("이름", placeholder="예: 홍길동")
            ex_platform = st.selectbox("플랫폼", ["instagram", "x", "linkedin", "threads", "web"])
            ex_url = st.text_input("프로필 URL", placeholder="https://...")
            ex_note = st.text_input("메모 (선택)", placeholder="예: 프롬프트 엔지니어링 전문")
            if st.form_submit_button("전문가 추가") and ex_url.strip():
                add_expert(ex_name or ex_url, ex_platform, ex_url, ex_note)
                st.success(f"전문가 추가됨: {ex_name or ex_url}")
                st.rerun()

        st.markdown("#### 게시물 가져오기")
        post_url = st.text_input("게시물 링크", placeholder="https://...", key="sns_post_url")
        if st.button("게시물 → inbox", key="sns_post_btn") and post_url.strip():
            with st.spinner("게시물 정보를 가져오는 중..."):
                path = save_social_post(post_url.strip())
            st.success(f"저장 완료: {path.name}")
            st.caption("캡션이 부실하면 Claude Code에 'just-scrape로 가져와줘'라고 요청하세요.")
            st.rerun()

        if src["experts"]:
            st.caption(f"등록된 전문가 {len(src['experts'])}명")
            for e in src["experts"]:
                c1, c2 = st.columns([5, 1])
                note = f" · {e['note']}" if e.get("note") else ""
                c1.markdown(
                    f"**{e['name']}** ({e['platform']}){note}  \n<small>{e['url']}</small>",
                    unsafe_allow_html=True,
                )
                if c2.button("삭제", key=f"delex_{e['url']}"):
                    remove_expert(e["url"])
                    st.rerun()
        else:
            st.info("아직 등록된 전문가가 없습니다.")

# ── 탭 2: 직접 메모 ────────────────────────────────────────────
with tab_memo:
    st.markdown("## ✏️ 직접 메모")
    st.caption("마크다운으로 메모를 작성하고 inbox에 저장하세요. 저장 후 Claude Code에 '정리해줘'라고 요청하세요.")

    # nonce로 위젯 key를 갈아끼워 저장 후 폼을 비울 수 있게 한다
    if "memo_nonce" not in st.session_state:
        st.session_state["memo_nonce"] = 0
    nonce = st.session_state["memo_nonce"]

    memo_title = st.text_input(
        "제목", placeholder="메모 제목을 입력하세요", key=f"memo_title_{nonce}"
    )

    col_edit, col_preview = st.columns(2)

    with col_edit:
        st.markdown("**편집**")
        st.caption("`**굵게**`  `*기울임*`  `# 제목`  `` `코드` ``  `- 목록`  `> 인용`")
        memo_content = st.text_area(
            "마크다운 입력",
            height=400,
            placeholder="# 제목\n\n내용을 마크다운으로 작성하세요.\n\n- 항목 1\n- 항목 2\n\n**굵게**, *기울임*, `코드`",
            key=f"memo_content_{nonce}",
            label_visibility="collapsed",
        )

    with col_preview:
        st.markdown("**미리보기**")
        if memo_content:
            st.markdown(memo_content)
        else:
            st.markdown('<p style="color:#aaa;">왼쪽에 내용을 입력하면 여기에 미리보기가 표시됩니다.</p>', unsafe_allow_html=True)

    st.divider()
    col_save, col_new = st.columns([1, 1])
    with col_save:
        if st.button("📥 inbox에 저장", key="memo_save_btn", type="primary"):
            if not memo_title.strip():
                st.warning("제목을 입력해주세요.")
            elif not memo_content.strip():
                st.warning("내용을 입력해주세요.")
            else:
                filename = memo_title.strip() + ".md"
                save_to_inbox(filename, memo_content)
                st.session_state["memo_saved_msg"] = f"'{memo_title}' 메모가 inbox에 저장되었습니다."
                st.rerun()
    with col_new:
        if st.button("✍️ 새 메모 작성", key="memo_new_btn"):
            st.session_state["memo_nonce"] += 1
            st.session_state.pop("memo_saved_msg", None)
            st.rerun()

    if st.session_state.get("memo_saved_msg"):
        st.success(st.session_state["memo_saved_msg"] + "  ‘새 메모 작성’으로 폼을 비울 수 있어요.")

# ── 탭 3: 지식 베이스 ──────────────────────────────────────────
with tab_kb:
    st.markdown("## 📚 지식 베이스")
    st.caption("Claude Code가 정리해 저장한 문서들입니다.")

    db = load_db()
    items = db.get("items", [])

    if not items:
        st.info("아직 저장된 지식이 없습니다. inbox에 문서를 넣고 Claude Code에 '정리해줘'라고 말해보세요.")
    else:
        all_tags = sorted({tag for item in items for tag in item.get("tags", [])})

        col_search, col_tag = st.columns([2, 1])
        with col_search:
            query = st.text_input(
                "🔍 제목·태그 검색", placeholder="키워드 입력 (예: ChatGPT, 프롬프트)", key="kb_search"
            )
        with col_tag:
            selected_tag = st.selectbox("태그 필터", ["전체"] + all_tags)

        # 검색어가 있으면 Curator.search() 결과를 기준 목록으로, 없으면 전체
        base = Curator().search(query.strip()) if query.strip() else items
        # 태그 필터 AND 결합
        filtered = base if selected_tag == "전체" else [i for i in base if selected_tag in i.get("tags", [])]

        caption = f"{len(filtered)}개 문서"
        if query.strip():
            caption += f"  ·  '{query.strip()}' 검색 결과"
        st.caption(caption)

        if not filtered:
            st.info("조건에 맞는 문서가 없습니다. 검색어나 태그 필터를 바꿔보세요.")

        for item in reversed(filtered):
            title = item.get("title", "제목 없음")
            tags = item.get("tags", [])
            path = Path(item.get("path", ""))
            created = item.get("created_at", "")[:10]

            tag_str = " ".join(f"`{t}`" for t in tags) if tags else ""
            with st.expander(f"**{title}** {tag_str}  •  {created}"):
                if path.exists():
                    content = path.read_text(encoding="utf-8")
                    st.markdown(content)
                    st.divider()
                    act_qa, act_dl = st.columns([1, 1])
                    with act_qa:
                        if st.button("QA 검토", key=f"qa_{path.name}"):
                            qa = QA()
                            st.session_state[f"qaresult_{path.name}"] = qa.format_report(
                                qa.review(content)
                            )
                    with act_dl:
                        st.download_button(
                            "⬇️ .md 다운로드",
                            data=content,
                            file_name=path.name,
                            mime="text/markdown",
                            key=f"dl_{path.name}",
                        )
                    # QA 결과 유지 렌더링
                    if st.session_state.get(f"qaresult_{path.name}"):
                        st.markdown(st.session_state[f"qaresult_{path.name}"])
                else:
                    st.warning("파일을 찾을 수 없습니다.")

# ── 탭 4: 커리큘럼 ─────────────────────────────────────────────
with tab_cur:
    # ── session_state 초기화 ────────────────────────────────────
    if "cur_selected_id" not in st.session_state:
        st.session_state["cur_selected_id"] = None
    if "cur_selected_week" not in st.session_state:
        st.session_state["cur_selected_week"] = 0  # 0 = 전체

    cur_db = load_curriculum_db()
    curricula = cur_db.get("curricula", [])

    # ════════════════════════════════════════════════════════════
    # DASHBOARD 뷰 (커리큘럼 미선택)
    # ════════════════════════════════════════════════════════════
    if st.session_state["cur_selected_id"] is None:
        st.markdown("## 📋 커리큘럼")
        st.caption("학습 커리큘럼을 선택해 교재와 슬라이드를 확인하세요.")

        if not curricula:
            st.info('아직 커리큘럼이 없습니다. Claude Code에 `"AI 기초 커리큘럼 만들어줘"`라고 말해보세요.')
        else:
            # 각 커리큘럼 메타를 한 번씩 로드해 두고 트랙/순서로 그룹·정렬한다
            loaded = []
            for entry in curricula:
                try:
                    cur_data = load_curriculum(entry["path"])
                except Exception:
                    cur_data = {}
                loaded.append((entry, cur_data))

            id_to_title = {e["id"]: e["title"] for e in curricula}

            def _order_key(item):
                o = item[1].get("order")
                return (0, o) if isinstance(o, int) else (1, 0)

            main_items = sorted(
                [it for it in loaded if it[1].get("track", "main") != "elective"],
                key=_order_key,
            )
            elective_items = [it for it in loaded
                              if it[1].get("track") == "elective"]

            def _render_cur_card(entry, cur_data):
                n_sessions = len(cur_data.get("sessions", []))
                audience = cur_data.get("target_audience", "입문자")
                desc = cur_data.get("description", "")
                updated = cur_data.get("updated_at", "")[:10]
                order = cur_data.get("order")
                level = cur_data.get("level", "")
                prereq = cur_data.get("prerequisites", [])
                try:
                    has_pptx = bool(
                        cur_data.get("generated", {}).get("pptx_path") and
                        Path(cur_data["generated"]["pptx_path"]).exists()
                    )
                except Exception:
                    has_pptx = False

                with st.container(border=True):
                    if cur_data.get("track") == "elective":
                        badge = "선택 트랙"
                    elif isinstance(order, int):
                        badge = f"{order}단계"
                    else:
                        badge = ""
                    if level:
                        badge = f"{badge} · {level}" if badge else level
                    if badge:
                        st.caption(f"🧭 {badge}")
                    st.markdown(f"### {entry['title']}")
                    st.caption(f"{audience} · {n_sessions}주 과정")
                    if desc:
                        st.write(desc[:100] + ("…" if len(desc) > 100 else ""))
                    if prereq:
                        names = ", ".join(id_to_title.get(p, p) for p in prereq)
                        st.caption(f"📋 선수: {names}")
                    st.caption(f"마지막 업데이트: {updated}")
                    if has_pptx:
                        st.caption("📎 PPTX 다운로드 가능")
                    if st.button("열기 →", key=f"open_{entry['id']}",
                                 use_container_width=True, type="primary"):
                        st.session_state["cur_selected_id"] = entry["id"]
                        st.session_state["cur_selected_week"] = 0
                        st.rerun()

            def _render_grid(items):
                cols = st.columns(min(3, len(items)))
                for i, (entry, cur_data) in enumerate(items):
                    with cols[i % 3]:
                        _render_cur_card(entry, cur_data)

            if main_items:
                st.markdown("#### 🎯 메인 학습 경로")
                st.caption("아래 순서대로 수강하는 것을 권장합니다.")
                _render_grid(main_items)

            if elective_items:
                st.divider()
                st.markdown("#### 🎨 선택 트랙")
                st.caption("메인 경로와 무관하게 단독으로 들을 수 있는 과정입니다.")
                _render_grid(elective_items)

        st.divider()
        with st.expander("💬 Claude Code 명령어 가이드"):
            st.code("""\
[제목] 커리큘럼 만들어줘      → 새 커리큘럼 생성
[N]주차 세션 추가: [제목]     → 세션 추가
[N]주차에 [파일명] 연결해줘   → 지식 문서 연결
[N]주차 목표 바꿔줘: [목표]   → 학습 목표 수정
[N]주차 활동 추가: [활동]     → 활동 추가
[N]주차 삭제해줘              → 세션 삭제
커리큘럼 슬라이드 업데이트해줘 → 슬라이드 JSON + PPTX 재생성
커리큘럼 목록 보여줘           → 목록 출력
또는 /커리큘럼 슬래시 커맨드 사용""", language="text")

    # ════════════════════════════════════════════════════════════
    # 상세 뷰 (커리큘럼 선택됨)
    # ════════════════════════════════════════════════════════════
    else:
        selected_entry = next(
            (c for c in curricula if c["id"] == st.session_state["cur_selected_id"]),
            None,
        )
        if selected_entry is None:
            st.session_state["cur_selected_id"] = None
            st.rerun()

        try:
            curriculum = load_curriculum(selected_entry["path"])
        except Exception as e:
            st.error(f"커리큘럼 파일을 불러올 수 없습니다: {e}")
            if st.button("← 목록으로"):
                st.session_state["cur_selected_id"] = None
                st.rerun()
            st.stop()

        sessions = sorted(curriculum.get("sessions", []), key=lambda s: s["week"])
        selected_week = st.session_state["cur_selected_week"]

        # ── 상단 헤더 ────────────────────────────────────────────
        hdr_l, hdr_r = st.columns([3, 1])
        with hdr_l:
            if st.button("← 커리큘럼 목록", key="back_to_dashboard"):
                st.session_state["cur_selected_id"] = None
                st.rerun()
            st.markdown(f"## {curriculum['title']}")
            order = curriculum.get("order")
            level = curriculum.get("level", "")
            if curriculum.get("track") == "elective":
                pos = "선택 트랙"
            elif isinstance(order, int):
                pos = f"메인 경로 {order}단계"
            else:
                pos = ""
            if level:
                pos = f"{pos} · {level}" if pos else level
            st.caption(
                (f"🧭 {pos} · " if pos else "")
                + f"{curriculum.get('target_audience','입문자')} · "
                f"{len(sessions)}주 과정 · "
                f"업데이트: {curriculum.get('updated_at','')[:10]}"
            )
            _id_title = {c["id"]: c["title"] for c in curricula}
            _prereq = curriculum.get("prerequisites", [])
            if _prereq:
                st.caption("📋 선수 과정: "
                           + ", ".join(_id_title.get(p, p) for p in _prereq))
            _next = curriculum.get("next", [])
            if _next:
                st.caption("➡️ 다음 권장 과정")
                ncols = st.columns(min(3, len(_next)))
                for ni, nid in enumerate(_next):
                    if nid not in _id_title:
                        continue
                    with ncols[ni % len(ncols)]:
                        if st.button(f"{_id_title[nid]} →", key=f"next_{nid}",
                                     use_container_width=True):
                            st.session_state["cur_selected_id"] = nid
                            st.session_state["cur_selected_week"] = 0
                            st.rerun()
        with hdr_r:
            pptx_path = curriculum.get("generated", {}).get("pptx_path")
            if pptx_path and Path(pptx_path).exists():
                with open(pptx_path, "rb") as f:
                    st.download_button(
                        "⬇️ PPTX 다운로드",
                        data=f,
                        file_name=Path(pptx_path).name,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        key="dl_pptx",
                        use_container_width=True,
                    )

        st.divider()

        # ── 본문: 왼쪽 네비 + 오른쪽 콘텐츠 ─────────────────────
        col_nav, col_content = st.columns([1, 3])

        # ── 왼쪽: 세션 네비게이션 버튼 ───────────────────────────
        with col_nav:
            st.markdown("**주차 선택**")
            # 전체 보기 버튼
            if st.button(
                "📋 전체 보기",
                key="ses_all",
                use_container_width=True,
                type="primary" if selected_week == 0 else "secondary",
            ):
                st.session_state["cur_selected_week"] = 0
                st.rerun()

            # 세션별 버튼
            for ses in sessions:
                btn_label = f"{ses['week']}주차\n{ses['title']}"
                is_active = selected_week == ses["week"]
                if st.button(
                    btn_label,
                    key=f"ses_w{ses['week']}_{selected_entry['id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["cur_selected_week"] = ses["week"]
                    # 슬라이드 인덱스 초기화
                    st.session_state[f"slide_idx_{selected_entry['id']}_{ses['week']}"] = 0
                    st.rerun()

        # ── 오른쪽: 교재 / 슬라이드 탭 ──────────────────────────
        with col_content:
            tab_doc, tab_slides = st.tabs(["📖 교재", "🖼 슬라이드"])

            # ── 교재 탭 ───────────────────────────────────────────
            with tab_doc:
                if selected_week == 0:
                    # 전체: 커리큘럼 개요 + 각 세션 요약
                    st.markdown(f"# {curriculum['title']}")
                    st.markdown(
                        f"> **수강 대상**: {curriculum.get('target_audience','입문자')}  |  "
                        f"**전체 {len(sessions)}주 과정**"
                    )
                    st.markdown(curriculum.get("description", ""))
                    st.divider()
                    st.markdown("## 커리큘럼 구성")
                    for ses in sessions:
                        with st.expander(f"**{ses['week']}주차: {ses['title']}** — {ses.get('duration','60분')}"):
                            if ses.get("objectives"):
                                st.markdown("**학습 목표**")
                                for obj in ses["objectives"]:
                                    st.markdown(f"- {obj}")
                            if ses.get("activities"):
                                st.markdown("**실습 활동**")
                                for act in ses["activities"]:
                                    st.markdown(f"- {act}")
                            refs = ses.get("knowledge_refs", [])
                            if refs:
                                st.caption("지식 문서: " + ", ".join(Path(r).name for r in refs))
                            ext_refs = ses.get("references", [])
                            if ext_refs:
                                st.markdown("**참고 자료 (영상·링크)**")
                                for ref in ext_refs:
                                    icon = {"youtube": "▶", "tool": "🧰"}.get(ref.get("type"), "🔗")
                                    title = ref.get("title") or ref.get("url", "링크")
                                    url = ref.get("url", "")
                                    ch = f" · {ref.get('channel')}" if ref.get("channel") else ""
                                    st.markdown(f"- {icon} [{title}]({url}){ch}")
                            cross = ses.get("cross_refs", [])
                            if cross:
                                st.markdown("**🔗 연결 통로**")
                                for cr in cross:
                                    where = (f"{cr.get('title','')} {cr.get('week')}주차"
                                             if cr.get("week") else cr.get("title", ""))
                                    note = (cr.get("note") or "").strip()
                                    st.markdown(
                                        f"- {where} · {cr.get('relation','연결')}"
                                        + (f" — {note}" if note else "")
                                    )
                else:
                    # 특정 주차 교재
                    ses = next((s for s in sessions if s["week"] == selected_week), None)
                    if ses:
                        st.markdown(build_session_doc(curriculum, ses))
                    else:
                        st.warning("해당 주차 세션을 찾을 수 없습니다.")

            # ── 슬라이드 탭 ───────────────────────────────────────
            with tab_slides:
                all_slides = load_slides(curriculum)
                if not all_slides:
                    st.info('슬라이드가 없습니다. Claude Code에 `"커리큘럼 슬라이드 업데이트해줘"`라고 요청하세요.')
                else:
                    # 선택된 주차에 맞게 슬라이드 필터링
                    if selected_week == 0:
                        view_slides = all_slides
                        slide_key = f"slide_idx_{selected_entry['id']}_all"
                    else:
                        def _belongs(s):
                            if s.get("type") == "title":
                                return True
                            # week 필드 우선(견고), 없으면 section 부분문자열 폴백
                            if s.get("week") is not None:
                                return s.get("week") == selected_week
                            return f"{selected_week}주차" in s.get("section", "")
                        view_slides = [s for s in all_slides if _belongs(s)]
                        slide_key = f"slide_idx_{selected_entry['id']}_{selected_week}"

                    if not view_slides:
                        st.info("이 주차에 해당하는 슬라이드가 없습니다.")
                    else:
                        st.caption("⛶ 전체화면 버튼 또는 ← → 화살표 키로 넘길 수 있어요.")
                        _render_slide_deck(view_slides)

# ── 탭 5: 보조 프로그램 ────────────────────────────────────────
with tab_aux:
    st.markdown("## 🧰 보조 프로그램")
    st.caption("확장프로그램·단축키 사이트·유용한 툴을 모아 관리합니다. "
               "제목을 클릭하면 브라우저(크롬)에서 바로 열립니다.")

    # 커리큘럼 id → 제목 매핑 (연관 표시용)
    _cur_title = {c["id"]: c["title"] for c in load_curriculum_db().get("curricula", [])}

    # ── 추가 폼 ──────────────────────────────────────────────────
    with st.expander("➕ 보조 프로그램 추가", expanded=False):
        with st.form("add_aux_form", clear_on_submit=True):
            ac1, ac2 = st.columns(2)
            with ac1:
                f_title = st.text_input("이름", placeholder="예: Vimium")
                f_url = st.text_input("링크(URL)", placeholder="https://...")
            with ac2:
                f_cat = st.selectbox("분류", CATEGORIES)
                f_tags = st.text_input("태그(쉼표로 구분, 선택)", placeholder="생산성, 키보드")
            f_desc = st.text_area("설명", placeholder="무엇에 쓰는 도구인지 한두 줄로")
            submitted = st.form_submit_button("카탈로그에 추가", type="primary")
            if submitted:
                if not f_title.strip() or not f_url.strip():
                    st.warning("이름과 링크는 필수입니다.")
                else:
                    tags = [t.strip() for t in f_tags.split(",") if t.strip()]
                    add_aux_program(f_title, f_desc, f_url, category=f_cat, tags=tags)
                    st.success(f"'{f_title}' 추가됨")
                    st.rerun()

    st.divider()

    aux_items = load_aux_db().get("items", [])
    if not aux_items:
        st.info("아직 등록된 보조 프로그램이 없습니다. 위 '추가' 폼을 쓰거나, "
                "Claude Code에 `\"[툴 링크] 보조 프로그램에 추가해줘\"`라고 말해보세요.")
    else:
        st.caption(f"총 {len(aux_items)}개")
        # 분류별 그룹핑 (표준 분류 순서 + 기타 분류)
        present_cats = [c for c in CATEGORIES if any(i.get("category") == c for i in aux_items)]
        extra_cats = sorted({i.get("category", "기타") for i in aux_items} - set(CATEGORIES))
        for cat in present_cats + extra_cats:
            cat_items = [i for i in aux_items if i.get("category", "기타") == cat]
            if not cat_items:
                continue
            st.markdown(f"### {cat}")
            cols = st.columns(min(3, len(cat_items)))
            for i, item in enumerate(cat_items):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{item.get('title','(제목 없음)')}**")
                        if item.get("description"):
                            st.caption(item["description"])
                        if item.get("tags"):
                            st.caption("🏷 " + ", ".join(item["tags"]))
                        if item.get("curriculum_id") and item["curriculum_id"] in _cur_title:
                            st.caption(f"📋 {_cur_title[item['curriculum_id']]}")
                        link_c, del_c = st.columns([3, 1])
                        with link_c:
                            if item.get("url"):
                                st.link_button("열기 ↗", item["url"], use_container_width=True)
                        with del_c:
                            if st.button("🗑", key=f"del_aux_{item['id']}",
                                         use_container_width=True, help="삭제"):
                                delete_aux_program(item["id"])
                                st.rerun()

# ── 탭 6: 에이전트 ─────────────────────────────────────────────
with tab_agents:
    st.markdown("## 🤖 에이전트 현황")
    st.caption("Claude Code 세션이 팀장 역할을 하며 아래 에이전트들을 오케스트레이션합니다.")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 팀 구성")
        st.markdown("""
| 에이전트 | 상태 | 역할 |
|----------|------|------|
| 팀장 | 🟢 활성 (Claude Code) | 요청 분석 + 오케스트레이션 |
| 교육자 | 🟢 활성 | 문서 + PPT 슬라이드 생성 |
| 큐레이터 | 🟢 활성 | DB 관리 + 자동 태깅 |
| QA | 🟢 활성 | 품질 검토 |
| 커리큘럼 | 🟢 활성 | 커리큘럼 생성·관리 |
| 리서처 | 👤 사용자 담당 | inbox에 직접 자료 입력 |
""")

    with col_b:
        st.markdown("### 지식베이스 통계")
        curator = Curator()
        stats = curator.get_stats()
        st.metric("총 문서 수", stats["total_items"])
        st.metric("등록된 태그 수", stats["total_tags"])

        cur_count = len(load_curriculum_db().get("curricula", []))
        st.metric("커리큘럼 수", cur_count)

        if stats["tag_counts"]:
            st.markdown("**태그별 문서 수**")
            for tag, count in sorted(stats["tag_counts"].items(), key=lambda x: -x[1]):
                st.caption(f"`{tag}` — {count}개")

    st.divider()
    st.markdown("### Claude Code에 요청하는 방법")
    st.code("""inbox 정리해줘              → 교육자가 문서화 + 큐레이터 저장
PPT 만들어줘                → 교육자가 PPT 슬라이드 생성
ChatGPT 관련 자료 찾아줘    → 큐레이터가 검색
방금 만든 문서 검토해줘      → QA가 점수 + 피드백 제공
AI 기초 커리큘럼 만들어줘    → 커리큘럼 에이전트가 생성
커리큘럼 슬라이드 업데이트해줘 → 슬라이드 JSON + PPTX 재생성
/커리큘럼                   → 커리큘럼 전용 슬래시 커맨드""", language="text")
