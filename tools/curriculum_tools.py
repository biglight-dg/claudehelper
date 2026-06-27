"""커리큘럼 데이터 저장/로드 유틸리티."""

from datetime import datetime

from tools import storage

CURRICULA_REL = "curricula"
CURRICULUM_DB_REL = "curricula/curriculum_db.json"


def _safe_filename(title: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in title).strip()


# ── 인덱스 ──────────────────────────────────────────────────────

def load_curriculum_db() -> dict:
    return storage.read_json(CURRICULUM_DB_REL, {"curricula": []})


def save_curriculum_db(db: dict) -> None:
    storage.write_json(CURRICULUM_DB_REL, db)


def _upsert_index(curriculum: dict) -> None:
    """인덱스에 커리큘럼 항목을 추가하거나 갱신한다."""
    db = load_curriculum_db()
    entry = {
        "id": curriculum["id"],
        "title": curriculum["title"],
        "path": curriculum["_path"],
        "track": curriculum.get("track", "main"),
        "order": curriculum.get("order"),
        "level": curriculum.get("level", ""),
    }
    for i, item in enumerate(db["curricula"]):
        if item["id"] == curriculum["id"]:
            db["curricula"][i] = entry
            save_curriculum_db(db)
            return
    db["curricula"].append(entry)
    save_curriculum_db(db)


# ── 커리큘럼 파일 ────────────────────────────────────────────────

def new_curriculum(title: str, description: str = "", target_audience: str = "입문자",
                   track: str = "main", order: int | None = None, level: str = "",
                   prerequisites: list[str] | None = None,
                   next: list[str] | None = None) -> dict:
    """새 커리큘럼 딕셔너리를 만든다 (저장은 save_curriculum으로).

    학습 경로 메타:
    - track: "main"(메인 학습 경로) | "elective"(독립 선택 트랙)
    - order: 메인 트랙 내 권장 수강 순서(1부터). elective는 None
    - level: 단계 라벨(기초·안전·실전·심화·교양·콘텐츠 제작 등)
    - prerequisites / next: 선수·다음 권장 과정의 커리큘럼 id 목록
    """
    safe = _safe_filename(title)
    path = f"{CURRICULA_REL}/{safe}.json"
    now = datetime.now().isoformat()
    return {
        "id": f"cur_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "title": title,
        "description": description,
        "target_audience": target_audience,
        "track": track,
        "order": order,
        "level": level,
        "prerequisites": prerequisites or [],
        "next": next or [],
        "created_at": now,
        "updated_at": now,
        "sessions": [],
        "generated": {
            "slides_path": None,
            "pptx_path": None,
            "last_generated": None,
        },
        "_path": path,
    }


def load_curriculum(path: str) -> dict:
    rel = storage.to_relpath(path)
    data = storage.read_json(rel)
    if data is None:
        raise FileNotFoundError(f"커리큘럼 파일을 찾을 수 없습니다: {path}")
    data["_path"] = rel
    return data


def save_curriculum(curriculum: dict) -> None:
    """커리큘럼을 JSON 파일로 저장하고 인덱스를 갱신한다."""
    curriculum["updated_at"] = datetime.now().isoformat()
    rel = storage.to_relpath(curriculum["_path"])
    curriculum["_path"] = rel  # 경로를 상대경로로 정규화(인덱스도 같이 통일)
    # _path는 내부 메타 필드 — JSON에서 제외
    data = {k: v for k, v in curriculum.items() if k != "_path"}
    storage.write_json(rel, data)
    _upsert_index(curriculum)


def delete_curriculum(curriculum_id: str) -> bool:
    """커리큘럼을 삭제하고 인덱스에서 제거한다. 성공 여부 반환."""
    db = load_curriculum_db()
    entry = next((c for c in db["curricula"] if c["id"] == curriculum_id), None)
    if not entry:
        return False
    rel = storage.to_relpath(entry["path"])
    storage.delete(rel)
    # 슬라이드 파일도 삭제
    if rel.endswith(".json"):
        storage.delete(rel[:-5] + "_slides.json")
    db["curricula"] = [c for c in db["curricula"] if c["id"] != curriculum_id]
    save_curriculum_db(db)
    return True


