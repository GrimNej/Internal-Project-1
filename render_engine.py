"""
MoFA Effect - Render Engine
Handles After Effects rendering and format conversion.
"""

import os
import subprocess
import time
import sys

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

        logger.info("Fill script executed successfully.")
        return True

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

    # We need to render the MAIN comp, not "Your Logo Here"
    # "Main Comp" is the actual animation, "Your Logo Here" is just the logo placeholder
    main_comp_name = "Main Comp"  # This is the actual composition with the animation

    # Output paths
    avi_output_path = os.path.join(OUTPUT_DIR, "render_output.avi")
    mp4_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    # Remove old outputs
    for path in [avi_output_path, mp4_output_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # Build aerender command
    cmd = [
        AERENDER_PATH,
        "-project", modified_aep_path,
        "-output", avi_output_path,
        "-RStemplate", "Best Settings",
        "-OMtemplate", "Lossless",
        "-comp", main_comp_name
    ]

    logger.info(f"Render command: {' '.join(cmd)}")
    logger.info(f"Rendering composition: {main_comp_name}")
    logger.info("Starting After Effects render...")
    logger.info("Progress:")

    start_time = time.time()
    last_frame = 0
    total_frames = 600  # 10 seconds at 60fps

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )

        # Read output line by line
        for line in process.stdout:
            line = line.strip()
            
            # Parse frame progress
            if "PROGRESS:" in line and "0:00:" in line:
                # Extract frame number from lines like "0:00:05:30 (330): 0 Seconds"
                try:
                    parts = line.split("(")
                    if len(parts) > 1:
                        frame_str = parts[1].split(")")[0]
                        current_frame = int(frame_str)
                        
                        # Only update every 10 frames to reduce spam
                        if current_frame - last_frame >= 10 or current_frame == total_frames:
                            last_frame = current_frame
                            percent = (current_frame / total_frames) * 100
                            bar_length = 40
                            filled = int(bar_length * current_frame / total_frames)
                            bar = "=" * filled + "-" * (bar_length - filled)
                            
                            # Print progress bar on same line
                            sys.stdout.write(f"\r  [{bar}] {percent:.1f}% (Frame {current_frame}/{total_frames})")
                            sys.stdout.flush()
                except Exception:
                    pass
            
            # Log important messages
            elif "Starting composition" in line:
                logger.info(f"  {line}")
            elif "Finished composition" in line:
                print()  # New line after progress bar
                logger.info(f"  {line}")
            elif "error" in line.lower() and "handle_con" not in line.lower():
                logger.warning(f"  {line}")

        process.wait()
        print()  # Final newline after progress
        
        elapsed = time.time() - start_time
        logger.info(f"Render process completed in {elapsed:.1f} seconds.")

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
    actual_avi = find_rendered_file(OUTPUT_DIR, logger)

    if not actual_avi:
        logger.error(
            "No rendered file found. The render may have failed."
        )
        return None

    logger.info(f"Rendered file: {actual_avi}")
    file_size_mb = os.path.getsize(actual_avi) / (1024 * 1024)
    logger.info(f"Rendered file size: {file_size_mb:.1f} MB")

    # Convert to MP4 with proper parameters
    mp4_path = convert_to_mp4_properly(actual_avi, mp4_output_path, logger)

    if mp4_path and os.path.getsize(mp4_path) > 100000:  # At least 100KB
        # Clean up the large AVI file
        try:
            os.remove(actual_avi)
            logger.info("Cleaned up intermediate AVI file.")
        except Exception:
            pass
        return mp4_path
    else:
        logger.error("MP4 conversion produced invalid file. Keeping AVI.")
        return actual_avi


def find_rendered_file(output_dir, logger):
    """Find the rendered output file."""
    video_extensions = [".avi", ".mov", ".mp4"]
    
    candidates = []
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        if os.path.isfile(filepath):
            ext = os.path.splitext(filename)[1].lower()
            if ext in video_extensions and os.path.getsize(filepath) > 1000000:  # At least 1MB
                mod_time = os.path.getmtime(filepath)
                candidates.append((filepath, mod_time))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    return None


def convert_to_mp4_properly(input_path, output_path, logger):
    """
    Convert AVI to MP4 properly. The issue was that we were trying to encode
    audio when there was no audio stream.
    """
    logger.info("Converting to MP4...")

    ffmpeg_path = find_ffmpeg(logger)
    if not ffmpeg_path:
        logger.error("ffmpeg not found. Cannot convert to MP4.")
        return input_path

    # First, check if the input has audio
    probe_cmd = [
        ffmpeg_path,
        "-i", input_path,
        "-hide_banner"
    ]

    has_audio = False
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        output_text = result.stderr  # ffmpeg writes to stderr
        has_audio = "Audio:" in output_text
        logger.info(f"Input file has audio: {has_audio}")
    except Exception:
        pass

    # Build conversion command based on whether audio exists
    if has_audio:
        cmd = [
            ffmpeg_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
    else:
        # Video only - no audio encoding
        cmd = [
            ffmpeg_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]

    logger.info("Running ffmpeg conversion...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0 and os.path.isfile(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 100000:  # At least 100KB
                file_size_mb = file_size / (1024 * 1024)
                logger.info(
                    f"MP4 conversion successful: {output_path} ({file_size_mb:.1f} MB)"
                )
                return output_path
            else:
                logger.error(f"MP4 file is suspiciously small: {file_size} bytes")
                logger.error(f"ffmpeg stderr: {result.stderr[-1000:]}")
                return None
        else:
            logger.error(f"ffmpeg failed with return code {result.returncode}")
            logger.error(f"ffmpeg stderr: {result.stderr[-1000:]}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg conversion timed out.")
        return None
    except Exception as e:
        logger.error(f"ffmpeg error: {str(e)}")
        return None


def find_ffmpeg(logger):
    """Find ffmpeg binary."""
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
    except Exception:
        pass

    return None
