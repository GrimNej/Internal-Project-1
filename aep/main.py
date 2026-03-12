"""
MoFA Effect - Main Entry Point
AI-Powered Video Generation Using After Effects Templates

Usage: python main.py
"""

import os
import sys
import shutil
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    ensure_directories, OUTPUT_DIR, AERENDER_PATH, LOGS_DIR
)
from comp.utils import Logger, save_json, ask_user, validate_file_exists
from aep_parser import parse_aep_binary
from aep_introspect import run_introspection, build_template_summary
from ai_script_generator import generate_content_plan
from image_generator import generate_images
from voice_generator import generate_voiceover
from template_filler import generate_fill_script
from render_engine import execute_fill_script, render_video


def print_banner():
    """Print the MoFA Effect startup banner."""
    banner = """
    ================================================================
         MoFA Effect - AI-Powered Video Generation
         Using After Effects Templates
         Prototype v0.2
    ================================================================
    """
    print(banner)


def check_dependencies(logger):
    """Check that all required dependencies are available."""
    logger.section("Dependency Check")
    all_good = True

    if os.path.isfile(AERENDER_PATH):
        logger.info(f"aerender.exe: Found")
    else:
        logger.error(f"aerender.exe: NOT FOUND at {AERENDER_PATH}")
        all_good = False

    packages = {
        "requests": "pip install requests",
        "edge_tts": "pip install edge-tts",
        "imageio_ffmpeg": "pip install imageio-ffmpeg",
    }

    for module, install_cmd in packages.items():
        try:
            __import__(module)
            logger.info(f"{module}: Installed")
        except ImportError:
            logger.error(f"{module}: NOT INSTALLED -- {install_cmd}")
            all_good = False

    # Check Pillow separately
    try:
        from PIL import Image
        logger.info("Pillow: Installed")
    except ImportError:
        logger.warning("Pillow: NOT INSTALLED -- pip install pillow (needed for placeholder images)")

    return all_good


def get_user_inputs(logger):
    """Collect all required inputs from the user."""
    logger.section("User Input Collection")

    print()
    print("Enter the full path to your After Effects template (.aep file).")
    print()

    while True:
        aep_path = ask_user("AEP template path")
        aep_path = aep_path.strip('"').strip("'")

        if validate_file_exists(aep_path, "AEP template"):
            ext = os.path.splitext(aep_path)[1].lower()
            if ext in [".aep", ".aepx"]:
                logger.info(f"Template file accepted: {aep_path}")
                break
            else:
                print(f"Warning: File extension is '{ext}', expected '.aep'.")
                confirm = ask_user("Continue anyway? (yes/no)", "yes")
                if confirm.lower() in ["yes", "y"]:
                    break
        else:
            print("File not found. Please check the path and try again.")

    print()
    print("Enter your Groq API key.")
    print("Get one free at: https://console.groq.com/keys")
    print()

    api_key = ask_user("Groq API key")
    while not api_key or len(api_key) < 20:
        print("API key seems too short. Please enter a valid key.")
        api_key = ask_user("Groq API key")
    logger.info("Groq API key received.")

    print()
    print("Describe the template you provided.")
    print("Example: Splash logo reveal with colorful ink splashes, 10 seconds")
    print()

    template_description = ask_user(
        "Template description",
        "Logo reveal animation template"
    )
    logger.info(f"Template description: {template_description}")

    print()
    print("Now describe the video you want to create.")
    print("Be specific about brand name, style, colors, and target audience.")
    print()

    creative_prompt = ask_user("Your creative brief")
    while not creative_prompt or len(creative_prompt) < 10:
        print("Please provide a more detailed description.")
        creative_prompt = ask_user("Your creative brief")
    logger.info(f"Creative brief: {creative_prompt}")

    return {
        "aep_path": aep_path,
        "api_key": api_key,
        "template_description": template_description,
        "creative_prompt": creative_prompt
    }