# ── 세션 헬퍼 ────────────────────────────────────────────────────

def new_session(week: int, title: str, objectives: list[str] | None = None,
                duration: str = "60분") -> dict:
    """세션 딕셔너리를 만든다."""
    return {
        "id": f"ses_w{week}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')[:18]}",
        "week": week,
        "title": title,
        "objectives": objectives or [],
        "duration": duration,
        "knowledge_refs": [],
        "references": [],
        "cross_refs": [],
        "activities": [],
        "notes": "",
    }


def get_session(curriculum: dict, week: int) -> dict | None:
    return next((s for s in curriculum["sessions"] if s["week"] == week), None)


def add_session(curriculum: dict, session: dict) -> None:
    """세션을 추가하고 week 순으로 정렬한다."""
    curriculum.setdefault("sessions", []).append(session)
    curriculum["sessions"].sort(key=lambda s: s["week"])


def remove_session(curriculum: dict, week: int, renumber: bool = True) -> bool:
    """해당 week 세션을 제거한다. renumber=True(기본)면 뒤 강의 week를 1씩 당긴다.

    반환: 제거 성공 여부. 저장은 호출부에서 save_curriculum()으로 한다.
    """
    sessions = curriculum.get("sessions", [])
    target = next((s for s in sessions if s["week"] == week), None)
    if target is None:
        return False
    sessions.remove(target)
    if renumber:
        for s in sessions:
            if s["week"] > week:
                s["week"] -= 1
    sessions.sort(key=lambda s: s["week"])
    return True


# 강을 쪼갤 때 새 강으로 재배분되는 리스트형 필드(교재 .md는 건드리지 않음)
_SPLIT_FIELDS = ("knowledge_refs", "objectives", "concepts",
                 "activities", "references", "cross_refs")


def split_session(curriculum: dict, week: int, parts: list[dict]) -> dict:
    """한 강(week)을 여러 강으로 분할한다.

    교재 본문(.md 파일)은 절대 건드리지 않고, 강의 메타 필드만 parts 명세대로
    재배분한다. 첫 part는 원본 week 번호를 유지하고, 이후 part는 week+1,
    week+2…를 갖는다. 원본보다 뒤에 있던 강들은 (len(parts)-1)만큼 week가
    뒤로 밀린다. 원본의 part(파트명)·duration은 명시하지 않은 새 강에 상속된다.

    parts[i] 예: {"title": "...", "knowledge_refs": [...], "objectives": [...],
                  "concepts": [...], "activities": [...], "references": [...],
                  "cross_refs": [...], "duration": "30분", "notes": "..."}
    title은 필수. 생략한 필드는 빈 값으로 둔다. 저장은 호출부에서
    save_curriculum() + 슬라이드 재생성으로 한다.

    반환: {"new_weeks": [int...], "shift": int, "cross_ref_warnings": [str...]}
    (cross_ref_warnings는 week가 밀려 어긋날 수 있는 참조 경고 — 자동 수정 안 함)
    """
    if len(parts) < 2:
        raise ValueError("split_session: parts는 2개 이상이어야 합니다(분할 의미).")
    sessions = curriculum.get("sessions", [])
    origin = next((s for s in sessions if s["week"] == week), None)
    if origin is None:
        raise ValueError(f"{week}강 세션을 찾을 수 없습니다.")

    shift = len(parts) - 1
    inherited_part = origin.get("part")
    inherited_duration = origin.get("duration", "60분")

    # 1) 원본보다 뒤 강의 week를 shift만큼 뒤로 민다
    for s in sessions:
        if s["week"] > week:
            s["week"] += shift
    # 2) 원본 제거
    sessions.remove(origin)

    # 3) 각 part를 새 강으로 생성 (교재 .md는 knowledge_refs 경로만 재배분)
    new_weeks = []
    for idx, part in enumerate(parts):
        w = week + idx
        title = (part.get("title") or "").strip()
        if not title:
            raise ValueError(f"parts[{idx}]에 title이 필요합니다.")
        ses = new_session(week=w, title=title,
                          objectives=list(part.get("objectives", [])),
                          duration=part.get("duration", inherited_duration))
        for f in _SPLIT_FIELDS:
            if f == "objectives":
                continue  # 이미 new_session에 전달됨
            ses[f] = list(part.get(f, []))
        ses["notes"] = part.get("notes", "")
        if inherited_part:
            ses["part"] = inherited_part
        add_session(curriculum, ses)
        new_weeks.append(w)

    warnings = _split_cross_ref_warnings(curriculum, week, shift)
    return {"new_weeks": new_weeks, "shift": shift, "cross_ref_warnings": warnings}


