"""
MoFA Effect v2 - Preview Renderer
Creates a preview MP4 from the template structure and user content.
Uses Pillow for frame generation and ffmpeg for video assembly.
"""

import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from config import OUTPUT_DIR, FRAMES_DIR, DEFAULT_FPS


def render_preview(template_data, voiceover_path, logger):
    """
    Build a preview video showing all changed content.
    Returns path to the output MP4 or None on failure.
    """
    logger.section("Preview Video Rendering")

    os.makedirs(FRAMES_DIR, exist_ok=True)

    width = template_data.get("width", 1920)
    height = template_data.get("height", 1080)
    fps = template_data.get("fps", DEFAULT_FPS)
    duration = template_data.get("duration_seconds", 5)
    elements = template_data.get("changeable_elements", [])

    # Build scenes from elements that have content
    scenes = []
    for elem in elements:
        display_val = elem.get("new_value") or elem.get("current_value", "")
        if not display_val or display_val in ["(empty)", "(Resolve timeline media)"]:
            continue

        if elem["type"] == "text":
            scenes.append({"type": "text", "content": display_val, "label": elem["tool_name"]})
        elif elem["type"] == "image" and os.path.isfile(display_val):
            scenes.append({"type": "image", "content": display_val, "label": elem["tool_name"]})
        elif elem["type"] == "color":
            scenes.append({"type": "color", "content": display_val, "label": elem["tool_name"]})

    if not scenes:
        scenes.append({"type": "text", "content": "MoFA Effect Preview", "label": "Default"})

    scene_duration = max(2.0, duration / len(scenes))

    logger.info(f"Scenes: {len(scenes)}, each ~{scene_duration:.1f}s")
    logger.info(f"Resolution: {width}x{height}, FPS: {fps}")

    # Generate frames
    frame_paths = []
    for i, scene in enumerate(scenes):
        frame_path = os.path.join(FRAMES_DIR, f"scene_{i + 1:03d}.png")
        create_frame(frame_path, width, height, scene)
        frame_paths.append({"path": frame_path, "duration": scene_duration})
        logger.info(f"  Scene {i + 1}: [{scene['type']}] {scene['content'][:50]}")

    # Build ffmpeg concat file
    concat_path = os.path.join(OUTPUT_DIR, "concat.txt")
    with open(concat_path, "w", encoding="utf-8") as f:
        for frame in frame_paths:
            safe = frame["path"].replace("\\", "/")
            f.write(f"file '{safe}'\n")
            f.write(f"duration {frame['duration']:.2f}\n")
        if frame_paths:
            safe = frame_paths[-1]["path"].replace("\\", "/")
            f.write(f"file '{safe}'\n")

    ffmpeg_path = find_ffmpeg(logger)
    if not ffmpeg_path:
        logger.error("ffmpeg not found. Install: pip install imageio-ffmpeg")
        return None

    video_path = os.path.join(OUTPUT_DIR, "preview_video.mp4")
    final_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    # Create video from frames
    cmd = [
        ffmpeg_path,
        "-f", "concat", "-safe", "0",
        "-i", concat_path,
        "-vf", f"fps={fps},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-y", video_path
    ]

    logger.info("Assembling video frames...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr[-500:]}")
            return None
    except Exception as e:
        logger.error(f"ffmpeg failed: {e}")
        return None

    # Add audio if available
    if voiceover_path and os.path.isfile(voiceover_path):
        logger.info("Adding voiceover...")
        cmd_audio = [
            ffmpeg_path,
            "-i", video_path, "-i", voiceover_path,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-y", final_path
        ]
        try:
            result = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                try:
                    os.remove(video_path)
                except Exception:
                    pass
            else:
                logger.warning("Audio merge failed. Using video without audio.")
                os.rename(video_path, final_path)
        except Exception:
            os.rename(video_path, final_path)
    else:
        os.rename(video_path, final_path)

    if os.path.isfile(final_path) and os.path.getsize(final_path) > 5000:
        size_mb = os.path.getsize(final_path) / (1024 * 1024)
        logger.info(f"Preview video: {final_path} ({size_mb:.2f} MB)")
        return final_path

    logger.error("Preview video creation failed.")
    return None


def create_frame(path, width, height, scene):
    """Create a single scene frame."""
    bg = (15, 22, 40)
    accent = (60, 130, 246)
    white = (240, 240, 245)
    gray = (100, 100, 110)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Top/bottom accent bars
    draw.rectangle([(0, 0), (width, 4)], fill=accent)
    draw.rectangle([(0, height - 4), (width, height)], fill=accent)

    # Subtle grid
    grid_color = (20, 28, 50)
    step = max(width, height) // 20
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    title_font = load_font(max(28, height // 10))
    sub_font = load_font(max(18, height // 18))
    small_font = load_font(max(12, height // 28))

    # Label at top
    label = f"[{scene['label']}]"
    centered_text(draw, label, small_font, gray, width, height // 8)

    if scene["type"] == "text":
        centered_text(draw, scene["content"], title_font, white, width, height // 2 - height // 10)

    elif scene["type"] == "image":
        try:
            pimg = Image.open(scene["content"])
            max_w, max_h = width // 2, height // 2
            pimg.thumbnail((max_w, max_h), Image.LANCZOS)
            px = (width - pimg.width) // 2
            py = (height - pimg.height) // 2 - height // 10
            img.paste(pimg, (px, py))
        except Exception:
            centered_text(draw, "(image)", title_font, gray, width, height // 2)

    elif scene["type"] == "color":
        hex_c = scene["content"].lstrip("#")
        try:
            cr = int(hex_c[0:2], 16)
            cg = int(hex_c[2:4], 16)
            cb = int(hex_c[4:6], 16)
            box_size = min(width, height) // 4
            bx = (width - box_size) // 2
            by = (height - box_size) // 2 - height // 10
            draw.rectangle([(bx, by), (bx + box_size, by + box_size)], fill=(cr, cg, cb))
            draw.rectangle([(bx, by), (bx + box_size, by + box_size)], outline=white, width=2)
            centered_text(draw, scene["content"], sub_font, white, width, by + box_size + 20)
        except Exception:
            centered_text(draw, scene["content"], title_font, white, width, height // 2)

    # Footer
    centered_text(draw, "MoFA Effect Preview", small_font, (50, 50, 60), width, height - height // 8)

    img.save(path, "PNG")


def centered_text(draw, text, font, color, canvas_width, y):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (canvas_width - tw) // 2

    # Wrap if too wide
    if tw > canvas_width * 0.85:
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            test_bbox = draw.textbbox((0, 0), test, font=font)
            if test_bbox[2] - test_bbox[0] > canvas_width * 0.8:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        line_height = bbox[3] - bbox[1] + 8
        start_y = y - (len(lines) * line_height) // 2
        for i, line in enumerate(lines):
            lb = draw.textbbox((0, 0), line, font=font)
            lw = lb[2] - lb[0]
            lx = (canvas_width - lw) // 2
            ly = start_y + i * line_height
            draw.text((lx + 2, ly + 2), line, fill=(0, 0, 0), font=font)
            draw.text((lx, ly), line, fill=color, font=font)
    else:
        draw.text((x + 2, y + 2), text, fill=(0, 0, 0), font=font)
        draw.text((x, y), text, fill=color, font=font)


def load_font(size):
    for p in ["C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\arial.ttf",
              "C:\\Windows\\Fonts\\calibri.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def find_ffmpeg(logger):
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(p):
            return p
    except Exception:
        pass
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        return "ffmpeg"
    except Exception:
        pass
    return None