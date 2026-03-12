"""
MoFA Effect v2 - Main Entry Point
DaVinci Resolve / Fusion Edition

Interactive element-by-element template editing with
automatic AI-powered voiceover generation.
"""

import os
import sys
import shutil
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ensure_directories, OUTPUT_DIR, LOGS_DIR
from utils import Logger, save_json, ask_user
from comp_parser import parse_comp_file
from font_manager import check_fonts, apply_font_fallbacks
from comp_modifier import apply_changes
from voice_generator import generate_voiceover
from render_engine import render_preview


def print_banner():
    print("""
    ================================================================
         MoFA Effect v2 - AI-Powered Video Generation
         DaVinci Resolve / Fusion Edition
         Prototype v0.2
    ================================================================
    """)


def check_dependencies(logger):
    logger.section("Dependency Check")
    ok = True
    for mod, cmd in [("PIL", "pillow"), ("imageio_ffmpeg", "imageio-ffmpeg"),
                     ("requests", "requests")]:
        try:
            if mod == "PIL":
                from PIL import Image
            else:
                __import__(mod)
            logger.info(f"{mod}: OK")
        except ImportError:
            logger.error(f"{mod}: MISSING -- pip install {cmd}")
            ok = False

    try:
        import edge_tts
        logger.info("edge_tts: OK")
    except ImportError:
        logger.warning("edge_tts: MISSING (voiceover will be unavailable)")
        logger.warning("  Install with: pip install edge-tts")

    return ok


def get_user_inputs(logger):
    """Get the .comp file path and Groq API key."""
    logger.section("User Input Collection")

    print("\nEnter the full path to your Fusion .comp template file.")
    while True:
        comp_path = ask_user("Comp file path").strip('"').strip("'")
        if os.path.isfile(comp_path):
            logger.info(f"File accepted: {comp_path}")
            break
        print("File not found. Check the path and try again.")

    print("\nEnter your Groq API key (needed for voiceover generation).")
    print("Get one free at: https://console.groq.com/keys")
    print("Press Enter to skip (voiceover will be disabled).\n")

    api_key = input("Groq API key (Enter to skip): ").strip()
    if api_key and len(api_key) >= 20:
        logger.info("Groq API key received.")
    else:
        api_key = None
        logger.info("No API key provided. Voiceover will be disabled.")

    return comp_path, api_key


def display_elements(elements, font_report):
    """Display all changeable element slots to the user."""
    print("\n" + "=" * 65)
    print("  CHANGEABLE ELEMENTS DETECTED")
    print("=" * 65)

    font_status = {}
    for fi in font_report.get("fonts", []):
        font_status[fi["name"]] = fi

    text_count = 0
    image_count = 0
    color_count = 0

    for elem in elements:
        idx = elem["index"]
        etype = elem["type"].upper()
        name = elem["tool_name"]

        if elem["type"] == "text":
            text_count += 1
            current = elem["current_value"]
            font = elem.get("font", "")
            style = elem.get("font_style", "")
            fi = font_status.get(font, {})
            font_ok = fi.get("available", True)
            fallback = fi.get("fallback", None)

            print(f"\n  {idx}. [{etype}] Tool: \"{name}\"")
            print(f"     Content:  \"{current}\"")
            font_label = font if font else "(default)"
            if style:
                font_label += f" {style}"
            if not font_ok and fallback:
                font_label += f"  [MISSING -> will use \"{fallback}\"]"
            print(f"     Font:     {font_label}")

        elif elem["type"] == "image":
            image_count += 1
            current = elem["current_value"]
            subtype = elem.get("media_subtype", "image")
            print(f"\n  {idx}. [{subtype.upper()} SLOT] Tool: \"{name}\"")
            print(f"     Current:  \"{current}\"")
            print(f"     (Provide a new image/video file path to replace)")

        elif elem["type"] == "color":
            color_count += 1
            current = elem["current_value"]
            print(f"\n  {idx}. [{etype}] Tool: \"{name}\"")
            print(f"     Color:    {current}")

    print(f"\n  Summary: {text_count} text, {image_count} image/video, {color_count} color")
    print("=" * 65)