def _split_cross_ref_warnings(curriculum: dict, week: int, shift: int) -> list[str]:
    """분할로 week가 밀려 참조가 어긋날 수 있는 cross_refs를 경고 문자열로 모은다.

    이 커리큘럼(id)을 가리키며 원본 week보다 뒤(week 큰)를 가리키는 cross_ref는
    분할 후 한 강(=shift)만큼 어긋난다. 자동 수정하지 않고 호출자에게 알린다.
    """
    cid = curriculum.get("id")
    warnings: list[str] = []
    if not cid:
        return warnings
    for entry in load_curriculum_db().get("curricula", []):
        try:
            other = load_curriculum(entry["path"])
        except Exception:
            continue
        for ses in other.get("sessions", []):
            for cr in ses.get("cross_refs", []):
                if (cr.get("curriculum_id") == cid
                        and isinstance(cr.get("week"), int)
                        and cr["week"] > week):
                    warnings.append(
                        f"[{other.get('title')}] {ses.get('week')}강의 연결 통로가 "
                        f"이 커리큘럼 {cr['week']}강을 가리킵니다 → 분할 후 "
                        f"{cr['week'] + shift}강으로 조정해야 맞습니다."
                    )
    return warnings


def add_session_reference(curriculum: dict, week: int, ref: dict) -> bool:
    """특정 강 세션의 references 리스트에 외부 참고자료(유튜브·링크)를 추가한다.

    ref 예시: {"type": "youtube", "title": ..., "description": ...,
               "url": ..., "channel": ...}
    같은 URL이 이미 있으면 중복 추가하지 않는다. 저장은 호출부에서
    save_curriculum()으로 한다. 세션을 찾으면 True, 없으면 False.
    """
    ses = get_session(curriculum, week)
    if ses is None:
        return False
    refs = ses.setdefault("references", [])
    url = (ref.get("url") or "").strip()
    if url and any((r.get("url") or "").strip() == url for r in refs):
        return True  # 이미 있음 — 성공으로 간주
    entry = dict(ref)
    entry.setdefault("added_at", datetime.now().isoformat())
    refs.append(entry)
    return True


# ── 슬라이드 JSON ────────────────────────────────────────────────

def load_slides(curriculum: dict) -> list[dict] | None:
    path = curriculum.get("generated", {}).get("slides_path")
    if not path:
        return None
    data = storage.read_json(storage.to_relpath(path))
    if data is None:
        return None
    return data.get("slides", [])


def save_slides(curriculum: dict, slides: list[dict]) -> str:
    """슬라이드 JSON을 저장하고 curriculum.generated를 업데이트한다."""
    safe = _safe_filename(curriculum["title"])
    rel = f"{CURRICULA_REL}/{safe}_slides.json"
    now = datetime.now().isoformat()
    storage.write_json(rel, {
        "curriculum_title": curriculum["title"],
        "generated_at": now,
        "slides": slides,
    })
    curriculum["generated"]["slides_path"] = rel
    curriculum["generated"]["last_generated"] = now
    return rel


# ── 마크다운 문서 생성 ───────────────────────────────────────────

_REF_ICON = {"youtube": "▶", "tool": "🧰", "link": "🔗"}


