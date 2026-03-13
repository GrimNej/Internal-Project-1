"""
MoFA Effect v2 - Main Entry Point
DaVinci Resolve Free Edition (Workspace > Scripts approach)

Pipeline:
  1. Parse .comp       - detect text / image / color slots
  2. User edits        - type new text, supply your image path
  3. Patch .comp       - write modified copy to output/
  4. Install fonts     - download from Google Fonts, register in Windows
  5. Hand off to Resolve:
       - Writes a handoff JSON with comp path + output path
       - Copies mofa_render.py into Resolve's Scripts/Comp/ folder
       - Opens Resolve
       - Tells you to click Workspace > Scripts > MoFA_Render
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from config import ensure_directories, OUTPUT_DIR, LOGS_DIR
from utils import Logger, save_json, ask_user
from comp_parser import parse_comp_file
from comp_modifier import apply_changes
from spline_evaluator import parse_all_splines
from font_picker import pick_font
from resolve_renderer import install_render_script


BANNER = """
================================================================
     MoFA Effect v2 - DaVinci Resolve Free Edition
     Parse -> Edit -> Patch -> Font Install -> Render
================================================================
"""


def get_comp_path(logger):
    logger.section("Select Template")
    print("\nDrag your .comp file here, or type its full path:")
    while True:
        path = ask_user("Comp file path").strip().strip('"').strip("'")
        if os.path.isfile(path):
            logger.info(f"Template: {path}")
            return path
        print("  File not found. Try again.")


def display_elements(elements):
    print("\n" + "=" * 65)
    print("  DETECTED ELEMENTS")
    print("=" * 65)
    for e in elements:
        idx  = e["index"]
        name = e["tool_name"]
        if e["type"] == "text":
            vals = e.get("current_values", [e.get("current_value", "")])
            print(f"\n  {idx}. [TEXT]  \"{name}\"")
            print(f"     Current values : {vals}")
            print(f"     Input format   : WORD1 / WORD2 / WORD3")
        elif e["type"] == "image":
            print(f"\n  {idx}. [IMAGE] \"{name}\"")
            print(f"     Current file   : {e['current_value']}")
        elif e["type"] == "color":
            print(f"\n  {idx}. [COLOR] \"{name}\"")
            print(f"     Current color  : {e['current_value']}")
            print(f"     Input format   : #rrggbb")
    print("\n" + "=" * 65)


def interactive_edit(elements):
    n = len(elements)
    changed = 0
    print(f"\nEditing {n} element(s). Press Enter to keep current.\n")
    for e in elements:
        idx  = e["index"]
        name = e["tool_name"]
        print(f"-- {idx}/{n} --")

        if e["type"] == "text":
            vals = e.get("current_values", [])
            print(f"[TEXT] \"{name}\"")
            print(f"  Current: {vals}")
            raw = input("  New (e.g. WELCOME / TO / MOFA, or Enter to keep): ").strip()
            if raw:
                e["new_value"] = raw
                changed += 1
                print(f"  -> {[v.strip() for v in raw.split('/')]}")
            else:
                print("  -> kept")

        elif e["type"] == "image":
            print(f"[IMAGE] \"{name}\"")
            print(f"  Current: {e['current_value']}")
            raw = input("  Your image path (Enter to skip): ").strip().strip('"').strip("'")
            if raw:
                if os.path.isfile(raw):
                    e["new_value"] = os.path.abspath(raw)
                    changed += 1
                    print(f"  -> {os.path.basename(raw)}")
                else:
                    print(f"  -> File not found: {raw}. Skipping.")
            else:
                print("  -> skipped")

        elif e["type"] == "color":
            print(f"[COLOR] \"{name}\"")
            print(f"  Current: {e['current_value']}")
            raw = input("  New hex color (Enter to keep): ").strip()
            if raw:
                if not raw.startswith("#"):
                    raw = "#" + raw
                if len(raw) == 7:
                    try:
                        int(raw[1:], 16)
                        e["new_value"] = raw
                        changed += 1
                        print(f"  -> {raw}")
                    except ValueError:
                        print("  -> Invalid hex. Keeping.")
                else:
                    print("  -> Bad format. Keeping.")
            else:
                print("  -> kept")
        print()
    return changed


def run(comp_path, logger):
    t0 = time.time()
    ensure_directories()

    # ── Phase 1: Parse ─────────────────────────────────────────────────────────
    logger.section("PHASE 1: Parse .comp")
    data = parse_comp_file(comp_path, logger)
    if not data["valid"]:
        logger.error("Not a valid .comp file.")
        return False

    print(f"\n  Duration  : {data['duration_seconds']}s  ({data['duration_frames']} frames @ {data['fps']} fps)")
    print(f"  Resolution: {data['width']}x{data['height']}")
    print(f"  Elements  : {len(data['changeable_elements'])}")

    elements = data["changeable_elements"]
    if not elements:
        logger.warning("No changeable elements detected.")
        return True

    # ── Phase 2: Parse splines (for font detection) ────────────────────────────
    logger.section("PHASE 2: Parse Splines")
    splines = parse_all_splines(data["raw_content"])
    logger.info(f"Splines found: {len(splines)}")

    # ── Phase 3: User edits ────────────────────────────────────────────────────
    logger.section("PHASE 3: Interactive Editing")
    display_elements(elements)
    do_edit = ask_user("Make changes? (yes/no)", "yes")
    n_changed = 0
    if do_edit.lower() in ("yes", "y"):
        n_changed = interactive_edit(elements)
        print(f"  {n_changed} element(s) changed.")
    else:
        print("  No changes. Will render original values.")

    # ── Phase 4: Font selection ────────────────────────────────────────────────
    logger.section("PHASE 4: Font Selection")

    # Show which fonts the .comp originally used
    font_splines = [n for n in splines if n.endswith("Font")]
    original_fonts = set()
    for fsn in font_splines:
        sp = splines[fsn]
        for _, v in getattr(sp, "keyframes", []):
            if v:
                original_fonts.add(v)
    if original_fonts:
        print(f"\n  This .comp uses: {', '.join(sorted(original_fonts))}")
        print("  These fonts likely aren't installed — pick a replacement.\n")

    replacement_font = pick_font("Choose the font to use for all text in this video")
    logger.info(f"Replacement font: {replacement_font}")

    # ── Phase 5: Patch the .comp ───────────────────────────────────────────────
    logger.section("PHASE 5: Patch .comp")
    data["replacement_font"] = replacement_font
    modified_comp = apply_changes(comp_path, data, font_fallback_map={}, logger=logger)
    logger.info(f"Modified .comp: {modified_comp}")

    # ── Phase 6: Hand off to Resolve ───────────────────────────────────────────
    logger.section("PHASE 6: Hand Off to Resolve")

    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.splitext(os.path.basename(comp_path))[0]
    output_mp4 = os.path.join(OUTPUT_DIR, f"{basename}_mofa_{ts}.mp4")

    install_render_script(modified_comp, output_mp4, PROJECT_ROOT, logger, comp_data=data)

    elapsed = time.time() - t0
    print(f"\n  Setup complete in {elapsed:.1f}s.")
    print("  Waiting for you to click the script in Resolve...")

    save_json({
        "comp":             comp_path,
        "modified_comp":    modified_comp,
        "expected_output":  output_mp4,
        "elements_total":   len(elements),
        "elements_changed": n_changed,
        "setup_elapsed_s":  round(elapsed, 1),
    }, os.path.join(OUTPUT_DIR, "render_report.json"))

    return True


def main():
    print(BANNER)
    ensure_directories()
    logger = Logger(LOGS_DIR)
    logger.info(f"Python {sys.version}")
    logger.info(f"Project root: {PROJECT_ROOT}")

    try:
        comp_path = get_comp_path(logger)
        run(comp_path, logger)
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as exc:
        import traceback
        logger.error(f"Unhandled error: {exc}")
        logger.error(traceback.format_exc())
        print(f"\nError: {exc}")


if __name__ == "__main__":
    main()