def interactive_edit(elements):
    """Walk through each element one by one and ask for new content."""
    total = len(elements)
    changed = 0

    print(f"\nWalking through {total} element(s).")
    print("Press Enter on any element to keep its current content.\n")

    for elem in elements:
        idx = elem["index"]
        etype = elem["type"].upper()
        name = elem["tool_name"]
        current = elem["current_value"]

        print(f"--- Element {idx} of {total} ---")

        if elem["type"] == "text":
            font = elem.get("font", "")
            if font:
                print(f"[{etype}] Tool: \"{name}\" | Font: {font}")
            else:
                print(f"[{etype}] Tool: \"{name}\"")
            print(f"Current content: \"{current}\"")
            new_val = input("Your content (Enter to keep): ").strip()
            if new_val:
                elem["new_value"] = new_val
                changed += 1
                print(f"  -> Changed to: \"{new_val}\"")
            else:
                print("  -> Kept current")

        elif elem["type"] == "image":
            subtype = elem.get("media_subtype", "image")
            print(f"[{subtype.upper()} SLOT] Tool: \"{name}\"")
            print(f"Current file: \"{current}\"")
            new_val = input("New file path (Enter to keep): ").strip().strip('"').strip("'")
            if new_val:
                if os.path.isfile(new_val):
                    elem["new_value"] = os.path.abspath(new_val)
                    changed += 1
                    print(f"  -> Changed to: \"{os.path.basename(new_val)}\"")
                else:
                    print(f"  -> File not found: \"{new_val}\". Keeping current.")
            else:
                print("  -> Kept current")

        elif elem["type"] == "color":
            print(f"[{etype}] Tool: \"{name}\"")
            print(f"Current color: {current}")
            new_val = input("New hex color, e.g. #1a2b3c (Enter to keep): ").strip()
            if new_val:
                if not new_val.startswith("#"):
                    new_val = "#" + new_val
                if len(new_val) == 7:
                    try:
                        int(new_val[1:], 16)
                        elem["new_value"] = new_val
                        changed += 1
                        print(f"  -> Changed to: {new_val}")
                    except ValueError:
                        print("  -> Invalid hex. Keeping current.")
                else:
                    print("  -> Invalid format (need 6 hex digits). Keeping current.")
            else:
                print("  -> Kept current")

        print()

    return changed


def cleanup_output(logger):
    if not os.path.exists(OUTPUT_DIR):
        return
    for item in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, item)
        try:
            if os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception:
            pass
    logger.info("Previous output cleaned.")