def _references_md(references: list[dict]) -> list[str]:
    """세션 references를 교재용 마크다운 줄 목록으로 변환한다.

    각 항목은 클릭하면 브라우저로 열리는 링크. 설명이 있으면 한 줄 덧붙인다.
    """
    if not references:
        return []
    lines = ["### 참고 자료 (영상·링크)", "",
             "아래 자료는 제목을 클릭하면 브라우저(크롬)에서 바로 열립니다.", ""]
    for ref in references:
        icon = _REF_ICON.get(ref.get("type", "link"), "🔗")
        title = ref.get("title") or ref.get("url", "링크")
        url = ref.get("url", "")
        channel = ref.get("channel", "")
        meta = f" · {channel}" if channel else ""
        lines.append(f"- {icon} [{title}]({url}){meta}")
        desc = (ref.get("description") or "").strip()
        if desc:
            short = desc if len(desc) <= 160 else desc[:158].rstrip() + "…"
            lines.append(f"    - {short}")
    lines.append("")
    return lines


_RELATION_ICON = {"심화": "⬆️", "전제": "⬅️", "연결": "↔️", "복습": "🔁"}


def _id_to_title() -> dict[str, str]:
    """커리큘럼 id → 제목 매핑(인덱스 기반). 끊긴 링크는 호출부에서 처리."""
    return {c["id"]: c["title"] for c in load_curriculum_db().get("curricula", [])}


def _prereq_next_md(curriculum: dict) -> list[str]:
    """커리큘럼 상단에 표시할 학습 경로(순서·선수·다음) 마크다운 줄."""
    track = curriculum.get("track", "main")
    order = curriculum.get("order")
    level = curriculum.get("level", "")
    prereq = curriculum.get("prerequisites", [])
    nxt = curriculum.get("next", [])
    if not (track in ("elective", "special") or order or prereq or nxt or level):
        return []

    titles = _id_to_title()
    lines = ["### 학습 경로", ""]
    if track == "special":
        path_label = "특별 강의 (실무 주제별 심화 특강 · 단독 수강 가능)"
    elif track == "elective":
        path_label = "독립 선택 트랙 (메인 과정과 무관하게 단독 수강 가능)"
    elif order:
        path_label = f"메인 학습 경로 {order}단계"
    else:
        path_label = "메인 학습 경로"
    if level:
        path_label += f" · {level}"
    lines.append(f"- **위치**: {path_label}")
    if prereq:
        names = ", ".join(titles.get(pid, pid) for pid in prereq)
        lines.append(f"- **선수 과정**: {names}")
    if nxt:
        names = ", ".join(titles.get(nid, nid) for nid in nxt)
        lines.append(f"- **다음 권장 과정**: {names}")
    lines.append("")
    return lines


def _cross_refs_md(cross_refs: list[dict]) -> list[str]:
    """세션의 cross_refs(과정 간 연결 통로)를 마크다운 줄 목록으로 변환한다."""
    if not cross_refs:
        return []
    lines = ["### 🔗 연결 통로", "",
             "이 강 내용은 다른 과정의 아래 지점과 이어집니다.", ""]
    for ref in cross_refs:
        icon = _RELATION_ICON.get(ref.get("relation", "연결"), "↔️")
        title = ref.get("title", "")
        week = ref.get("week")
        relation = ref.get("relation", "연결")
        where = f"{title} {week}강" if week else title
        note = (ref.get("note") or "").strip()
        tail = f" — {note}" if note else ""
        lines.append(f"- {icon} **{where}** · {relation}{tail}")
    lines.append("")
    return lines


