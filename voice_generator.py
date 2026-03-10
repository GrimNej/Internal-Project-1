"""
MoFA Effect - AI Voice Generator
Uses Edge-TTS (Microsoft Neural TTS, free) to generate voiceover.
"""

import os
import asyncio
import subprocess
import sys

from config import TTS_VOICE, TTS_RATE, AUDIO_DIR


def generate_voiceover(content_plan, logger):
    """
    Generate voiceover audio from the content plan's narration script.
    Returns the path to the generated audio file, or None if not needed.
    """
    logger.section("AI Voice Generation (Edge-TTS)")

    script = content_plan.get("voiceover_script", "").strip()

    if not script:
        logger.info(
            "No voiceover script provided (likely a short template). "
            "Skipping voice generation."
        )
        return None

    os.makedirs(AUDIO_DIR, exist_ok=True)
    output_path = os.path.join(AUDIO_DIR, "voiceover.mp3")

    logger.info(f"Voice: {TTS_VOICE}")
    logger.info(f"Script length: {len(script)} characters, ~{len(script.split())} words")
    logger.info(f"Script preview: {script[:150]}...")

    # Check if edge-tts is available
    try:
        import edge_tts
        success = run_edge_tts_python(script, output_path, logger)
    except ImportError:
        logger.info("edge_tts module not found. Trying command-line edge-tts...")
        success = run_edge_tts_cli(script, output_path, logger)

    if success and os.path.isfile(output_path):
        file_size = os.path.getsize(output_path) / 1024
        logger.info(f"Voiceover generated: {output_path} ({file_size:.0f} KB)")
        return output_path
    else:
        logger.error("Failed to generate voiceover.")
        return None


def run_edge_tts_python(script, output_path, logger):
    """Generate voiceover using edge_tts Python module."""
    try:
        import edge_tts

        async def _generate():
            communicate = edge_tts.Communicate(
                text=script,
                voice=TTS_VOICE,
                rate=TTS_RATE
            )
            await communicate.save(output_path)

        # Run the async function
        # Handle the case where an event loop is already running
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new loop in this case
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, _generate()).result()
            else:
                loop.run_until_complete(_generate())
        except RuntimeError:
            asyncio.run(_generate())

        logger.info("Voice generated via edge_tts Python module.")
        return True

    except Exception as e:
        logger.error(f"edge_tts Python module error: {str(e)}")
        return False


def run_edge_tts_cli(script, output_path, logger):
    """Generate voiceover using edge-tts command line tool."""
    try:
        # Write script to temp file to avoid command line escaping issues
        temp_script_path = os.path.join(AUDIO_DIR, "temp_script.txt")
        with open(temp_script_path, "w", encoding="utf-8") as f:
            f.write(script)

        cmd = [
            sys.executable, "-m", "edge_tts",
            "--voice", TTS_VOICE,
            "--rate", TTS_RATE,
            "--file", temp_script_path,
            "--write-media", output_path
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Clean up temp file
        if os.path.exists(temp_script_path):
            os.remove(temp_script_path)

        if result.returncode == 0:
            logger.info("Voice generated via edge-tts CLI.")
            return True
        else:
            logger.error(f"edge-tts CLI error: {result.stderr[:300]}")
            return False

    except FileNotFoundError:
        logger.error(
            "edge-tts not found. Install it with: pip install edge-tts"
        )
        return False
    except Exception as e:
        logger.error(f"edge-tts CLI error: {str(e)}")
        return False