def cleanup_previous_run(logger):
    """Delete all files and subfolders in the output directory."""
    logger.section("Cleaning Up Previous Run")
    if not os.path.exists(OUTPUT_DIR):
        logger.info("Output directory does not exist. Nothing to clean.")
        return

    try:
        for item in os.listdir(OUTPUT_DIR):
            item_path = os.path.join(OUTPUT_DIR, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    logger.info(f"  Removed file: {item}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.info(f"  Removed folder: {item}")
            except Exception as e:
                logger.warning(f"  Failed to remove {item}: {e}")
        logger.info("Cleanup complete.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def run_pipeline(inputs, logger):
    """Execute the full MoFA Effect pipeline."""
    pipeline_start = time.time()

    # Clean up previous run to prevent AE caching issues
    cleanup_previous_run(logger)
    ensure_directories()

    aep_path = inputs["aep_path"]
    api_key = inputs["api_key"]
    template_description = inputs["template_description"]
    creative_prompt = inputs["creative_prompt"]

    # ===================================================================
    # PHASE 1: Template Analysis
    # ===================================================================
    logger.section("PHASE 1: Template Analysis")

    binary_info = parse_aep_binary(aep_path, logger)
    save_json(binary_info, os.path.join(OUTPUT_DIR, "binary_analysis.json"))

    logger.info("")
    logger.info("Attempting deep introspection via After Effects...")
    logger.info("After Effects will open briefly in the background.")
    logger.info("If a dialog box appears, please close it manually.")
    print()
    proceed = ask_user(
        "Ready to run After Effects introspection? (yes/skip)",
        "yes"
    )

    analysis = None
    if proceed.lower() in ["yes", "y"]:
        analysis = run_introspection(aep_path, logger)
        if analysis:
            save_json(
                analysis,
                os.path.join(OUTPUT_DIR, "template_analysis.json")
            )
    else:
        logger.info("Skipping ExtendScript introspection.")

    template_summary = build_template_summary(
        analysis, binary_info, template_description, logger
    )
    save_json(
        template_summary,
        os.path.join(OUTPUT_DIR, "template_summary.json")
    )

    if not analysis:
        logger.warning(
            "Deep introspection was not available. "
            "Using binary parser results and user input."
        )
        print()
        print("Since deep analysis was not available, please provide:")

        duration_str = ask_user("Template duration in seconds", "10")
        try:
            template_summary["duration"] = float(duration_str)
        except ValueError:
            template_summary["duration"] = 10.0

        resolution = ask_user("Template resolution (e.g., 1920x1080)", "1920x1080")
        try:
            w, h = resolution.lower().split("x")
            template_summary["width"] = int(w)
            template_summary["height"] = int(h)
        except Exception:
            template_summary["width"] = 1920
            template_summary["height"] = 1080

        template_summary["frame_rate"] = 30

        print()
        print("Do you know the names of any text layers in the template?")
        print("Enter comma-separated names, or press Enter to skip.")
        text_layers_input = ask_user("Text layer names", "")
        if text_layers_input:
            for name in text_layers_input.split(","):
                name = name.strip()
                if name:
                    template_summary["replaceable_text_layers"].append({
                        "name": name, "index": 0,
                        "current_text": "", "font": "", "font_size": 0
                    })

        print()
        print("Do you know the names of any image/logo layers?")
        print("Enter comma-separated names, or press Enter to skip.")
        image_layers_input = ask_user("Image layer names", "")
        if image_layers_input:
            for name in image_layers_input.split(","):
                name = name.strip()
                if name:
                    template_summary["replaceable_image_layers"].append({
                        "name": name, "index": 0,
                        "source_name": "", "source_file": "",
                        "width": template_summary["width"],
                        "height": template_summary["height"],
                        "is_missing": False
                    })

        save_json(
            template_summary,
            os.path.join(OUTPUT_DIR, "template_summary.json")
        )

    print()
    print("=" * 50)
    print("  TEMPLATE ANALYSIS RESULTS")
    print("=" * 50)
    print(f"  Duration:   {template_summary.get('duration', 'Unknown')}s")
    print(f"  Resolution: {template_summary.get('width', '?')}x{template_summary.get('height', '?')}")
    print(f"  Frame Rate: {template_summary.get('frame_rate', '?')} fps")
    print(f"  Text Layers:  {len(template_summary.get('replaceable_text_layers', []))}")
    print(f"  Image Layers: {len(template_summary.get('replaceable_image_layers', []))}")
    print(f"  Other Layers: {len(template_summary.get('artistic_layers', []))}")
    print("=" * 50)
    print()

    # ===================================================================
    # PHASE 2: AI Content Generation
    # ===================================================================
    logger.section("PHASE 2: AI Content Generation")

    content_plan = generate_content_plan(
        template_summary, creative_prompt, api_key, logger
    )

    if not content_plan:
        logger.error("Failed to generate content plan. Aborting pipeline.")
        return False

    save_json(content_plan, os.path.join(OUTPUT_DIR, "content_plan.json"))

    print()
    print("=" * 50)
    print("  AI-GENERATED CONTENT PLAN")
    print("=" * 50)
    print(f"  Brand: {content_plan.get('brand_name', 'N/A')}")
    print(f"  Tagline: {content_plan.get('tagline', 'N/A')}")
    print(f"  Tone: {content_plan.get('tone', 'N/A')}")
    print(f"  Text Replacements: {len(content_plan.get('text_replacements', []))}")
    for tr in content_plan.get("text_replacements", []):
        print(f"    [{tr.get('layer_name', '?')}] -> \"{tr.get('new_text', '')}\"")
    print(f"  Images to Generate: {len(content_plan.get('image_prompts', []))}")
    for ip in content_plan.get("image_prompts", []):
        print(f"    [{ip.get('purpose', '?')}] {ip.get('prompt', '')[:60]}...")
    voiceover = content_plan.get("voiceover_script", "")
    if voiceover:
        print(f"  Voiceover: {voiceover[:80]}...")
    else:
        print("  Voiceover: None (template too short)")
    print("=" * 50)
    print()

    proceed = ask_user("Proceed with asset generation? (yes/no)", "yes")
    if proceed.lower() not in ["yes", "y"]:
        logger.info("User chose not to proceed. Pipeline stopped.")
        return False

    # ===================================================================
    # PHASE 3: Asset Generation
    # ===================================================================
    logger.section("PHASE 3: Asset Generation")

    generated_images = generate_images(content_plan, logger)
    voiceover_path = generate_voiceover(content_plan, logger)

    # ===================================================================
    # PHASE 4: Template Filling
    # ===================================================================
    logger.section("PHASE 4: Template Filling")

    jsx_file_path, modified_aep_path = generate_fill_script(
        aep_path, content_plan, generated_images,
        voiceover_path, template_summary, logger
    )

    print()
    logger.info("Ready to execute fill script in After Effects.")
    logger.info("After Effects will open, modify the template, and save.")
    print()
    proceed = ask_user(
        "Execute fill script in After Effects? (yes/no)", "yes"
    )

    if proceed.lower() not in ["yes", "y"]:
        logger.info("Skipping AE fill execution.")
        logger.info(f"You can manually run the script in AE: {jsx_file_path}")
    else:
        fill_success = execute_fill_script(jsx_file_path, logger)
        if not fill_success:
            logger.warning(
                "Fill script execution may have had issues. "
                "Continuing to render step anyway."
            )
        time.sleep(5)

    # Check the debug log from the fill script
    debug_log_path = os.path.join(OUTPUT_DIR, "jsx_debug.log")
    if os.path.isfile(debug_log_path):
        logger.info("--- ExtendScript Debug Log ---")
        try:
            with open(debug_log_path, "r", encoding="utf-8") as f:
                debug_content = f.read()
            for line in debug_content.strip().split("\n"):
                logger.info(f"  JSX: {line}")
        except Exception:
            pass
        logger.info("--- End Debug Log ---")

    # ===================================================================
    # PHASE 5: Rendering
    # ===================================================================
    logger.section("PHASE 5: Rendering")

    print()
    proceed = ask_user(
        "Render the final video? (yes/no)", "yes"
    )

    if proceed.lower() not in ["yes", "y"]:
        logger.info("Skipping render.")
        logger.info(f"You can render manually from: {modified_aep_path}")
        return True

    final_video = render_video(modified_aep_path, template_summary, logger)

    # ===================================================================
    # PHASE 6: Results
    # ===================================================================
    pipeline_elapsed = time.time() - pipeline_start

    logger.section("PIPELINE COMPLETE")

    print()
    print("=" * 60)
    print("  MoFA Effect - Pipeline Complete")
    print("=" * 60)
    print(f"  Total time: {pipeline_elapsed:.1f} seconds")
    print()
    print("  Generated files:")
    print(f"    Template analysis:  {os.path.join(OUTPUT_DIR, 'template_summary.json')}")
    print(f"    Content plan:       {os.path.join(OUTPUT_DIR, 'content_plan.json')}")

    if generated_images:
        for img in generated_images:
            print(f"    Image: {os.path.basename(img['path'])}")

    if voiceover_path:
        print(f"    Voiceover: {voiceover_path}")

    print(f"    Fill script: {jsx_file_path}")
    print(f"    Modified AEP: {modified_aep_path}")
    print(f"    Debug log: {debug_log_path}")

    if final_video and os.path.isfile(final_video):
        file_size_mb = os.path.getsize(final_video) / (1024 * 1024)
        print()
        print(f"    >>> FINAL VIDEO: {final_video}")
        print(f"    >>> File size:   {file_size_mb:.2f} MB")
    else:
        print()
        print("    Video render was skipped or failed.")
        print(f"    You can render manually from: {modified_aep_path}")

    print()
    print("=" * 60)

    report = {
        "pipeline_duration_seconds": round(pipeline_elapsed, 1),
        "template_file": aep_path,
        "creative_prompt": creative_prompt,
        "template_description": template_description,
        "images_generated": len(generated_images),
        "voiceover_generated": voiceover_path is not None,
        "modified_aep_file": modified_aep_path,
        "final_video": final_video,
        "status": "complete" if final_video else "partial"
    }
    save_json(report, os.path.join(OUTPUT_DIR, "generation_report.json"))

    return True


def main():
    """Main entry point for MoFA Effect."""
    print_banner()

    ensure_directories()
    logger = Logger(LOGS_DIR)

    logger.section("MoFA Effect Starting")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Output directory: {OUTPUT_DIR}")

    deps_ok = check_dependencies(logger)
    if not deps_ok:
        print()
        print("Some dependencies are missing. Please install them:")
        print("  pip install requests edge-tts imageio-ffmpeg pillow")
        print()
        proceed = ask_user(
            "Continue anyway? Some features may not work. (yes/no)",
            "no"
        )
        if proceed.lower() not in ["yes", "y"]:
            logger.info("Exiting due to missing dependencies.")
            return

    try:
        inputs = get_user_inputs(logger)
    except KeyboardInterrupt:
        print()
        logger.info("User cancelled input. Exiting.")
        return

    try:
        success = run_pipeline(inputs, logger)
        if success:
            logger.info("MoFA Effect pipeline finished successfully.")
        else:
            logger.warning("MoFA Effect pipeline finished with issues.")
    except KeyboardInterrupt:
        print()
        logger.info("User cancelled pipeline execution.")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        print()
        print(f"An unexpected error occurred: {str(e)}")
        print(f"Check the log file for details: {logger.log_file}")


if __name__ == "__main__":
    main()
    