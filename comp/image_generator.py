"""
MoFA Effect v2 - Image Generator
Creates placeholder images using Pillow.
No external AI image APIs used (per boss instructions).
"""

import os
from PIL import Image, ImageDraw, ImageFont

from config import IMAGES_DIR


def generate_images(content_plan, logger):
    logger.section("Placeholder Image Generation")

    image_prompts = content_plan.get("image_prompts", [])
    if not image_prompts:
        logger.info("No images to generate.")
        return []

    os.makedirs(IMAGES_DIR, exist_ok=True)
    generated = []

    colors = content_plan.get("color_scheme", {})
    primary = hex_to_rgb(colors.get("primary", "#2d55ff"))
    secondary = hex_to_rgb(colors.get("secondary", "#1a1a2e"))
    accent = hex_to_rgb(colors.get("accent", "#ffffff"))

    for i, spec in enumerate(image_prompts):
        width = min(max(spec.get("width", 1024), 256), 4096)
        height = min(max(spec.get("height", 1024), 256), 4096)
        purpose = spec.get("purpose", "general")
        tool_name = spec.get("tool_name", f"image_{i}")
        prompt = spec.get("prompt", "placeholder")

        filename = f"placeholder_{i + 1:02d}_{purpose}.png"
        output_path = os.path.join(IMAGES_DIR, filename)

        logger.info(f"Creating placeholder {i + 1}: {purpose} ({width}x{height})")

        create_placeholder(
            output_path, width, height, purpose,
            content_plan.get("brand_name", "Brand"),
            content_plan.get("tagline", ""),
            primary, secondary, accent
        )

        generated.append({
            "path": output_path,
            "tool_name": tool_name,
            "purpose": purpose,
            "width": width,
            "height": height
        })
        logger.info(f"  Saved: {output_path}")

    logger.info(f"Generated {len(generated)} placeholder images.")
    return generated


def create_placeholder(path, width, height, purpose, brand, tagline,
                        primary, secondary, accent):
    img = Image.new("RGB", (width, height), secondary)
    draw = ImageDraw.Draw(img)

    # Draw border
    border = max(4, min(width, height) // 100)
    draw.rectangle([(border, border), (width - border - 1, height - border - 1)],
                   outline=primary, width=border)

    # Draw inner accent line
    inner = border * 3
    draw.rectangle([(inner, inner), (width - inner - 1, height - inner - 1)],
                   outline=tuple(c // 2 for c in primary), width=2)

    # Load font
    title_size = max(24, height // 10)
    sub_size = max(16, height // 18)
    small_size = max(12, height // 25)

    title_font = load_font(title_size)
    sub_font = load_font(sub_size)
    small_font = load_font(small_size)

    # Draw purpose label at top
    label = f"[{purpose.upper()}]"
    draw_centered_text(draw, label, small_font, accent, width, height // 6)

    # Draw brand name
    draw_centered_text(draw, brand, title_font, primary, width, height // 2 - title_size)

    # Draw tagline
    if tagline:
        draw_centered_text(draw, tagline, sub_font, accent, width, height // 2 + sub_size)

    # Draw "PLACEHOLDER" note
    note = "Placeholder - AI image model pending"
    draw_centered_text(draw, note, small_font, (128, 128, 128), width, height - height // 6)

    img.save(path, "PNG")


def draw_centered_text(draw, text, font, color, canvas_width, y):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (canvas_width - text_width) // 2
    draw.text((x + 2, y + 2), text, fill=(0, 0, 0), font=font)
    draw.text((x, y), text, fill=color, font=font)


def load_font(size):
    paths = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (45, 85, 255)
    try:
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (45, 85, 255)