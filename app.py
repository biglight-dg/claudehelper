from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from tools.file_tools import load_db, save_knowledge_file
from tools.reader import read_inbox_files, fetch_url, save_to_inbox, read_pdf
from tools.sources import (
    load_sources, add_rss, remove_rss, add_expert, remove_expert,
    save_social_post, auto_collect_kind, sync_expert_feeds,
)
from tools.news import (
    collect_news, collect_news_daily, recent_items, sources_in_news,
    build_digest_source, load_news, latest_digest,
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


# ── 접근 인증: 공유 비밀번호 게이트 + 역할(role) ────────────────
def _is_admin() -> bool:
    """관리자(전체 권한)면 True. 손님(보기·입력만)이면 False."""
    return st.session_state.get("role") == "admin"


def _check_auth() -> None:
    """비밀번호로 입장 + 역할 부여. 인증 전에는 본문 렌더를 막는다.

    secrets.toml 에 admin_password / guest_password 를 둔다.
    비밀번호가 설정돼 있지 않으면(로컬 단독 사용) 게이트 없이 관리자 통과.
    """
    if st.session_state.get("auth_ok"):
        return

    admin_pw = st.secrets.get("admin_password", "")
    guest_pw = st.secrets.get("guest_password", "")

    # 비번이 하나도 설정되지 않은 환경(로컬 개발)은 게이트를 건너뛴다.
    if not admin_pw and not guest_pw:
        st.session_state["auth_ok"] = True
        st.session_state["role"] = "admin"
        return

    def _grant(role: str) -> None:
        st.session_state["auth_ok"] = True
        st.session_state["role"] = role

    # "비밀번호 저장하기"로 저장해 둔 값이 URL(?k=)에 있으면 자동 입장한다.
    # (지인 공유용 간이 기능 — 비번이 주소에 남으므로 강한 보안용은 아님)
    saved = st.query_params.get("k", "")
    if saved:
        if admin_pw and saved == admin_pw:
            _grant("admin")
            return
        if guest_pw and saved == guest_pw:
            _grant("guest")
            return

    st.title("🔒 나만의 지식 베이스")
    st.caption("공유받은 비밀번호를 입력하면 입장합니다.")
    pw = st.text_input("비밀번호", type="password")
    remember = st.checkbox("비밀번호 저장하기 (다음에 자동 입장)", value=True)
    if st.button("입장"):
        role = None
        if admin_pw and pw == admin_pw:
            role = "admin"
        elif guest_pw and pw == guest_pw:
            role = "guest"

        if role:
            _grant(role)
            if remember:
                st.query_params["k"] = pw   # 주소에 저장 → 다음 방문 시 자동 입장
            else:
                st.query_params.pop("k", None)
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()  # 인증 전에는 아래 본문이 실행되지 않는다.


_check_auth()


# ── Notion 스타일 전역 테마 CSS ────────────────────────────────
# config.toml [theme]가 핵심 팔레트를 잡고, 여기서 폰트·둥글기·그림자·
# 버튼/탭/카드 등 세부를 입힌다. 발표 슬라이드 덱(_slide_inner_html /
# _DECK_TEMPLATE)은 흑백 = PPTX 일치를 위해 건드리지 않는다.
_THEME_CSS = """
<style>
/* Pretendard — 한글 완방 + Inter 메트릭 (이 프로젝트 PPTX와 동일 계열) */
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/variable/pretendardvariable-dynamic-subset.css");

:root {
  --ink: #1a1a1a;          /* soft true-black */
  --ink-muted: #615d59;    /* 보조 텍스트 */
  --ink-faint: #a39e98;    /* 캡션·플레이스홀더 */
  --primary: #0075de;      /* 유일한 구조적 액센트 */
  --primary-active: #005bab;
  --hairline: #e6e6e6;
  --surface: #ffffff;
  /* Level-1 다층 미세 그림자 (Notion Elevation) */
  --shadow-soft: 0 0.175px 1.041px rgba(0,0,0,0.01),
                 0 0.8px 2.925px rgba(0,0,0,0.02),
                 0 2.025px 7.847px rgba(0,0,0,0.027),
                 0 4px 18px rgba(0,0,0,0.04);
}

.stApp, .stApp button, .stApp input, .stApp textarea, .stApp select,
.stMarkdown, [data-testid="stSidebar"] {
  font-family: "Pretendard Variable", Pretendard, -apple-system,
               system-ui, "Segoe UI", Helvetica, Arial, sans-serif;
}
/* Material 아이콘은 폰트 오버라이드 제외 — 안 하면 아이콘이 "upload" 같은
   리거처 텍스트로 깨진다. 아이콘 전용 폰트를 강제로 되돌린다. */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded,
[class*="material-symbols"], [class*="material-icons"] {
  font-family: "Material Symbols Rounded", "Material Icons" !important;
}

/* 헤딩: 굵고 타이트 (음수 트래킹) */
h1, h2, h3 { color: var(--ink); font-weight: 700; }
h1 { font-weight: 800; letter-spacing: -1px; }
h2 { letter-spacing: -0.625px; }
h3 { letter-spacing: -0.25px; }

/* 보조 텍스트 (캡션) */
[data-testid="stCaptionContainer"], .stCaption { color: var(--ink-faint); }

/* 링크 — 단 하나의 파랑 */
a, a:visited { color: var(--primary); }

/* 버튼 기본/secondary = 유틸리티: 흰 표면 · 헤어라인 · 8px */
.stButton > button,
[data-testid="stBaseButton-secondary"] {
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  font-weight: 500;
}
.stButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--primary);
  color: var(--primary);
}
/* primary 버튼 = 파랑. 라운드는 유틸리티 버튼과 8px로 통일(활성/비활성 일관) */
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
  background: var(--primary);
  color: #ffffff;
  border: 1px solid var(--primary);
  border-radius: 8px;
  font-weight: 500;
}
.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
  background: var(--primary-active);
  border-color: var(--primary-active);
  color: #ffffff;
}
.stButton > button[kind="primary"]:active,
[data-testid="stBaseButton-primary"]:active {
  background: var(--primary-active);
  transform: scale(0.98);
}

/* 카드: st.container(border=True) — 12px · 헤어라인 · 은은한 그림자 */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
  border-radius: 12px;
}
div[data-testid="stVerticalBlockBorderWrapper"][style*="border"] {
  background: var(--surface);
  border: 1px solid var(--hairline) !important;
  border-radius: 12px;
  box-shadow: var(--shadow-soft);
}

/* 입력: 4px (pill 금지) · 헤어라인 */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="input"], [data-baseweb="textarea"] {
  border-radius: 4px !important;
  border-color: var(--hairline) !important;
}
[data-baseweb="select"] > div { border-radius: 4px !important; }

/* 탭: 활성 탭 라벨 + 얇은 밑줄 하이라이트만 파랑 (패널은 절대 칠하지 않음) */
[data-baseweb="tab"][aria-selected="true"] { color: var(--primary) !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--primary) !important; }
</style>
"""

# 다크 모드: config.toml은 라이트 1종만 지정하므로, 토글이 켜지면
# CSS 변수와 표면 색을 어둡게 덮어쓴다(앱 한정 — 슬라이드 덱 iframe은 불변).
_DARK_CSS = """
<style>
:root {
  --ink: #e9e9e7;
  --ink-muted: #9b9b9b;
  --ink-faint: #6f6f6f;
  --hairline: #373737;
  --surface: #2a2a2a;
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background-color: #191919 !important;
}
[data-testid="stSidebar"] { background-color: #202020 !important; }
.stApp, .stApp p, .stApp li, .stApp label, .stApp span,
h1, h2, h3, h4, [data-testid="stMarkdownContainer"] { color: #e9e9e7; }
[data-testid="stCaptionContainer"] { color: #9b9b9b !important; }
/* 카드 */
div[data-testid="stVerticalBlockBorderWrapper"][style*="border"] {
  background: #2a2a2a !important;
  border-color: #373737 !important;
}
/* 입력 */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="input"] input,
[data-baseweb="select"] > div {
  background-color: #2a2a2a !important;
  color: #e9e9e7 !important;
  border-color: #373737 !important;
}
/* 유틸리티 버튼 */
.stButton > button, [data-testid="stBaseButton-secondary"] {
  background: #2a2a2a !important;
  color: #e9e9e7 !important;
  border-color: #373737 !important;
}
/* 코드 블록 */
code, .stCode, pre { background-color: #2a2a2a !important; color: #e9e9e7 !important; }
/* 비활성 탭 / 세그먼트 라벨 — 어둠 위 어둠 방지 */
.stTabs [data-baseweb="tab"] { color: #c9c9c7 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: var(--primary) !important; }
[data-testid="stButtonGroup"] button { color: #e9e9e7 !important; }
/* 파일 업로더 드롭존 */
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploader"] section {
  background-color: #2a2a2a !important;
}
</style>
"""

# 다크 모드 토글 — 사이드바 최상단에 배치(코드 위치와 무관하게 사이드바로 렌더)
_dark = st.sidebar.toggle("🌙 다크 모드", key="dark_mode")
st.markdown(_THEME_CSS, unsafe_allow_html=True)
if _dark:
    st.markdown(_DARK_CSS, unsafe_allow_html=True)


# 슬라이드 가상 캔버스 크기(px). 폰트·박스 모두 이 캔버스 기준 절대값으로
# 그린 뒤, 렌더 단계에서 transform:scale로 컨테이너 폭에 맞춘다.
# 세로 4:5(1280×1600) — 교재 옆 좁은 칸을 세로로 꽉 채워 더 잘 보이게 한다.
CANVAS_W = 1280
CANVAS_H = 1600


def _slide_inner_html(slide: dict) -> str:
    """슬라이드 타입별 내부 패널 HTML(래퍼 제외)을 문자열로 반환한다.

    폰트는 1280×1600(세로 4:5) 고정 가상 캔버스 기준의 절대 px다. 렌더 단계에서
    캔버스 전체를 transform:scale로 컨테이너 폭에 맞추므로, 폰트와 박스가
    항상 같은 비율로 줄어 PowerPoint처럼 절대 박스를 넘치지 않는다.
    """
    stype = slide.get("type", "content")

    # 폰트는 1280×1600(세로 4:5) 캔버스 기준 절대 px. 세로 공간이 넓으므로
    # 폰트를 큼직하게 잡고 본문을 세로로 고르게 분배해 여백을 최소화한다.
    if stype == "title":
        inner = (
            '<div style="background:#111;width:100%;height:100%;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center;padding:8% 7%;">'
            '<div style="font-size:68px;font-weight:800;'
            f'color:#fff;text-align:center;line-height:1.3;margin-bottom:1.6rem;">'
            f'{slide.get("title","")}</div>'
            '<div style="width:140px;height:4px;background:#555;margin-bottom:1.6rem;"></div>'
            '<div style="font-size:34px;color:#bbb;text-align:center;line-height:1.5;">'
            f'{slide.get("subtitle","")}</div>'
            '<div style="position:absolute;bottom:4%;right:5%;font-size:22px;color:#555;">AI 교육팀</div>'
            '</div>'
        )
        return inner

    elif stype == "part_divider":
        weeks = slide.get("weeks", "")
        inner = (
            '<div style="background:#111;width:100%;height:100%;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center;padding:8% 7%;">'
            '<div style="font-size:92px;font-weight:800;'
            f'color:#fff;text-align:center;letter-spacing:0.05em;margin-bottom:1.4rem;">'
            f'{slide.get("label","")}</div>'
            '<div style="width:140px;height:4px;background:#555;margin-bottom:1.4rem;"></div>'
            '<div style="font-size:44px;color:#ddd;text-align:center;'
            f'line-height:1.35;margin-bottom:1rem;">{slide.get("title","")}</div>'
            f'<div style="font-size:30px;color:#888;">{weeks}</div>'
            '</div>'
        )
        return inner

    elif stype == "divider":
        inner = (
            '<div style="background:#fff;width:100%;height:100%;display:flex;'
            'align-items:center;padding:7% 8%;">'
            '<div style="width:12px;height:55%;background:#000;border-radius:6px;'
            'margin-right:6%;flex-shrink:0;"></div>'
            '<div>'
            '<div style="font-size:170px;font-weight:800;color:#e8e8e8;'
            f'line-height:0.95;margin-bottom:0.6rem;">{slide.get("number","")}</div>'
            '<div style="font-size:58px;font-weight:700;color:#111;line-height:1.2;">'
            f'{slide.get("section","")}</div>'
            '</div></div>'
        )
        return inner

    elif stype == "content":
        bullets_html = "".join(
            f'<div style="display:flex;align-items:flex-start;">'
            f'<span style="color:#555;margin-right:0.8rem;flex-shrink:0;'
            f'font-size:40px;line-height:1.35;">▪</span>'
            f'<span style="font-size:40px;color:#222;line-height:1.35;">{b}</span>'
            f'</div>'
            for b in slide.get("bullets", [])
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:24px;color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.5rem;">{slide.get("section","")}</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1.2rem;"></div>'
            '<div style="font-size:58px;font-weight:800;color:#000;'
            f'margin-bottom:1.6rem;line-height:1.2;">{slide.get("title","")}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly;'
            f'overflow:auto;">{bullets_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "concept":
        analogy = (slide.get("analogy") or "").strip()
        analogy_html = (
            '<div style="background:#f2f2f2;border-left:8px solid #111;border-radius:10px;'
            'padding:1.4rem 1.6rem;margin-top:1.6rem;font-size:34px;color:#333;line-height:1.5;">'
            f'💡 {analogy}</div>'
        ) if analogy else ""
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:24px;color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.5rem;">{slide.get("section","")} · 개념</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1.2rem;"></div>'
            '<div style="font-size:56px;font-weight:800;color:#000;'
            f'margin-bottom:1.4rem;line-height:1.25;">{slide.get("term","")}</div>'
            '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;overflow:auto;">'
            '<div style="font-size:38px;color:#222;line-height:1.55;">'
            f'{slide.get("explain","")}</div>'
            f'{analogy_html}'
            '</div></div>'
        )
        return inner

    elif stype == "cards":
        variant = slide.get("variant", "number")
        items = slide.get("items", [])
        cards_html = "".join(
            '<div style="display:flex;align-items:stretch;background:#f2f2f2;border:1px solid #ccc;'
            'border-radius:10px;flex:1;min-height:0;overflow:hidden;">'
            '<div style="background:#111;color:#fff;font-weight:800;display:flex;align-items:center;'
            'justify-content:center;min-width:80px;'
            f'font-size:44px;">{(i+1) if variant=="number" else "•"}</div>'
            '<div style="display:flex;align-items:center;padding:0.6rem 1.4rem;'
            f'font-size:40px;color:#222;line-height:1.3;">{item}</div>'
            '</div>'
            for i, item in enumerate(items)
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:24px;color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.5rem;">{slide.get("section","")}</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1.2rem;"></div>'
            '<div style="font-size:58px;font-weight:800;color:#000;'
            f'margin-bottom:1.4rem;line-height:1.2;">{slide.get("title","")}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:1rem;min-height:0;">{cards_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "flow":
        # 세로 캔버스 → 박스를 위→아래로 스택하고 사이 화살표는 아래(▼) 방향.
        steps = slide.get("steps", [])
        boxes = []
        for idx, step in enumerate(steps):
            items_html = "".join(
                f'<div style="font-size:32px;color:#222;'
                f'margin-bottom:0.55rem;line-height:1.4;">· {it}</div>'
                for it in step.get("items", [])
            )
            boxes.append(
                '<div style="flex:1;background:#f2f2f2;border:2px solid #111;border-radius:12px;'
                'padding:1.4rem 1.8rem;display:flex;flex-direction:column;min-height:0;">'
                '<div style="font-weight:800;color:#000;'
                'font-size:40px;margin-bottom:0.9rem;">'
                f'{step.get("label","")}</div>'
                f'<div style="flex:1;">{items_html}</div></div>'
            )
            if idx < len(steps) - 1:
                boxes.append(
                    '<div style="display:flex;justify-content:center;color:#777;'
                    'font-size:42px;padding:0.35rem 0;flex-shrink:0;">▼</div>'
                )
        boxes_html = "".join(boxes)
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:24px;color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.5rem;">{slide.get("section","")}</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1.2rem;"></div>'
            '<div style="font-size:58px;font-weight:800;color:#000;'
            f'margin-bottom:1.4rem;line-height:1.2;">{slide.get("title","")}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column;min-height:0;gap:0.3rem;">{boxes_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "table":
        # 세로 캔버스 → 행 패딩을 키워 표가 세로를 고르게 채우도록 한다.
        headers = slide.get("headers", [])
        rows = slide.get("rows", [])
        header_cells = "".join(
            f'<th style="background:#111;color:#fff;padding:18px 20px;font-size:30px;'
            f'font-weight:700;text-align:left;white-space:nowrap;">{h}</th>'
            for h in headers
        )
        body_rows = ""
        for i, row in enumerate(rows):
            bg = "#fff" if i % 2 == 0 else "#f6f6f6"
            cells = "".join(
                f'<td style="padding:16px 20px;font-size:28px;'
                f'color:#222;border-bottom:1px solid #eee;line-height:1.35;">{row[j] if j < len(row) else ""}</td>'
                for j in range(len(headers))
            )
            body_rows += f'<tr style="background:{bg};">{cells}</tr>'
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:5% 6%;display:flex;flex-direction:column;">'
            '<div style="font-size:24px;color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.5rem;">{slide.get("section","")}</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1rem;"></div>'
            '<div style="font-size:52px;font-weight:800;color:#000;margin-bottom:1.2rem;line-height:1.2;">'
            f'{slide.get("title","")}</div>'
            '<div style="flex:1;overflow:auto;">'
            f'<table style="width:100%;height:100%;border-collapse:collapse;">'
            f'<thead><tr>{header_cells}</tr></thead>'
            f'<tbody>{body_rows}</tbody>'
            '</table></div></div>'
        )
        return inner

    elif stype == "references":
        items_html = "".join(
            '<div style="margin-bottom:0;">'
            f'<div style="font-size:34px;color:#111;font-weight:600;line-height:1.35;">{it.get("head","")}</div>'
            + (f'<div style="font-size:26px;color:#777;line-height:1.45;margin-top:0.35rem;">{it.get("desc","")}</div>'
               if it.get("desc") else "")
            + '</div>'
            for it in slide.get("items", [])
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:24px;color:#999;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:0.5rem;">{slide.get("section","")}</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1.2rem;"></div>'
            '<div style="font-size:52px;font-weight:800;color:#000;margin-bottom:1.4rem;line-height:1.2;">'
            f'{slide.get("title","")}</div>'
            '<div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly;'
            f'overflow:auto;">{items_html}</div>'
            '</div>'
        )
        return inner

    elif stype == "comparison":
        # 세로 캔버스 → 좌/우 2열 대신 위/아래 2행으로 스택.
        left_html = "".join(
            f'<div style="margin-bottom:0.6rem;font-size:34px;color:#222;line-height:1.4;">'
            f'▪ {item}</div>'
            for item in slide.get("left_items", [])
        )
        right_html = "".join(
            f'<div style="margin-bottom:0.6rem;font-size:34px;color:#222;line-height:1.4;">'
            f'▪ {item}</div>'
            for item in slide.get("right_items", [])
        )
        inner = (
            '<div style="background:#fff;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:52px;font-weight:800;color:#000;margin-bottom:1.2rem;line-height:1.2;">'
            f'{slide.get("title","")}</div>'
            '<div style="height:2px;background:#e0e0e0;margin-bottom:1.2rem;"></div>'
            '<div style="display:flex;flex-direction:column;flex:1;min-height:0;gap:1.4rem;">'
            '<div style="flex:1;min-height:0;display:flex;flex-direction:column;">'
            '<div style="font-weight:700;margin-bottom:0.8rem;font-size:38px;">'
            f'{slide.get("left_label","")}</div>{left_html}</div>'
            '<div style="height:2px;background:#e0e0e0;"></div>'
            '<div style="flex:1;min-height:0;display:flex;flex-direction:column;">'
            '<div style="font-weight:700;margin-bottom:0.8rem;font-size:38px;">'
            f'{slide.get("right_label","")}</div>{right_html}</div>'
            '</div></div>'
        )
        return inner

    elif stype == "summary":
        lessons_html = "".join(
            f'<div style="display:flex;align-items:flex-start;">'
            f'<span style="font-weight:800;color:#000;margin-right:0.9rem;flex-shrink:0;'
            f'font-size:34px;line-height:1.4;">{i+1}.</span>'
            f'<span style="font-size:34px;color:#222;line-height:1.4;">{lesson}</span>'
            f'</div>'
            for i, lesson in enumerate(slide.get("lessons", []))
        )
        source = slide.get("source", "")
        inner = (
            '<div style="background:#f5f5f5;width:100%;height:100%;padding:6% 7%;display:flex;flex-direction:column;">'
            '<div style="font-size:52px;font-weight:800;color:#000;margin-bottom:0.7rem;line-height:1.2;">'
            '커리큘럼 요약</div>'
            '<div style="height:2px;background:#ccc;margin-bottom:1.4rem;"></div>'
            '<div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly;'
            f'overflow:auto;">{lessons_html}</div>'
            f'<div style="font-size:22px;color:#999;margin-top:0.8rem;">출처: {source}</div>'
            '</div>'
        )
        return inner

    return ""


def _render_slide(slide: dict) -> None:
    """슬라이드 한 장을 캔버스 덱으로 렌더링한다(덱과 동일 스케일 처리)."""
    _render_slide_deck([slide], height=840)


# 클라이언트 덱: 1280×1600(세로 4:5) 고정 캔버스를 컨테이너 폭에 맞춰 transform:scale.
# 폰트가 박스와 같은 비율로 스케일되어 절대 넘치지 않는다(PowerPoint식 WYSIWYG).
_DECK_TEMPLATE = """
<style>
  *{box-sizing:border-box;}
  html,body{margin:0;padding:0;background:transparent;}
  #root{font-family:-apple-system,'Segoe UI',sans-serif;}
  #stage{display:flex;justify-content:center;}
  /* 세로 4:5 슬라이드가 넓은 컨테이너(전체 보기)에서 과도하게 커지지 않도록 표시폭 캡 */
  .viewport{width:100%;max-width:620px;margin:0 auto;overflow:hidden;}
  #root.fs .viewport{max-width:none;margin:0;}
  .scaler{position:relative;width:__CW__px;height:__CH__px;transform-origin:top left;}
  .slide{position:absolute;inset:0;width:__CW__px;height:__CH__px;}
  .frame{position:relative;width:__CW__px;height:__CH__px;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.15);display:flex;flex-direction:column;}
  /* 하단 마우스 조작 바: 큼직한 페이지 이동 버튼 */
  #bar{display:flex;align-items:center;justify-content:center;gap:0.7rem;margin-top:0.9rem;
       max-width:620px;margin-left:auto;margin-right:auto;}
  #bar button{border:1px solid #ccc;background:#fff;border-radius:10px;padding:0.6rem 1.3rem;
              cursor:pointer;font-size:1.05rem;font-weight:600;color:#222;line-height:1;
              transition:background 0.12s,transform 0.05s;}
  #bar button:hover:not(:disabled){background:#f2f2f2;}
  #bar button:active:not(:disabled){transform:translateY(1px);}
  #bar .nav{min-width:96px;}
  #bar #fs{margin-left:0.4rem;}
  #bar button:disabled{opacity:0.35;cursor:default;}
  #counter{color:#555;font-size:1.05rem;font-weight:600;min-width:88px;text-align:center;}
  #root.fs{background:#000;display:flex;flex-direction:column;justify-content:center;height:100vh;}
  #root.fs #stage{flex:1;align-items:center;}
  #root.fs #counter{color:#bbb;}
  #root.fs #bar button{background:#222;border-color:#444;color:#eee;}
  #root.fs #bar button:hover:not(:disabled){background:#333;}
  #root.fs #bar{padding-bottom:0.8rem;}
</style>
<div id="root">
  <div id="stage"><div class="viewport"><div class="scaler">__SLIDES__</div></div></div>
  <div id="bar">
    <button id="prev" class="nav">◀ 이전</button>
    <span id="counter"></span>
    <button id="next" class="nav">다음 ▶</button>
    <button id="fs">⛶ 전체화면</button>
  </div>
</div>
<script>
(function(){
  var n = __N__, i = 0;
  var CW = __CW__, CH = __CH__;
  var root = document.getElementById('root');
  var slides = root.querySelectorAll('.slide');
  var viewport = root.querySelector('.viewport');
  var scaler = root.querySelector('.scaler');
  var counter = document.getElementById('counter');
  var prev = document.getElementById('prev');
  var next = document.getElementById('next');
  var fs = document.getElementById('fs');

  function show(){
    for (var k=0;k<slides.length;k++){ slides[k].style.display = (k===i?'block':'none'); }
    counter.textContent = (i+1)+' / '+n;
    prev.disabled = (i===0);
    next.disabled = (i===n-1);
  }
  prev.onclick = function(){ if(i>0){ i--; show(); } };
  next.onclick = function(){ if(i<n-1){ i++; show(); } };

  // ── 스케일: 컨테이너 폭(전체화면이면 화면 폭)에 맞춰 캔버스를 통째로 축소 ──
  function curWidth(){
    if (root.classList.contains('fs')){
      return Math.min(window.innerWidth, window.innerHeight * CW / CH) - 8;
    }
    return viewport.clientWidth;
  }
  var lastW = -1;
  function reportHeight(){
    try {
      var h = Math.ceil(root.scrollHeight) + 4;
      window.parent.postMessage({type:'streamlit:setFrameHeight', height:h}, '*');
    } catch(e){}
  }
  function applyScale(force){
    var w = curWidth();
    if (!force && Math.abs(w - lastW) < 0.5) return;
    lastW = w;
    var s = w / CW;
    scaler.style.transform = 'scale(' + s + ')';
    viewport.style.height = (CH * s) + 'px';
    viewport.style.width = root.classList.contains('fs') ? (w + 'px') : '100%';
    reportHeight();
  }

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
    applyScale(true);
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

  if (typeof ResizeObserver !== 'undefined'){
    new ResizeObserver(function(){ applyScale(false); }).observe(viewport);
  }
  window.addEventListener('resize', function(){ applyScale(true); });

  show();
  applyScale(true);
})();
</script>
"""


def _render_slide_deck(slides: list[dict], height: int = 560) -> None:
    """슬라이드 목록을 화살표 이동 + 전체화면 가능한 클라이언트 덱으로 렌더링한다.

    1280×720 캔버스에 슬라이드를 절대 px로 그린 뒤 컨테이너 폭에 맞춰 scale한다.
    실제 높이는 iframe 안에서 postMessage(setFrameHeight)로 부모에 통보하며,
    height 인자는 통보 전 초기 높이(폴백)로만 쓰인다.
    """
    boxes = []
    for i, s in enumerate(slides):
        disp = "block" if i == 0 else "none"
        boxes.append(
            f'<div class="slide" style="display:{disp};">'
            f'<div class="frame">{_slide_inner_html(s)}</div>'
            f'</div>'
        )
    html = (
        _DECK_TEMPLATE
        .replace("__SLIDES__", "".join(boxes))
        .replace("__N__", str(len(slides)))
        .replace("__CW__", str(CANVAS_W))
        .replace("__CH__", str(CANVAS_H))
    )
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


def _render_digest(digest: dict) -> None:
    """주간 브리핑(구조화 dict)을 뉴닉 스타일 카드 레이아웃으로 렌더한다.

    구조화 필드(deep_dives 등)가 없으면 knowledge_path 마크다운으로 폴백한다.
    """
    if not digest.get("deep_dives") and not digest.get("intro"):
        p = Path(digest.get("knowledge_path") or digest.get("path", ""))
        if p.exists():
            st.markdown(p.read_text(encoding="utf-8"))
        else:
            st.warning("브리핑 내용을 찾을 수 없습니다.")
        return

    # 히어로
    st.markdown(
        '<div style="background:#213183;color:#fff;border-radius:12px;padding:1.4rem 1.6rem;margin-bottom:1.2rem;">'
        f'<div style="font-size:1.3rem;font-weight:800;margin-bottom:0.5rem;">📋 이번 주 AI 한 편으로</div>'
        f'<div style="font-size:0.85rem;color:rgba(255,255,255,0.6);margin-bottom:0.7rem;">{digest.get("period","")}</div>'
        f'<div style="font-size:1.02rem;line-height:1.6;color:#eee;">{digest.get("intro","")}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # 핵심 3 카드
    for i, d in enumerate(digest.get("deep_dives", []), 1):
        with st.container(border=True):
            st.markdown(
                f"<div style='font-size:1.25rem;font-weight:800;color:inherit;margin-bottom:0.2rem;'>"
                f"{d.get('emoji','🔥')} 핵심 {i}. {d.get('title','')}</div>",
                unsafe_allow_html=True,
            )
            if d.get("body"):
                st.markdown(d["body"])
            if d.get("question"):
                st.markdown(
                    '<div style="border-left:4px solid #0075de;background:#f6f5f4;'
                    'padding:0.7rem 1rem;border-radius:6px;margin:0.6rem 0;">'
                    '<b style="color:#0075de;">❔ 생각해볼 질문</b><br>'
                    f'<span style="color:#1a1a1a;">{d["question"]}</span></div>',
                    unsafe_allow_html=True,
                )
            srcs = d.get("sources", [])
            if srcs:
                cited = " · ".join(
                    f"[{s.get('name','출처')}]({s['url']})" if s.get("url") else s.get("name", "")
                    for s in srcs
                )
                st.caption(f"출처: {cited}")

    # 자투리 뉴스 (제목 + 두 줄 요약을 줄바꿈해 클릭 없이도 이해되게)
    shorts = digest.get("shorts", [])
    if shorts:
        st.markdown("#### 📌 자투리 뉴스")
        for s in shorts:
            head = f"[{s.get('title','')}]({s['link']})" if s.get("link") else s.get("title", "")
            line = f"- **{head}**"
            blurb = (s.get("blurb") or "").strip()
            src = f" <small>({s['source']})</small>" if s.get("source") else ""
            if blurb:
                line += f"  \n  {blurb}{src}"
            elif src:
                line += f"  \n  {src}"
            st.markdown(line, unsafe_allow_html=True)

    # 필요 기술 · 공부거리
    c1, c2 = st.columns(2)
    if digest.get("skills"):
        with c1:
            with st.container(border=True):
                st.markdown("**🛠 필요 기술 · 알아두면 좋은 개념**")
                for x in digest["skills"]:
                    st.markdown(f"- {x}")
    if digest.get("study"):
        with c2:
            with st.container(border=True):
                st.markdown("**📚 이번 주 공부거리**")
                for x in digest["study"]:
                    st.markdown(f"- {x}")


def _sort_items(items, mode, date_field, title_field="title"):
    """목록을 정렬 모드에 따라 정렬한다(원본 비변형).

    mode: '최신순' | '오래된순' | '제목순'. date_field 비교는 ISO 문자열 기준.
    """
    if mode == "제목순":
        return sorted(items, key=lambda x: (x.get(title_field) or "").lower())
    return sorted(items, key=lambda x: x.get(date_field) or "", reverse=(mode == "최신순"))


# ── 전역 헤더 + 상시 사이드바 (공부 모드가 아닐 때만 하단에서 호출) ──
def render_global_chrome():
    st.title("📚 나만의 지식 베이스")
    st.caption("문서를 모아두면 Claude Code(팀장)가 교육 자료로 정리해 줍니다.")

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

        # 현재 접속 역할 표시 + 로그아웃 (비번 게이트가 켜진 경우에만 의미 있음)
        if st.secrets.get("admin_password", "") or st.secrets.get("guest_password", ""):
            st.divider()
            _role_label = "관리자 (전체 권한)" if _is_admin() else "손님 (보기·입력)"
            st.caption(f"👤 {_role_label}")
            if st.button("로그아웃", key="logout_btn"):
                for _k in ("auth_ok", "role"):
                    st.session_state.pop(_k, None)
                st.query_params.pop("k", None)   # 저장해 둔 자동 입장도 해제
                st.rerun()


# ── 탭 본문: 각 탭을 렌더 함수로 정의 (맨 아래 그룹 네비에서 호출) ──

# ── 탭 1: 받은 문서 ────────────────────────────────────────────
def render_inbox():
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

                # 삭제: 2단계 확인 (관리자 전용)
                if _is_admin():
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
def render_sources():
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

        st.caption("등록한 RSS는 **📰 최근 뉴스** 탭에서 자동으로 수집됩니다.")

        if src["rss"]:
            st.caption(f"등록된 피드 {len(src['rss'])}개")
            for r in src["rss"]:
                c1, c2 = st.columns([5, 1])
                cat = f" · {r['category']}" if r.get("category") else ""
                c1.markdown(f"**{r['title']}**{cat}  \n<small>{r['url']}</small>", unsafe_allow_html=True)
                if _is_admin() and c2.button("삭제", key=f"delrss_{r['url']}"):
                    remove_rss(r["url"])
                    st.rerun()
        else:
            st.info("아직 등록된 RSS 피드가 없습니다.")

    # ── 전문가 SNS ──
    with col_sns:
        st.markdown("### 👤 전문가 SNS")
        with st.form("add_expert_form", clear_on_submit=True):
            ex_name = st.text_input("이름", placeholder="예: 홍길동")
            ex_platform = st.selectbox("플랫폼", ["youtube", "instagram", "x", "linkedin", "threads", "web"])
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
                # 자동수집(RSS) 상태 배지 — feed_url 연결 전까지 계속 표시
                kind = auto_collect_kind(e["url"])
                if e.get("feed_url"):
                    badge = "✅ 자동수집 중 (RSS 연결됨)"
                elif kind is None:
                    badge = "⚠️ 자동수집 불가 — 이 플랫폼은 RSS가 없어요. 아래 '게시물 → inbox'로 직접 가져오세요"
                elif kind == "youtube":
                    badge = "🔗 RSS 연결 가능 — 오른쪽 'RSS 연결' 버튼을 누르세요"
                else:
                    badge = "🔗 블로그 RSS 연결 가능 — Claude Code에 'RSS 피드 추가'로 등록하세요"
                c1.markdown(
                    f"**{e['name']}** ({e['platform']}){note}  \n"
                    f"<small>{e['url']}</small>  \n<small>{badge}</small>",
                    unsafe_allow_html=True,
                )
                # 유튜브인데 아직 RSS 미연결이면 즉시 연결 버튼
                if not e.get("feed_url") and kind == "youtube":
                    if c2.button("RSS 연결", key=f"linkrss_{e['url']}"):
                        sync_expert_feeds()
                        st.rerun()
                if _is_admin() and c2.button("삭제", key=f"delex_{e['url']}"):
                    remove_expert(e["url"])
                    st.rerun()
        else:
            st.info("아직 등록된 전문가가 없습니다.")

# ── 탭: 최근 뉴스 (뉴스 스트림 + 주간 브리핑) ───────────────────
def render_news():
    st.markdown("## 📰 최근 뉴스")
    st.caption(
        "구독한 RSS에서 모은 AI 소식이 쌓입니다(앱 열 때 하루 1회 자동 수집). "
        "지식 문서와 달리 '흘러가는 뉴스'이며, 주 1회 핵심만 골라 브리핑으로 정리합니다."
    )

    # 앱 열 때 하루 1회 자동 수집 (세션당 1회만 시도)
    if not st.session_state.get("news_daily_done"):
        got = collect_news_daily()
        st.session_state["news_daily_done"] = True
        if got:
            st.toast(f"오늘의 새 뉴스 {got}건을 수집했습니다.", icon="📰")

    news_db = load_news()
    digests = news_db.get("digests", [])

    # ── 1) 이번 주 통합 요약 (뉴닉 스타일) ──
    latest = latest_digest()
    if latest:
        _render_digest(latest)
        st.caption("🔄 새로 정리하려면 Claude Code에 **`이번 주 뉴스 정리해줘`** 라고 요청하세요.")
    else:
        st.info(
            "아직 이번 주 통합 요약이 없습니다.  \n"
            "**Claude Code에 `이번 주 뉴스 정리해줘`** 라고 요청하면 핵심 뉴스 3개(생각해볼 질문 포함)"
            " + 자투리 10개 + 필요 기술·공부거리로 정리해 드립니다."
        )

    # ── 2) 뉴스 스트림 (접기) ──
    st.divider()
    with st.expander("🗞 전체 뉴스 스트림 보기 (원본 수집 목록)", expanded=False):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("🔄 지금 수집", key="news_collect_btn"):
                with st.spinner("피드에서 새 글을 가져오는 중..."):
                    added = collect_news()
                st.success(f"새 뉴스 {added}건 수집") if added else st.info("새 글이 없습니다.")
                st.rerun()
        with c2:
            period = st.selectbox("기간", [7, 14, 30], format_func=lambda d: f"최근 {d}일", key="news_period")
        with c3:
            src_opts = ["전체"] + sources_in_news()
            sel_src = st.selectbox("출처", src_opts, key="news_source")

        c4, c5 = st.columns([2, 1])
        with c4:
            news_q = st.text_input("🔍 제목·요약 검색", placeholder="키워드 입력", key="news_q")
        with c5:
            news_sort = st.selectbox("정렬", ["최신순", "오래된순"], key="news_sort")

        src_filter = None if sel_src == "전체" else sel_src
        items = recent_items(days=period, source=src_filter)
        q = news_q.strip().lower()
        if q:
            items = [it for it in items
                     if q in (it.get("title") or "").lower()
                     or q in (it.get("summary") or "").lower()]
        items = _sort_items(items, news_sort, "published")
        st.markdown(f"**뉴스 {len(items)}건 · 최근 {period}일 · {news_sort}**")
        if not items:
            st.info("조건에 맞는 뉴스가 없습니다. 기간·출처·검색어를 바꿔보세요.")
        else:
            for it in items:
                pub = f" · {it['published'][:16]}" if it.get("published") else ""
                badge = "🗂" if it.get("in_digest") else ""
                st.markdown(
                    f"**[{it['title']}]({it['link']})**  \n"
                    f"<small>{badge} {it['source']} · {it.get('category','')}{pub}</small>",
                    unsafe_allow_html=True,
                )
                summ = (it.get("summary") or "").strip()
                if summ:
                    st.caption(summ[:180] + ("..." if len(summ) > 180 else ""))

    # ── 3) 지난 브리핑 아카이브 ──
    if len(digests) > 1:
        st.divider()
        st.markdown("### 🗂 지난 브리핑")
        for d in digests[1:]:
            with st.expander(f"📄 {d['title']}  ·  {d.get('period','')}  ({d.get('item_count',0)}건)"):
                _render_digest(d)

# ── 탭 2: 직접 메모 ────────────────────────────────────────────
def render_memo():
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
def render_kb():
    st.markdown("## 📚 지식 베이스")
    st.caption("Claude Code가 정리해 저장한 문서들입니다.")

    db = load_db()
    items = db.get("items", [])

    if not items:
        st.info("아직 저장된 지식이 없습니다. inbox에 문서를 넣고 Claude Code에 '정리해줘'라고 말해보세요.")
    else:
        all_tags = sorted({tag for item in items for tag in item.get("tags", [])})

        col_search, col_tag, col_sort = st.columns([2, 1, 1])
        with col_search:
            query = st.text_input(
                "🔍 제목·태그 검색", placeholder="키워드 입력 (예: ChatGPT, 프롬프트)", key="kb_search"
            )
        with col_tag:
            selected_tag = st.selectbox("태그 필터", ["전체"] + all_tags, key="kb_tag")
        with col_sort:
            sort_mode = st.selectbox("정렬", ["최신순", "오래된순", "제목순"], key="kb_sort")

        # 검색어가 있으면 Curator.search() 결과를 기준 목록으로, 없으면 전체
        base = Curator().search(query.strip()) if query.strip() else items
        # 태그 필터 AND 결합
        filtered = base if selected_tag == "전체" else [i for i in base if selected_tag in i.get("tags", [])]
        # 정렬(생성일/제목) — reversed 루프 대신 명시적 정렬
        filtered = _sort_items(filtered, sort_mode, "created_at")

        caption = f"{len(filtered)}개 문서  ·  {sort_mode}"
        if query.strip():
            caption += f"  ·  '{query.strip()}' 검색 결과"
        st.caption(caption)

        if not filtered:
            st.info("조건에 맞는 문서가 없습니다. 검색어나 태그 필터를 바꿔보세요.")

        for item in filtered:
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

# ── 픽셀 스타일 썸네일 (실제 이미지가 없으므로 결정적 생성) ────────
# Notion의 스티커 팔레트는 '장식용'으로만 허용되므로 여기서만 컬러를 쓴다.
# seed가 같으면 항상 같은 그림 → 커리큘럼마다 고유하고 일관된 픽셀 아이콘.
_THUMB_PAIRS = [
    ("#eef4ff", "#62aef0"),  # sky
    ("#f3ecfb", "#a06be0"),  # purple
    ("#ffeaf6", "#ff64c8"),  # pink
    ("#fff0e6", "#dd5b00"),  # orange
    ("#e8f6f5", "#2a9d99"),  # teal
    ("#e9f7ed", "#1aae39"),  # green
]


# 7×7 픽셀 아이콘 비트맵 (# = 채움). 제목 키워드로 모양을 고른다.
_PIX_ICONS = {
    "camera": [".......", ".##....", "#######", "#.....#", "#.###.#", "#.###.#", "#######"],
    "bolt":   ["....##.", "...##..", "..##...", ".#####.", "...##..", "..##...", ".##...."],
    "shield": [".#####.", "#######", "#######", "#######", ".#####.", "..###..", "...#..."],
    "code":   ["..#.#..", ".#...#.", "#.....#", ".......", "#.....#", ".#...#.", "..#.#.."],
    "chat":   ["#######", "#.....#", "#.#.#.#", "#.....#", "#####.#", "...##..", "..#...."],
    "robot":  ["...#...", ".#####.", "#.#.#.#", "#######", "#.###.#", "#######", ".#...#."],
    "book":   ["##...##", "#.#.#.#", "#.#.#.#", "#.#.#.#", "#.#.#.#", "#.#.#.#", "##...##"],
    "spark":  ["...#...", "..###..", ".#####.", "#######", ".#####.", "..###..", "...#..."],
}

# (키워드들, 아이콘) — 위에서부터 먼저 매칭. 더 구체적인 주제를 앞에 둔다.
_ICON_RULES = [
    (("이미지", "영상", "사진", "그림", "디자인", "미드저니", "미디어", "동영상"), "camera"),
    (("안전", "보안", "저작권", "개인정보", "환각", "윤리"), "shield"),
    (("에이전트", "agent", "mcp", "노코드", "봇", "로봇"), "robot"),
    (("자동화", "워크플로", "automation", "실전", "자동"), "bolt"),
    (("개발", "코드", "코딩", "배경", "언어", "git", "html", "css", "터미널", "api", "서버", "마크다운"), "code"),
    (("프롬프트", "대화", "gpt", "claude", "멋지게", "활용", "사용"), "chat"),
    (("ai", "트렌드", "지형도", "미래", "인공지능", "기초"), "spark"),
]


def _icon_key_for(title: str) -> str:
    """제목에서 키워드를 찾아 어울리는 픽셀 아이콘 키를 고른다(없으면 책)."""
    t = (title or "").lower()
    for kws, key in _ICON_RULES:
        if any(k in t for k in kws):
            return key
    return "book"


def _pixel_thumb(seed: str, title: str, height: int = 104) -> str:
    """제목에 맞는 7×7 픽셀 아이콘 썸네일 HTML. 색은 seed로 결정(일관·고유)."""
    import random as _random
    bg, fg = _THUMB_PAIRS[_random.Random(seed or "x").randrange(len(_THUMB_PAIRS))]
    grid = _PIX_ICONS[_icon_key_for(title)]
    cells = "".join(
        f'<div style="background:{fg if ch == "#" else "transparent"};border-radius:2px;"></div>'
        for row in grid for ch in row
    )
    return (
        f'<div style="height:{height}px;background:{bg};border-radius:8px;'
        f'display:flex;align-items:center;justify-content:center;margin-bottom:0.7rem;">'
        f'<div style="display:grid;grid-template-columns:repeat(7,10px);'
        f'grid-template-rows:repeat(7,10px);gap:2px;">{cells}</div></div>'
    )


def _render_session_doc_collapsible(doc: str) -> None:
    """단일 강 교재 마크다운을 H3(### ) 소제목 단위로 접어 렌더한다.

    긴 교재를 한 덩어리로 쏟지 않고 '이번 강 소개·학습 목표·핵심 학습 내용·
    실습 안내' 등으로 접어, 슬라이드와 대조하며 필요한 부분만 펼쳐 본다.
    소개·학습 목표·(첫) 핵심 학습 내용만 기본 펼침, 나머지는 접힘.
    """
    head: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    cur_title: str | None = None
    cur_body: list[str] = []
    for ln in doc.split("\n"):
        if ln.startswith("### "):
            if cur_title is None:
                head = cur_body
            else:
                sections.append((cur_title, cur_body))
            cur_title = ln[4:].strip()
            cur_body = []
        else:
            cur_body.append(ln)
    if cur_title is None:
        head = cur_body
    else:
        sections.append((cur_title, cur_body))

    if any(s.strip() for s in head):
        st.markdown("\n".join(head))

    core_seen = 0
    core_total = sum(1 for t, _ in sections if t == "핵심 학습 내용")
    for title, body in sections:
        label = title
        expanded = title in ("이번 강 소개", "학습 목표")
        if title == "핵심 학습 내용":
            core_seen += 1
            if core_total > 1:
                label = f"핵심 학습 내용 ({core_seen})"
            expanded = expanded or core_seen == 1  # 첫 핵심 내용만 펼침
        with st.expander(label, expanded=expanded):
            st.markdown("\n".join(body))


def _render_textbook(curriculum, sessions, selected_week):
    """교재 본문(전체 개요 또는 특정 강)을 렌더한다. 독립 스크롤 컨테이너 안에서 호출."""
    if selected_week == 0:
        # 전체: 커리큘럼 개요 + 각 세션 요약
        st.markdown(f"# {curriculum['title']}")
        st.markdown(
            f"> **수강 대상**: {curriculum.get('target_audience','입문자')}  |  "
            f"**전체 {len(sessions)}강**"
        )
        st.markdown(curriculum.get("description", ""))
        st.divider()
        st.markdown("## 커리큘럼 구성")
        for ses in sessions:
            with st.expander(f"**{ses['week']}강: {ses['title']}** — {ses.get('duration','60분')}"):
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
                        where = (f"{cr.get('title','')} {cr.get('week')}강"
                                 if cr.get("week") else cr.get("title", ""))
                        note = (cr.get("note") or "").strip()
                        st.markdown(
                            f"- {where} · {cr.get('relation','연결')}"
                            + (f" — {note}" if note else "")
                        )
    else:
        # 특정 강 교재 — 소제목 단위로 접어 슬라이드와 대조하기 쉽게
        ses = next((s for s in sessions if s["week"] == selected_week), None)
        if ses:
            _render_session_doc_collapsible(build_session_doc(curriculum, ses))
        else:
            st.warning("해당 강 세션을 찾을 수 없습니다.")


# ── 탭 4: 커리큘럼 ─────────────────────────────────────────────
def render_curriculum():
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
                [it for it in loaded
                 if it[1].get("track", "main") not in ("elective", "special")],
                key=_order_key,
            )
            elective_items = [it for it in loaded
                              if it[1].get("track") == "elective"]
            special_items = [it for it in loaded
                             if it[1].get("track") == "special"]

            def _render_cur_card(entry, cur_data):
                n_sessions = len(cur_data.get("sessions", []))
                audience = cur_data.get("target_audience", "입문자")
                desc = cur_data.get("description", "")
                updated = cur_data.get("updated_at", "")[:10]
                order = cur_data.get("order")
                level = cur_data.get("level", "")
                prereq = cur_data.get("prerequisites", [])

                if cur_data.get("track") == "special":
                    badge = "특별 강의"
                elif cur_data.get("track") == "elective":
                    badge = "선택 트랙"
                elif isinstance(order, int):
                    badge = f"{order}단계"
                else:
                    badge = ""
                if level:
                    badge = f"{badge} · {level}" if badge else level

                def _esc(s: str) -> str:
                    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                badge_html = (
                    f'<span style="display:inline-block;background:#f6f5f4;color:#0075de;'
                    f'font-size:0.72rem;font-weight:600;padding:2px 8px;border-radius:9999px;'
                    f'margin-bottom:0.4rem;">🧭 {_esc(badge)}</span>'
                    if badge else ""
                )
                # 고정 높이 본문: 썸네일 + 배지 + 제목(2줄 클램프) + 메타 + 설명(2줄 클램프)
                body = (
                    _pixel_thumb(entry.get("id") or entry["title"], entry["title"])
                    + '<div style="height:142px;display:flex;flex-direction:column;overflow:hidden;">'
                    + badge_html
                    + f'<div style="font-size:1.05rem;font-weight:700;color:var(--ink,#1a1a1a);'
                      f'line-height:1.3;margin-bottom:0.25rem;display:-webkit-box;-webkit-line-clamp:2;'
                      f'-webkit-box-orient:vertical;overflow:hidden;">{_esc(entry["title"])}</div>'
                    + f'<div style="font-size:0.78rem;color:#615d59;margin-bottom:0.35rem;">'
                      f'{_esc(audience)} · 총 {n_sessions}강</div>'
                    + (f'<div style="font-size:0.82rem;color:#615d59;line-height:1.45;flex:1;'
                       f'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;'
                       f'overflow:hidden;">{_esc(desc)}</div>' if desc else "")
                    + '</div>'
                )
                with st.container(border=True):
                    st.markdown(body, unsafe_allow_html=True)
                    if st.button("열기 →", key=f"open_{entry['id']}",
                                 use_container_width=True, type="primary"):
                        st.session_state["cur_selected_id"] = entry["id"]
                        st.session_state["cur_selected_week"] = 0
                        st.rerun()

            def _render_grid(items):
                # 항상 3열 고정 → 항목이 적은 선택 트랙도 메인 경로와 같은 카드 폭
                cols = st.columns(3)
                for i, (entry, cur_data) in enumerate(items):
                    with cols[i % 3]:
                        _render_cur_card(entry, cur_data)

            if main_items:
                st.markdown("#### 🎯 메인 학습 경로")
                st.caption("아래 순서대로 수강하는 것을 권장합니다.")
                _render_grid(main_items)

            if special_items:
                st.divider()
                st.markdown("#### 🚀 특별 강의")
                st.caption("실무 주제별 심화 특강입니다. 관심 주제만 골라 단독으로 들을 수 있습니다.")
                _render_grid(special_items)

            if elective_items:
                st.divider()
                st.markdown("#### 🎨 선택 트랙")
                st.caption("메인 경로와 무관하게 단독으로 들을 수 있는 과정입니다.")
                _render_grid(elective_items)

        st.divider()
        with st.expander("💬 Claude Code 명령어 가이드"):
            st.code("""\
[제목] 커리큘럼 만들어줘      → 새 커리큘럼 생성
[N]강 세션 추가: [제목]       → 세션 추가
[N]강에 [파일명] 연결해줘     → 지식 문서 연결
[N]강 목표 바꿔줘: [목표]     → 학습 목표 수정
[N]강 활동 추가: [활동]       → 활동 추가
[N]강 삭제해줘                → 세션 삭제
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

        # ── 공부 모드: 헤더/네비/메타는 전부 사이드바로, 본문은 교재|슬라이드만 ──
        order = curriculum.get("order")
        level = curriculum.get("level", "")
        if curriculum.get("track") == "special":
            pos = "특별 강의"
        elif curriculum.get("track") == "elective":
            pos = "선택 트랙"
        elif isinstance(order, int):
            pos = f"메인 경로 {order}단계"
        else:
            pos = ""
        if level:
            pos = f"{pos} · {level}" if pos else level
        _id_title = {c["id"]: c["title"] for c in curricula}

        with st.sidebar:
            st.divider()
            if st.button("← 커리큘럼 목록", key="back_to_dashboard",
                         use_container_width=True):
                st.session_state["cur_selected_id"] = None
                st.rerun()
            st.markdown(f"### 📚 {curriculum['title']}")
            st.caption(
                (f"🧭 {pos} · " if pos else "")
                + f"{curriculum.get('target_audience','입문자')} · "
                f"총 {len(sessions)}강"
            )
            _prereq = curriculum.get("prerequisites", [])
            if _prereq:
                st.caption("📋 선수: " + ", ".join(_id_title.get(p, p) for p in _prereq))

            st.markdown("**강 선택**")
            for ses in sessions:
                is_active = selected_week == ses["week"]
                if st.button(
                    f"{ses['week']}강 · {ses['title']}",
                    key=f"ses_w{ses['week']}_{selected_entry['id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["cur_selected_week"] = ses["week"]
                    # 슬라이드 인덱스 초기화
                    st.session_state[f"slide_idx_{selected_entry['id']}_{ses['week']}"] = 0
                    st.rerun()

            # 전체 보기(교재·슬라이드 전체 읽기) — 강 목록 맨 아래
            st.divider()
            if st.button(
                "📖 전체 보기 (교재·슬라이드 전체)",
                key="ses_all",
                use_container_width=True,
                type="primary" if selected_week == 0 else "secondary",
            ):
                st.session_state["cur_selected_week"] = 0
                st.rerun()

            _next = [n for n in curriculum.get("next", []) if n in _id_title]
            if _next:
                st.divider()
                st.caption("➡️ 다음 권장 과정")
                for nid in _next:
                    if st.button(f"{_id_title[nid]} →", key=f"next_{nid}",
                                 use_container_width=True):
                        st.session_state["cur_selected_id"] = nid
                        st.session_state["cur_selected_week"] = 0
                        st.rerun()

        all_slides = load_slides(curriculum)

        if selected_week == 0:
            # ── 전체 보기: 탭으로 교재 전체 / 슬라이드 전체 (각각 자체 스크롤) ──
            st.caption("📖 과정 전체를 한 번에 읽는 모드입니다. 왼쪽에서 특정 강을 고르면 공부 모드로 바뀝니다.")
            tab_doc_all, tab_deck_all = st.tabs(["📖 교재 전체", "🖼 슬라이드 전체"])
            with tab_doc_all:
                # 모든 강의 지식까지 내장된 전체 교재(자체 스크롤 컨테이너)
                with st.container(height=600):
                    st.markdown(build_markdown_doc(curriculum))
            with tab_deck_all:
                if not all_slides:
                    st.info('슬라이드가 없습니다. Claude Code에 `"커리큘럼 슬라이드 업데이트해줘"`라고 요청하세요.')
                else:
                    st.caption("⛶ 전체화면 버튼 또는 ← → 화살표 키로 넘길 수 있어요.")
                    _render_slide_deck(all_slides, height=960)
        else:
            # ── 개별 강(공부 모드): 교재 | 슬라이드 2열, 고정 높이로 페이지 스크롤 최소화 ──
            tab_doc, tab_slides = st.columns(2)
            with tab_doc:
                st.markdown("#### 📖 교재")
                with st.container(height=560):
                    _render_textbook(curriculum, sessions, selected_week)
            with tab_slides:
                st.markdown("#### 🖼 슬라이드")
                if not all_slides:
                    st.info('슬라이드가 없습니다. Claude Code에 `"커리큘럼 슬라이드 업데이트해줘"`라고 요청하세요.')
                else:
                    def _belongs(s):
                        if s.get("type") == "title":
                            return True
                        # week 필드 우선(견고), 없으면 section 부분문자열 폴백
                        if s.get("week") is not None:
                            return s.get("week") == selected_week
                        return f"{selected_week}강" in s.get("section", "")
                    view_slides = [s for s in all_slides if _belongs(s)]
                    if not view_slides:
                        st.info("이 강에 해당하는 슬라이드가 없습니다.")
                    else:
                        st.caption("⛶ 전체화면 · ← → 키로 넘기기")
                        _render_slide_deck(view_slides, height=840)

# ── 탭 5: 보조 프로그램 ────────────────────────────────────────
def render_aux():
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

    aux_all = load_aux_db().get("items", [])
    if not aux_all:
        st.info("아직 등록된 보조 프로그램이 없습니다. 위 '추가' 폼을 쓰거나, "
                "Claude Code에 `\"[툴 링크] 보조 프로그램에 추가해줘\"`라고 말해보세요.")
    else:
        ac_q, ac_sort = st.columns([2, 1])
        with ac_q:
            aux_q = st.text_input("🔍 이름·설명·태그 검색", placeholder="키워드 입력", key="aux_q")
        with ac_sort:
            aux_sort = st.selectbox("정렬", ["최신순", "오래된순", "제목순"], key="aux_sort")

        q = aux_q.strip().lower()
        aux_items = aux_all
        if q:
            aux_items = [
                i for i in aux_items
                if q in (i.get("title") or "").lower()
                or q in (i.get("description") or "").lower()
                or any(q in (t or "").lower() for t in i.get("tags", []))
            ]
        # 카테고리 내 카드 순서가 정렬을 따르도록 미리 정렬
        aux_items = _sort_items(aux_items, aux_sort, "added_at")

        st.caption(f"총 {len(aux_items)}개  ·  {aux_sort}")
        if not aux_items:
            st.info("조건에 맞는 보조 프로그램이 없습니다. 검색어를 바꿔보세요.")
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
                        if _is_admin():
                            link_c, del_c = st.columns([3, 1])
                        else:
                            link_c, del_c = st.container(), None
                        with link_c:
                            if item.get("url"):
                                st.link_button("열기 ↗", item["url"], use_container_width=True)
                        if del_c is not None:
                            with del_c:
                                if st.button("🗑", key=f"del_aux_{item['id']}",
                                             use_container_width=True, help="삭제"):
                                    delete_aux_program(item["id"])
                                    st.rerun()

# ── 탭 6: 에이전트 ─────────────────────────────────────────────
def render_agents():
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


# ── 상단 그룹 네비 (그룹바 + 그룹별 하위탭) ────────────────────────
GROUPS = {
    "📚 지식·학습": [
        ("📚 지식 베이스", render_kb),
        ("📰 최근 뉴스", render_news),
        ("📋 커리큘럼", render_curriculum),
        ("🧰 보조 프로그램", render_aux),
    ],
    "📥 수집": [
        ("📥 받은 문서", render_inbox),
        ("✏️ 직접 메모", render_memo),
        ("📡 소스", render_sources),
    ],
    "⚙ 시스템": [
        ("🤖 에이전트", render_agents),
    ],
}

# 공부 모드: 커리큘럼이 선택돼 있으면 전역 헤더·사이드바·그룹 네비를 모두
# 건너뛰고 전용 화면(사이드바 세션 네비 + 본문 교재|슬라이드)으로 간다.
# 빠져나가기는 상세 화면의 "← 커리큘럼 목록" 버튼(cur_selected_id=None).
if st.session_state.get("cur_selected_id"):
    render_curriculum()
else:
    render_global_chrome()
    _group = st.segmented_control(
        "메뉴", list(GROUPS), default="📚 지식·학습",
        key="nav_group", label_visibility="collapsed",
    )
    _group = _group or "📚 지식·학습"  # 해제 시 None → 폴백
    _subtabs = GROUPS[_group]
    for _tab, (_label, _render_fn) in zip(st.tabs([t for t, _ in _subtabs]), _subtabs):
        with _tab:
            _render_fn()
