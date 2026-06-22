# -*- coding: utf-8 -*-
"""커리큘럼 슬라이드 재생성: build_slides_data → save_slides.
화면 슬라이드(세로 4:5)만 사용하므로 PPTX는 생성하지 않는다.
인자로 커리큘럼 id를 받는다."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from tools.curriculum_tools import (
    load_curriculum_db, load_curriculum, save_slides, save_curriculum,
)
from agents.curriculum import build_slides_data


def regen(curriculum_id: str):
    db = load_curriculum_db()
    entry = next(c for c in db["curricula"] if c["id"] == curriculum_id)
    cur = load_curriculum(entry["path"])

    slides = build_slides_data(cur)
    slides_path = save_slides(cur, slides)  # generated.slides_path + last_generated 갱신
    save_curriculum(cur)
    print("SLIDES_JSON:", slides_path)
    print("SLIDE_COUNT:", len(slides))
    print("LAST_GENERATED:", cur["generated"]["last_generated"])


if __name__ == "__main__":
    regen(sys.argv[1])
