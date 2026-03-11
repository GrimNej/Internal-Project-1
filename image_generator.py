"""
MoFA Effect - AI Image Generator
Uses multiple free image generation APIs with automatic fallback.
"""

import os
import time
import urllib.request
import urllib.parse
import urllib.error
import json

from config import POLLINATIONS_BASE_URL, POLLINATIONS_TIMEOUT, IMAGES_DIR


def generate_images(content_plan, logger):
    """Generate all images specified in the content plan."""
    logger.section("AI Image Generation (Multi-Provider)")

    image_prompts = content_plan.get("image_prompts", [])

    if not image_prompts:
        logger.info("No images to generate.")
        return []

    os.makedirs(IMAGES_DIR, exist_ok=True)
    generated_images = []

    for i, img_spec in enumerate(image_prompts):
        prompt = img_spec.get("prompt", "")
        width = img_spec.get("width", 1024)
        height = img_spec.get("height", 1024)
        purpose = img_spec.get("purpose", "general")
        layer_name = img_spec.get("layer_name", f"image_{i}")

        if not prompt:
            logger.warning(f"Empty prompt for image {i + 1}. Skipping.")
            continue

        width = min(max(width, 256), 2048)
        height = min(max(height, 256), 2048)

        enhanced_prompt = enhance_image_prompt(prompt, purpose, content_plan)

        logger.info(f"Generating image {i + 1}/{len(image_prompts)}: {purpose} ({width}x{height})")
        logger.info(f"  Prompt: {enhanced_prompt[:100]}...")

        output_filename = f"scene_{i + 1:02d}_{purpose}.png"
        output_path = os.path.join(IMAGES_DIR, output_filename)

        success = False

        # Try Pollinations first
        logger.info("  Trying Pollinations.ai...")
        success = download_pollinations_image(enhanced_prompt, width, height, output_path, logger)

        # Try the WORKING Hugging Face endpoint
        if not success:
            logger.info("  Pollinations failed. Trying Segmind API (free)...")
            success = download_segmind_image(enhanced_prompt, width, height, output_path, logger)

        # Create placeholder as last resort
        if not success:
            logger.warning("  All APIs failed. Creating placeholder...")
            success = create_placeholder_image(enhanced_prompt, width, height, output_path, purpose, logger)

        if success:
            generated_images.append({
                "path": output_path,
                "layer_name": layer_name,
                "layer_index": img_spec.get("layer_index", 0),
                "purpose": purpose,
                "width": width,
                "height": height
            })
            logger.info(f"  Saved: {output_path}")
        else:
            logger.error(f"  Failed to generate image {i + 1}.")

        if i < len(image_prompts) - 1:
            time.sleep(2)

    logger.info(f"Image generation complete. {len(generated_images)}/{len(image_prompts)} images generated.")
    return generated_images


def enhance_image_prompt(prompt, purpose, content_plan):
    """Enhance the image prompt for better results."""
    tone = content_plan.get("tone", "professional")
    colors = content_plan.get("color_scheme", {})

    enhancements = []

    if purpose == "logo":
        enhancements.append("professional logo design, clean, centered, simple background, vector style, high contrast, modern")
    elif purpose == "background":
        enhancements.append("high quality background, professional photography")
    elif purpose == "product_shot":
        enhancements.append("professional product photography, studio lighting")

    if colors.get("primary"):
        enhancements.append(f"color {colors['primary']}")

    enhancements.append(f"{tone} style, high quality, sharp, detailed")

    return prompt + ", " + ", ".join(enhancements)


def download_pollinations_image(prompt, width, height, output_path, logger, max_retries=2):
    """Download from Pollinations.ai."""
    encoded_prompt = urllib.parse.quote(prompt)
    seed = int(time.time())
    url = f"{POLLINATIONS_BASE_URL}/{encoded_prompt}?width={width}&height={height}&nologo=true&seed={seed}"

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MoFA-Effect/1.0"})
            with urllib.request.urlopen(req, timeout=POLLINATIONS_TIMEOUT) as response:
                image_data = response.read()
                if len(image_data) < 1000:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return False

                with open(output_path, "wb") as f:
                    f.write(image_data)
                logger.info(f"    Downloaded: {len(image_data) / 1024:.0f} KB")
                return True
        except Exception as e:
            logger.warning(f"    Pollinations error: {str(e)[:100]}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return False


def download_segmind_image(prompt, width, height, output_path, logger, max_retries=2):
    """
    Download from Segmind's free API (SDXL model).
    Completely free, no API key needed.
    """
    url = "https://api.segmind.com/v1/sdxl1.0-txt2img"
    
    # Segmind supports standard sizes
    supported_sizes = [(512, 512), (768, 768), (1024, 1024), (512, 768), (768, 512)]
    # Find closest supported size
    closest_size = min(supported_sizes, key=lambda s: abs(s[0] - width) + abs(s[1] - height))
    
    payload = {
        "prompt": prompt,
        "negative_prompt": "low quality, blurry, text, watermark, logo, signature",
        "samples": 1,
        "scheduler": "UniPC",
        "num_inference_steps": 20,
        "guidance_scale": 7.5,
        "seed": int(time.time()),
        "img_width": closest_size[0],
        "img_height": closest_size[1],
        "base64": False
    }

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MoFA-Effect/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                image_data = response.read()
                if len(image_data) < 1000:
                    if attempt < max_retries - 1:
                        time.sleep(10)
                        continue
                    return False

                with open(output_path, "wb") as f:
                    f.write(image_data)
                logger.info(f"    Downloaded from Segmind: {len(image_data) / 1024:.0f} KB")
                return True

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            logger.warning(f"    Segmind error {e.code}: {error_body[:200]}")
            if attempt < max_retries - 1:
                time.sleep(10)
        except Exception as e:
            logger.warning(f"    Segmind error: {str(e)[:100]}")
            if attempt < max_retries - 1:
                time.sleep(10)

    return False


def create_placeholder_image(prompt, width, height, output_path, purpose, logger):
    """Create a simple placeholder using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        color_map = {
            "logo": (45, 85, 255),
            "background": (200, 200, 210),
            "product_shot": (255, 255, 255)
        }
        bg_color = color_map.get(purpose, (128, 128, 128))
        
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        border_width = max(5, width // 100)
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(30, 30, 30), width=border_width)
        
        text_lines = [purpose.upper().replace("_", " "), "", "AI Generation Failed", "Placeholder"]
        
        font_size = max(20, height // 20)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        
        y_offset = height // 3
        for line in text_lines:
            if line:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (width - text_width) // 2
                y = y_offset
                
                draw.text((x + 2, y + 2), line, fill=(0, 0, 0), font=font)
                draw.text((x, y), line, fill=(255, 255, 255), font=font)
                
                y_offset += text_height + 10
        
        img.save(output_path, "PNG")
        logger.info(f"    Created placeholder: {output_path}")
        return True
        
    except ImportError:
        logger.error("    Pillow not installed. Install with: pip install pillow")
        return False
    except Exception as e:
        logger.error(f"    Placeholder failed: {str(e)}")
        return False