def build_markdown_doc(curriculum: dict) -> str:
    """커리큘럼을 교재 스타일 Markdown으로 변환한다.

    - 각 세션에 연결된 지식 파일의 전체 내용을 포함
    - ~입니다/~합니다 교재 어투
    - 표, 예시, 활동 안내 포함
    """
    lines = [
        f"# {curriculum['title']}",
        "",
        (f"> **수강 대상**: {curriculum.get('target_audience', '입문자')}"
         f"  |  **최종 업데이트**: {curriculum.get('updated_at', '')[:10]}"),
        "",
        curriculum.get("description", ""),
        "",
    ]
    lines += _prereq_next_md(curriculum)
    lines += [
        "---",
        "",
        "## 목차",
        "",
    ]

    sessions = sorted(curriculum.get("sessions", []), key=lambda s: s["week"])
    for ses in sessions:
        lines.append(f"- [{ses['week']}강: {ses['title']}](#{ses['week']}강-{ses['title'].replace(' ', '-')})")
    lines += ["", "---", ""]

    # 파트별 강 범위 미리 계산 (Part A/B 헤더용)
    part_weeks: dict[str, list[int]] = {}
    for ses in sessions:
        if ses.get("part"):
            part_weeks.setdefault(ses["part"], []).append(ses["week"])

    seen_refs: set[str] = set()
    current_part = None

    for ses in sessions:
        # 파트 전환 시 상위(H1) 파트 헤더 삽입
        part = ses.get("part")
        if part and part != current_part:
            current_part = part
            weeks = part_weeks.get(part, [])
            week_range = (f"{min(weeks)}~{max(weeks)}강"
                          if weeks and min(weeks) != max(weeks)
                          else (f"{weeks[0]}강" if weeks else ""))
            suffix = f"  ·  {week_range}" if week_range else ""
            lines += [f"# {part}{suffix}", "", "---", ""]

        lines.append(f"## {ses['week']}강: {ses['title']}")
        lines.append("")
        lines.append(f"**수업 시간**: {ses.get('duration', '60분')}")
        lines.append("")

        # 학습 목표 (교재 어투)
        if ses.get("objectives"):
            lines.append("### 학습 목표")
            lines.append("")
            lines.append(
                f"이번 {ses['week']}강을 마치면 다음 내용을 이해하고 실습할 수 있습니다."
            )
            lines.append("")
            for obj in ses["objectives"]:
                lines.append(f"- {obj}")
            lines.append("")

        # 연결된 지식 파일 전체 내용 삽입
        for ref_path in ses.get("knowledge_refs", []):
            ref_key = storage.to_relpath(ref_path)
            if ref_key in seen_refs:
                continue
            content = storage.read_text(ref_key)
            if content is None:
                continue
            seen_refs.add(ref_key)

            lines.append("### 핵심 학습 내용")
            lines.append("")

            # H1 제목 제거, H2→H4, H3→H5 로 변환해서 계층 유지
            for cl in content.splitlines():
                if cl.startswith('# ') and not cl.startswith('## '):
                    continue  # 최상위 H1 skip
                elif cl.startswith('## '):
                    lines.append('#### ' + cl[3:])
                elif cl.startswith('### '):
                    lines.append('##### ' + cl[4:])
                else:
                    lines.append(cl)
            lines.append("")

        # 참고 자료 (외부 영상·링크)
        lines += _references_md(ses.get("references", []))

        # 연결 통로 (다른 과정의 관련 지점)
        lines += _cross_refs_md(ses.get("cross_refs", []))

        # 실습 활동 (교재 어투)
        if ses.get("activities"):
            lines.append("### 실습 활동")
            lines.append("")
            lines.append(
                "학습 내용을 바탕으로 아래 실습을 진행합니다. "
                "각 활동은 수업 시간 내에 직접 실행해 보시기 바랍니다."
            )
            lines.append("")
            for i, act in enumerate(ses["activities"], 1):
                lines.append(f"**활동 {i}**: {act}")
            lines.append("")

        if ses.get("notes"):
            lines.append(f"> **강사 노트**: {ses['notes']}")
            lines.append("")

        lines += ["---", ""]

    return "\n".join(lines)


