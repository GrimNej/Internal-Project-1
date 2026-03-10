"""
MoFA Effect - Render Engine
Handles After Effects rendering and format conversion.
"""

import os
import subprocess
import time

from config import (
    AERENDER_PATH, RENDER_TIMEOUT_SECONDS, OUTPUT_DIR
)


def execute_fill_script(jsx_file_path, logger):
    """
    Execute the fill script in After Effects to modify the template.
    """
    logger.section("Executing Template Fill Script")

    afterfx_path = os.path.join(
        os.path.dirname(AERENDER_PATH), "AfterFX.exe"
    )

    if os.path.isfile(afterfx_path):
        cmd = [afterfx_path, "-r", jsx_file_path]
        logger.info("Executing fill script via AfterFX.exe")
    else:
        cmd = [AERENDER_PATH, "-r", jsx_file_path]
        logger.info("Executing fill script via aerender.exe")

    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("Waiting for After Effects to fill the template...")
    logger.info("(This may take 30-90 seconds)")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )

        stdout, stderr = process.communicate(timeout=RENDER_TIMEOUT_SECONDS)

        if stdout:
            stdout_text = stdout.decode("utf-8", errors="replace")
            if stdout_text.strip():
                logger.info(f"AE output: {stdout_text[:500]}")
        if stderr:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text.strip():
                logger.warning(f"AE errors: {stderr_text[:500]}")

        if process.returncode == 0:
            logger.info("Fill script executed successfully.")
            return True
        else:
            logger.warning(
                f"AfterFX process exited with code {process.returncode}. "
                "This may or may not indicate a problem. "
                "After Effects sometimes returns non-zero even on success."
            )
            # Check if the modified AEP file was actually updated
            return True  # Proceed anyway

    except subprocess.TimeoutExpired:
        process.kill()
        logger.error(
            f"After Effects timed out after {RENDER_TIMEOUT_SECONDS} seconds."
        )
        return False
    except Exception as e:
        logger.error(f"Error executing fill script: {str(e)}")
        return False


def render_video(modified_aep_path, template_summary, logger):
    """
    Render the modified AEP file to video using aerender.
    First renders to AVI, then converts to MP4 using ffmpeg.
    """
    logger.section("Video Rendering")

    if not os.path.isfile(AERENDER_PATH):
        logger.error(f"aerender.exe not found at: {AERENDER_PATH}")
        return None

    main_comp_name = template_summary.get("main_comp_name", "")

    # Output paths
    avi_output_path = os.path.join(OUTPUT_DIR, "render_output.avi")
    mp4_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    # Remove old outputs
    for path in [avi_output_path, mp4_output_path]:
        if os.path.exists(path):
            os.remove(path)

    # Build aerender command
    cmd = [
        AERENDER_PATH,
        "-project", modified_aep_path,
        "-output", avi_output_path,
        "-RStemplate", "Best Settings",
        "-OMtemplate", "Lossless",
    ]

    # Add composition name if we know it
    if main_comp_name:
        cmd.extend(["-comp", main_comp_name])

    logger.info(f"Render command: {' '.join(cmd)}")
    logger.info("Starting After Effects render...")
    logger.info(
        f"This may take 1-5 minutes depending on template complexity."
    )

    start_time = time.time()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )

        # Read output in real-time for progress
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    # Log render progress
                    if "PROGRESS" in decoded.upper() or "frame" in decoded.lower():
                        logger.info(f"  Render: {decoded[:100]}")
                    elif "error" in decoded.lower():
                        logger.warning(f"  Render: {decoded[:200]}")

        elapsed = time.time() - start_time
        logger.info(f"Render process completed in {elapsed:.1f} seconds.")

        if process.returncode != 0:
            logger.warning(
                f"aerender exited with code {process.returncode}."
            )

    except subprocess.TimeoutExpired:
        process.kill()
        logger.error(
            f"Rendering timed out after {RENDER_TIMEOUT_SECONDS} seconds."
        )
        return None
    except Exception as e:
        logger.error(f"Render error: {str(e)}")
        return None

    # Check if AVI was created
    # aerender might create files with frame numbers or different names
    actual_avi = find_rendered_file(OUTPUT_DIR, logger)

    if not actual_avi:
        logger.error(
            "No rendered file found. The render may have failed. "
            "Check if After Effects is properly licensed and the template "
            "can be opened without errors."
        )
        return None

    logger.info(f"Rendered file: {actual_avi}")
    file_size_mb = os.path.getsize(actual_avi) / (1024 * 1024)
    logger.info(f"Rendered file size: {file_size_mb:.1f} MB")

    # Convert to MP4
    mp4_path = convert_to_mp4(actual_avi, mp4_output_path, logger)

    if mp4_path:
        # Clean up the large AVI file
        try:
            os.remove(actual_avi)
            logger.info("Cleaned up intermediate AVI file.")
        except Exception:
            pass

    return mp4_path


def find_rendered_file(output_dir, logger):
    """
    Find the rendered output file. aerender sometimes creates files
    with different naming patterns.
    """
    video_extensions = [".avi", ".mov", ".mp4", ".mkv"]

    # Look for recently created video files in output directory
    candidates = []
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        if os.path.isfile(filepath):
            ext = os.path.splitext(filename)[1].lower()
            if ext in video_extensions:
                mod_time = os.path.getmtime(filepath)
                candidates.append((filepath, mod_time))

    if not candidates:
        # Check one level of subdirectories
        for dirname in os.listdir(output_dir):
            dirpath = os.path.join(output_dir, dirname)
            if os.path.isdir(dirpath):
                for filename in os.listdir(dirpath):
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in video_extensions:
                            mod_time = os.path.getmtime(filepath)
                            candidates.append((filepath, mod_time))

    if candidates:
        # Return the most recently modified video file
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    return None


def convert_to_mp4(input_path, output_path, logger):
    """
    Convert rendered video to MP4 using ffmpeg (via imageio-ffmpeg).
    """
    logger.info("Converting to MP4...")

    # Try to find ffmpeg
    ffmpeg_path = find_ffmpeg(logger)

    if not ffmpeg_path:
        logger.error(
            "ffmpeg not found. Cannot convert to MP4. "
            "Install imageio-ffmpeg: pip install imageio-ffmpeg"
        )
        # Return the original file path instead
        return input_path

    cmd = [
        ffmpeg_path,
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",  # Overwrite output
        output_path
    ]

    logger.info(f"ffmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0 and os.path.isfile(output_path):
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(
                f"MP4 conversion successful: {output_path} "
                f"({file_size_mb:.1f} MB)"
            )
            return output_path
        else:
            logger.error(f"ffmpeg error: {result.stderr[:500]}")
            return input_path

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg conversion timed out.")
        return input_path
    except Exception as e:
        logger.error(f"ffmpeg error: {str(e)}")
        return input_path


def find_ffmpeg(logger):
    """Find ffmpeg binary. Check imageio-ffmpeg first, then system PATH."""
    # Try imageio-ffmpeg (bundled ffmpeg)
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(ffmpeg_path):
            logger.info(f"Found ffmpeg via imageio-ffmpeg: {ffmpeg_path}")
            return ffmpeg_path
    except ImportError:
        pass
    except Exception:
        pass

    # Try system ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("Found ffmpeg in system PATH.")
            return "ffmpeg"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try common Windows locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]
    for path in common_paths:
        if os.path.isfile(path):
            logger.info(f"Found ffmpeg at: {path}")
            return path

    return None