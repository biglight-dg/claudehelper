"""Remove unreferenced files from an unpacked PPTX directory.

Usage: python clean.py <unpacked_dir>
"""

import re
import sys
from pathlib import Path

try:
    import defusedxml.minidom as minidom_parser
except ImportError:
    import xml.dom.minidom as minidom_parser  # fallback


def get_slides_in_sldidlst(unpacked_dir: Path) -> set[str]:
    pres_path = unpacked_dir / "ppt" / "presentation.xml"
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"
    if not pres_path.exists() or not pres_rels_path.exists():
        return set()
    rels_dom = minidom_parser.parse(str(pres_rels_path))
    rid_to_slide = {}
    for rel in rels_dom.getElementsByTagName("Relationship"):
        rid = rel.getAttribute("Id")
        target = rel.getAttribute("Target")
        rel_type = rel.getAttribute("Type")
        if "slide" in rel_type and target.startswith("slides/"):
            rid_to_slide[rid] = target.replace("slides/", "")
    pres_content = pres_path.read_text(encoding="utf-8")
    referenced_rids = set(re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres_content))
    return {rid_to_slide[rid] for rid in referenced_rids if rid in rid_to_slide}


def remove_orphaned_slides(unpacked_dir: Path) -> list[str]:
    slides_dir = unpacked_dir / "ppt" / "slides"
    slides_rels_dir = slides_dir / "_rels"
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"
    if not slides_dir.exists():
        return []
    referenced_slides = get_slides_in_sldidlst(unpacked_dir)
    removed = []
    for slide_file in slides_dir.glob("slide*.xml"):
        if slide_file.name not in referenced_slides:
            rel_path = slide_file.relative_to(unpacked_dir)
            slide_file.unlink()
            removed.append(str(rel_path))
            rels_file = slides_rels_dir / f"{slide_file.name}.rels"
            if rels_file.exists():
                rels_file.unlink()
                removed.append(str(rels_file.relative_to(unpacked_dir)))
    return removed


def get_referenced_files(unpacked_dir: Path) -> set:
    referenced = set()
    for rels_file in unpacked_dir.rglob("*.rels"):
        dom = minidom_parser.parse(str(rels_file))
        for rel in dom.getElementsByTagName("Relationship"):
            target = rel.getAttribute("Target")
            if not target:
                continue
            target_path = (rels_file.parent.parent / target).resolve()
            try:
                referenced.add(target_path.relative_to(unpacked_dir.resolve()))
            except ValueError:
                pass
    return referenced


def remove_orphaned_files(unpacked_dir: Path, referenced: set) -> list[str]:
    resource_dirs = ["media", "embeddings", "charts", "diagrams", "tags", "drawings", "ink"]
    removed = []
    for dir_name in resource_dirs:
        dir_path = unpacked_dir / "ppt" / dir_name
        if not dir_path.exists():
            continue
        for file_path in dir_path.glob("*"):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(unpacked_dir)
            if rel_path not in referenced:
                file_path.unlink()
                removed.append(str(rel_path))
    return removed


def update_content_types(unpacked_dir: Path, removed_files: list[str]) -> None:
    ct_path = unpacked_dir / "[Content_Types].xml"
    if not ct_path.exists():
        return
    dom = minidom_parser.parse(str(ct_path))
    changed = False
    for override in list(dom.getElementsByTagName("Override")):
        part_name = override.getAttribute("PartName").lstrip("/")
        if part_name in removed_files:
            if override.parentNode:
                override.parentNode.removeChild(override)
                changed = True
    if changed:
        with open(ct_path, "wb") as f:
            f.write(dom.toxml(encoding="utf-8"))


def clean_unused_files(unpacked_dir: Path) -> list[str]:
    all_removed = []
    all_removed.extend(remove_orphaned_slides(unpacked_dir))
    trash_dir = unpacked_dir / "[trash]"
    if trash_dir.exists():
        for f in trash_dir.iterdir():
            if f.is_file():
                all_removed.append(str(f.relative_to(unpacked_dir)))
                f.unlink()
        trash_dir.rmdir()
    while True:
        referenced = get_referenced_files(unpacked_dir)
        removed = remove_orphaned_files(unpacked_dir, referenced)
        if not removed:
            break
        all_removed.extend(removed)
    if all_removed:
        update_content_types(unpacked_dir, all_removed)
    return all_removed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clean.py <unpacked_dir>", file=sys.stderr)
        sys.exit(1)
    unpacked_dir = Path(sys.argv[1])
    if not unpacked_dir.exists():
        print(f"Error: {unpacked_dir} not found", file=sys.stderr)
        sys.exit(1)
    removed = clean_unused_files(unpacked_dir)
    if removed:
        print(f"Removed {len(removed)} unreferenced files:")
        for f in removed:
            print(f"  {f}")
    else:
        print("No unreferenced files found")