def build_session_doc(curriculum: dict, session: dict) -> str:
    """단일 세션의 교재 내용을 생성한다.

    읽는 책처럼 친절하게 — 개념 소개 → 학습 목표 → 핵심 내용 → 실습 안내 순서.
    """
    week = session["week"]
    title = session["title"]
    total_weeks = len(curriculum.get("sessions", []))

    lines = [
        f"## {week}강: {title}",
        "",
        f"> **수업 시간**: {session.get('duration', '60분')}  ·  "
        f"**전체 {total_weeks}강 중 {week}강**",
        "",
    ]

    # ── 소개 단락 ──────────────────────────────────────────────────
    lines += [
        "### 이번 강 소개",
        "",
        _make_intro(week, title, session),
        "",
    ]

    # ── 학습 목표 (Why 설명 포함) ──────────────────────────────────
    if session.get("objectives"):
        lines += [
            "### 학습 목표",
            "",
            (f"이번 {week}강을 마치고 나면 다음 내용을 스스로 할 수 있게 됩니다. "
             "수업을 시작하기 전에 아래 목표를 한 번 읽어두면, "
             "무엇에 집중해야 할지 방향을 잡는 데 도움이 됩니다."),
            "",
        ]
        for obj in session["objectives"]:
            lines.append(f"- {obj}")
        lines.append("")

    # ── 핵심 학습 내용 (지식 파일 전체, 교재 친화적 형식) ────────────
    seen: set[str] = set()
    for ref_path in session.get("knowledge_refs", []):
        rel = storage.to_relpath(ref_path)
        if rel in seen:
            continue
        content = storage.read_text(rel)
        if content is None:
            continue
        seen.add(rel)

        lines += ["### 핵심 학습 내용", ""]

        for cl in content.splitlines():
            if cl.startswith("# ") and not cl.startswith("## "):
                continue
            elif cl.startswith("## "):
                lines.append("#### " + cl[3:])
            elif cl.startswith("### "):
                lines.append("##### " + cl[4:])
            else:
                lines.append(cl)
        lines.append("")

    # ── 참고 자료 (외부 영상·링크) ─────────────────────────────────
    lines += _references_md(session.get("references", []))

    # ── 연결 통로 (다른 과정의 관련 지점) ──────────────────────────
    lines += _cross_refs_md(session.get("cross_refs", []))

    # ── 핵심 요약 박스 ─────────────────────────────────────────────
    if session.get("objectives"):
        lines += [
            "### 이것만 기억하세요",
            "",
            ("> 수업이 끝난 후, 아래 질문에 스스로 답할 수 있는지 확인해 보세요."),
            "",
        ]
        for obj in session["objectives"]:
            # 목표를 질문 형태로 변환
            q = _objective_to_question(obj)
            lines.append(f"- {q}")
        lines.append("")

    # ── 실습 안내 (단계별 설명 포함) ──────────────────────────────
    if session.get("activities"):
        lines += [
            "### 실습 안내",
            "",
            (f"이론을 배웠다면 이제 직접 해볼 차례입니다. "
             f"총 {len(session['activities'])}개의 실습 활동이 있으며, "
             "순서대로 진행하는 것을 권장합니다. "
             "처음에는 잘 안 되더라도 괜찮습니다 — 반복이 실력을 만듭니다."),
            "",
        ]
        for i, act in enumerate(session["activities"], 1):
            lines += [
                f"**활동 {i} — {act}**",
                "",
                _make_activity_guide(i, act),
                "",
            ]

    if session.get("notes"):
        lines += [f"> **강사 노트**: {session['notes']}", ""]

    return "\n".join(lines)


# ── 교재 문장 생성 헬퍼 ───────────────────────────────────────────

