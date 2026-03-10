"""
MoFA Effect - AI Image Generator
Uses Pollinations.ai (free, no API key) to generate images.
"""

import os
import time
import urllib.request
import urllib.parse
import urllib.error

from config import POLLINATIONS_BASE_URL, POLLINATIONS_TIMEOUT, IMAGES_DIR


def generate_images(content_plan, logger):
    """
    Generate all images specified in the content plan.
    Returns a list of generated image file paths.
    """
    logger.section("AI Image Generation (Pollinations.ai)")

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

        # Ensure reasonable dimensions
        width = min(max(width, 256), 2048)
        height = min(max(height, 256), 2048)

        # Enhance prompt for better results
        enhanced_prompt = enhance_image_prompt(prompt, purpose, content_plan)

        logger.info(
            f"Generating image {i + 1}/{len(image_prompts)}: "
            f"{purpose} ({width}x{height})"
        )
        logger.info(f"  Prompt: {enhanced_prompt[:100]}...")

        # Generate the image
        output_filename = f"scene_{i + 1:02d}_{purpose}.png"
        output_path = os.path.join(IMAGES_DIR, output_filename)

        success = download_pollinations_image(
            enhanced_prompt, width, height, output_path, logger
        )

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

        # Small delay between requests to be respectful to the API
        if i < len(image_prompts) - 1:
            time.sleep(2)

    logger.info(
        f"Image generation complete. "
        f"{len(generated_images)}/{len(image_prompts)} images generated."
    )
    return generated_images


def enhance_image_prompt(prompt, purpose, content_plan):
    """Enhance the image prompt for better generation results."""
    tone = content_plan.get("tone", "professional")
    brand = content_plan.get("brand_name", "")
    colors = content_plan.get("color_scheme", {})

    enhancements = []

    if purpose == "logo":
        enhancements.append(
            "clean professional logo design, centered, "
            "simple background, vector style, high contrast"
        )
        if brand:
            enhancements.append(f"for brand called {brand}")
    elif purpose == "background":
        enhancements.append(
            "high quality background image, no text, no watermark"
        )
    elif purpose == "product_shot":
        enhancements.append(
            "professional product photography, studio lighting, "
            "clean background"
        )

    if colors.get("primary"):
        enhancements.append(f"color palette includes {colors['primary']}")

    enhancements.append(f"{tone} style")
    enhancements.append("high quality, 4k, detailed")

    enhanced = prompt + ", " + ", ".join(enhancements)
    return enhanced


def download_pollinations_image(prompt, width, height, output_path, logger,
                                  max_retries=3):
    """Download an image from Pollinations.ai."""
    encoded_prompt = urllib.parse.quote(prompt)
    url = (
        f"{POLLINATIONS_BASE_URL}/{encoded_prompt}"
        f"?width={width}&height={height}&nologo=true&seed={int(time.time())}"
    )

    for attempt in range(max_retries):
        try:
            logger.info(
                f"  Requesting image (attempt {attempt + 1}/{max_retries})..."
            )

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "MoFA-Effect-Prototype/1.0"
                }
            )

            with urllib.request.urlopen(req, timeout=POLLINATIONS_TIMEOUT) as response:
                image_data = response.read()

                if len(image_data) < 1000:
                    logger.warning(
                        f"  Response too small ({len(image_data)} bytes). "
                        "Might be an error."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return False

                with open(output_path, "wb") as f:
                    f.write(image_data)

                file_size_kb = len(image_data) / 1024
                logger.info(f"  Downloaded: {file_size_kb:.0f} KB")
                return True

        except urllib.error.URLError as e:
            logger.warning(f"  Network error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.info(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        except Exception as e:
            logger.warning(f"  Error: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)

    return False