def run_pipeline(comp_path, api_key, logger):
    start_time = time.time()

    cleanup_output(logger)
    ensure_directories()

    # ==================================================================
    # PHASE 1: Parse template
    # ==================================================================
    logger.section("PHASE 1: Template Analysis")
    template_data = parse_comp_file(comp_path, logger)

    if not template_data["valid"]:
        logger.error("Invalid .comp file. Cannot proceed.")
        return False

    save_json(
        {k: v for k, v in template_data.items() if k != "raw_content"},
        os.path.join(OUTPUT_DIR, "template_analysis.json")
    )

    print("\n" + "=" * 50)
    print("  TEMPLATE SUMMARY")
    print("=" * 50)
    print(f"  Duration:    {template_data['duration_seconds']}s ({template_data['duration_frames']} frames)")
    print(f"  Resolution:  {template_data['width']}x{template_data['height']}")
    print(f"  FPS:         {template_data['fps']}")
    print(f"  Elements:    {len(template_data['changeable_elements'])}")
    print("=" * 50)

    elements = template_data["changeable_elements"]

    if not elements:
        logger.warning("No changeable elements found.")
        print("\nNo changeable elements detected in this template.")
        return True

    # ==================================================================
    # PHASE 2: Font check
    # ==================================================================
    logger.section("PHASE 2: Font Check")
    font_report = check_fonts(template_data, logger)
    font_fallback_map = apply_font_fallbacks(template_data, font_report, logger)
    save_json(font_report, os.path.join(OUTPUT_DIR, "font_report.json"))

    # ==================================================================
    # PHASE 3: Display elements and edit
    # ==================================================================
    logger.section("PHASE 3: Interactive Editing")
    display_elements(elements, font_report)

    choice = ask_user("\nDo you want to make changes? (yes/no)", "yes")
    if choice.lower() in ["yes", "y"]:
        num_changed = interactive_edit(elements)
        print(f"Total elements changed: {num_changed}")
    else:
        print("No changes requested.")

    # ==================================================================
    # PHASE 4: Apply changes to .comp
    # ==================================================================
    has_changes = any(e.get("new_value") is not None for e in elements)
    has_font_fallbacks = bool(font_fallback_map)

    if has_changes or has_font_fallbacks:
        logger.section("PHASE 4: Applying Changes")
        modified_path = apply_changes(
            comp_path, template_data, font_fallback_map, logger
        )
    else:
        logger.info("No modifications to apply.")
        modified_path = comp_path

    # ==================================================================
    # PHASE 5: Voiceover (automatic, optional)
    # ==================================================================
    logger.section("PHASE 5: Voiceover")
    voiceover_path = None

    if api_key:
        print("\nThe AI can automatically generate a voiceover narration")
        print(f"that matches your video content ({template_data['duration_seconds']}s duration).")
        vo_choice = ask_user("Generate voiceover? (yes/no)", "no")

        if vo_choice.lower() in ["yes", "y"]:
            voiceover_path = generate_voiceover(template_data, api_key, logger)
            if voiceover_path:
                print(f"\nVoiceover created: {os.path.basename(voiceover_path)}")
            else:
                print("\nVoiceover generation failed. Continuing without it.")
    else:
        logger.info("No API key. Voiceover generation skipped.")
        print("\n(Voiceover unavailable - no Groq API key provided)")

    # ==================================================================
    # PHASE 6: Preview render
    # ==================================================================
    logger.section("PHASE 6: Preview Rendering")

    print("\nGenerate a preview video?")
    print("(The modified .comp file can also be opened in DaVinci Resolve)")
    gen_preview = ask_user("Generate preview? (yes/no)", "yes")

    final_video = None
    if gen_preview.lower() in ["yes", "y"]:
        final_video = render_preview(template_data, voiceover_path, logger)

    # ==================================================================
    # RESULTS
    # ==================================================================
    elapsed = time.time() - start_time
    logger.section("PIPELINE COMPLETE")

    print("\n" + "=" * 60)
    print("  MoFA Effect v2 - Complete")
    print("=" * 60)
    print(f"  Time: {elapsed:.1f} seconds\n")
    print("  Output files:")

    if modified_path != comp_path:
        print(f"    Modified .comp:  {os.path.basename(modified_path)}")
        print(f"      Full path:     {modified_path}")
        print(f"      (Open in DaVinci Resolve for full-quality render)")
    else:
        print(f"    No changes applied to .comp file")

    if voiceover_path:
        print(f"    Voiceover:       {os.path.basename(voiceover_path)}")

    if final_video:
        size_mb = os.path.getsize(final_video) / (1024 * 1024)
        print(f"\n    >>> PREVIEW VIDEO: {final_video}")
        print(f"    >>> Size: {size_mb:.2f} MB")

    if not font_report.get("all_available", True):
        print("\n  Font substitutions:")
        for fi in font_report["fonts"]:
            if not fi["available"]:
                print(f"    \"{fi['name']}\" -> \"{fi['fallback']}\"")

    print("\n" + "=" * 60)

    save_json({
        "duration": round(elapsed, 1),
        "template": comp_path,
        "modified_comp": modified_path,
        "preview_video": final_video,
        "voiceover": voiceover_path,
        "elements_total": len(elements),
        "elements_changed": sum(1 for e in elements if e.get("new_value")),
        "fonts_substituted": len(font_fallback_map),
    }, os.path.join(OUTPUT_DIR, "generation_report.json"))

    return True


def main():
    print_banner()
    ensure_directories()
    logger = Logger(LOGS_DIR)

    logger.section("MoFA Effect v2 Starting")
    logger.info(f"Python: {sys.version}")

    if not check_dependencies(logger):
        print("\nInstall missing dependencies:")
        print("  pip install requests pillow imageio-ffmpeg edge-tts")
        return

    try:
        comp_path, api_key = get_user_inputs(logger)
        run_pipeline(comp_path, api_key, logger)
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"\nError: {e}")
        print(f"Log: {logger.log_file}")


if __name__ == "__main__":
    main()