def _make_intro(week: int, title: str, session: dict) -> str:
    """세션 제목과 목표를 바탕으로 소개 단락을 생성한다."""
    obj_preview = ""
    objs = session.get("objectives", [])
    if objs:
        obj_preview = f" 특히 **{objs[0].split('(')[0].strip()}**를 중심으로 배웁니다."

    templates = {
        1: (f"AI 도구를 처음 배울 때 가장 중요한 것은 '어떻게 말을 걸어야 하는가' 입니다. "
            f"이번 {week}강에서는 **{title}**를 다루며,{obj_preview} "
            "마치 사진작가에게 촬영 지시를 내리듯, AI에게 원하는 결과를 "
            "정확히 요청하는 방법을 익히게 됩니다. "
            "처음에는 낯설게 느껴질 수 있지만, "
            "5단계 공식을 한 번 익히고 나면 어떤 이미지도 만들 수 있다는 자신감이 생깁니다."),
        2: (f"이번 {week}강에서는 **{title}**를 배웁니다.{obj_preview} "
            "지난 강에서 이미지를 만드는 법을 배웠다면, "
            "이번에는 나만의 캐릭터를 만들고 다양한 상황에 적용하는 방법을 익힙니다. "
            "광고 소재, SNS 콘텐츠, 교육 자료 등 실제 업무에 바로 쓸 수 있는 기술입니다."),
        3: (f"이번 {week}강에서는 **{title}**를 배웁니다.{obj_preview} "
            "정지 이미지를 만드는 것에서 한 발 나아가, "
            "이제 이미지를 움직이는 영상으로 만드는 전체 흐름을 이해합니다. "
            "스토리보드 9장을 만들고 나면, 30초짜리 미니 광고를 제작할 준비가 됩니다."),
        4: (f"이번 {week}강에서는 **{title}**를 배웁니다.{obj_preview} "
            "Kling AI는 현재 가장 많이 쓰이는 AI 영상 생성 도구 중 하나입니다. "
            "5칸 공식을 외워두면 어떤 씬이든 빠르게 프롬프트를 작성할 수 있습니다. "
            "직접 4가지 씬을 만들어보면서 공식이 자연스럽게 몸에 익도록 합니다."),
        5: (f"드디어 마지막 {week}강, **{title}**입니다.{obj_preview} "
            "지금까지 만든 이미지와 영상 클립들을 하나의 완성된 영상으로 엮는 시간입니다. "
            "CapCut의 타임라인 편집은 처음 보면 복잡해 보이지만, "
            "기본 기능 3가지(트랜지션, 자막, BGM)만 알면 충분합니다. "
            "이번 강이 끝나면 나만의 15~30초 영상을 완성하게 됩니다."),
    }
    return templates.get(
        week,
        (f"이번 {week}강에서는 **{title}**를 다룹니다.{obj_preview} "
         "아래 핵심 내용을 차근차근 읽고, 실습을 통해 직접 익혀보시기 바랍니다."),
    )


def _objective_to_question(objective: str) -> str:
    """학습 목표를 자기 점검 질문 형태로 변환한다."""
    obj = objective.split("(")[0].strip()
    if obj.endswith("이해"):
        return obj.replace("이해", "이해했나요?")
    if obj.endswith("활용"):
        return obj.replace("활용", "직접 활용할 수 있나요?")
    if obj.endswith("생성"):
        return obj.replace("생성", "스스로 만들 수 있나요?")
    if obj.endswith("작성"):
        return obj.replace("작성", "작성할 수 있나요?")
    return obj + " — 혼자서 할 수 있나요?"


def _make_activity_guide(index: int, activity: str) -> str:
    """실습 활동에 친절한 안내 문구를 추가한다."""
    guides = {
        1: ("먼저 배운 내용을 떠올리며 직접 시도해보세요. "
            "정답이 없는 실습입니다 — 내가 원하는 결과를 만드는 것이 목표입니다."),
        2: ("앞 활동의 결과를 바탕으로 진행합니다. "
            "잘 안 되는 부분이 있으면 강사에게 질문하거나 "
            "다시 핵심 내용 섹션을 참고해 보세요."),
        3: ("이번 활동은 지금까지 배운 내용을 통합하는 단계입니다. "
            "시간 안에 완성하지 못해도 괜찮습니다 — "
            "어디서 막혔는지 기록해 두면 이후 복습에 도움이 됩니다."),
    }
    guide = guides.get(index, "직접 실행해보면서 익혀보세요.")
    return f"> {guide}"
