"""
MoFA Effect - AI Script Generator
Uses Google Gemini (free API) to generate video content matched to template structure.
"""

import json
import urllib.request
import urllib.error

from config import GEMINI_MODEL, GEMINI_API_BASE


def generate_content_plan(template_summary, user_prompt, api_key, logger):
    """
    Use Gemini to generate a complete content plan for the video.
    The plan includes text replacements, image prompts, and voiceover script.
    """
    logger.section("AI Content Generation (Gemini)")

    # Build the prompt for Gemini
    system_prompt = build_system_prompt(template_summary)
    user_message = build_user_message(template_summary, user_prompt)

    logger.info("Sending request to Gemini API...")
    logger.info(f"Model: {GEMINI_MODEL}")

    # Make the API call
    response_text = call_gemini(system_prompt, user_message, api_key, logger)

    if not response_text:
        logger.error("Failed to get response from Gemini.")
        return None

    # Parse the response
    content_plan = parse_gemini_response(response_text, template_summary, logger)

    if content_plan:
        logger.info("Content plan generated successfully.")
        logger.info(f"Text replacements: {len(content_plan.get('text_replacements', []))}")
        logger.info(f"Image prompts: {len(content_plan.get('image_prompts', []))}")
        logger.info(f"Voiceover: {'Yes' if content_plan.get('voiceover_script') else 'No'}")
    else:
        logger.error("Failed to parse Gemini response into content plan.")

    return content_plan


def build_system_prompt(template_summary):
    """Build the system instruction for Gemini."""
    return (
        "You are MoFA Effect, an AI system that generates content for video templates. "
        "You receive a template structure description and a user creative brief. "
        "You must generate content that precisely fills the template. "
        "Your output must be valid JSON and nothing else. No markdown, no explanation, "
        "no code fences. Just the raw JSON object. "
        "Be creative, professional, and match the tone requested by the user."
    )


def build_user_message(template_summary, user_prompt):
    """Build the user message with template details and creative brief."""

    duration = template_summary.get("duration", 10)
    width = template_summary.get("width", 1920)
    height = template_summary.get("height", 1080)
    text_layers = template_summary.get("replaceable_text_layers", [])
    image_layers = template_summary.get("replaceable_image_layers", [])
    description = template_summary.get("description", "")

    # Determine if voiceover makes sense
    include_voiceover = duration >= 10  # Only for videos 10+ seconds

    text_layers_desc = ""
    if text_layers:
        text_layers_desc = "TEXT LAYERS TO FILL:\n"
        for tl in text_layers:
            current = tl.get("current_text", "placeholder")
            text_layers_desc += (
                f"  - Layer name: \"{tl['name']}\", "
                f"layer index: {tl['index']}, "
                f"current placeholder text: \"{current}\"\n"
            )
    else:
        text_layers_desc = (
            "No specific text layers were detected. "
            "Generate 1-2 text items anyway (a headline and optional subtitle) "
            "in case the parser missed them.\n"
        )

    image_layers_desc = ""
    if image_layers:
        image_layers_desc = "IMAGE LAYERS TO FILL:\n"
        for il in image_layers:
            image_layers_desc += (
                f"  - Layer name: \"{il['name']}\", "
                f"layer index: {il['index']}, "
                f"source: \"{il.get('source_name', 'unknown')}\", "
                f"size: {il.get('width', 'unknown')}x{il.get('height', 'unknown')}\n"
            )
    else:
        image_layers_desc = (
            "No specific image layers were detected. "
            "Generate 1 image prompt for a logo or key visual.\n"
        )

    voiceover_instruction = ""
    if include_voiceover:
        voiceover_instruction = (
            f"VOICEOVER: Generate a voiceover narration script. "
            f"The narration should be timed to approximately {duration:.0f} seconds "
            f"when spoken at a natural pace. "
            f"A rough guide: about 2.5 words per second.\n"
        )
    else:
        voiceover_instruction = (
            f"VOICEOVER: The video is only {duration:.1f} seconds long. "
            f"This is likely a short intro/reveal animation. "
            f"Set voiceover_script to an empty string. "
            f"Do not generate narration for videos under 10 seconds.\n"
        )

    message = f"""TEMPLATE INFORMATION:
- Template description: {description}
- Duration: {duration:.1f} seconds
- Resolution: {width}x{height}
- Total compositions: {len(template_summary.get('compositions', []))}

{text_layers_desc}
{image_layers_desc}
{voiceover_instruction}
USER CREATIVE BRIEF:
{user_prompt}

Generate a JSON object with this exact structure:
{{
  "brand_name": "the brand name from the user brief",
  "tagline": "a short catchy tagline for the brand",
  "tone": "the overall tone (e.g., energetic, professional, elegant)",
  "color_scheme": {{
    "primary": "#hexcolor",
    "secondary": "#hexcolor",
    "accent": "#hexcolor"
  }},
  "text_replacements": [
    {{
      "layer_name": "exact layer name from template",
      "layer_index": layer_index_number,
      "new_text": "the replacement text content"
    }}
  ],
  "image_prompts": [
    {{
      "layer_name": "exact layer name from template or descriptive name",
      "layer_index": layer_index_number_or_0,
      "prompt": "detailed image generation prompt",
      "width": image_width,
      "height": image_height,
      "purpose": "logo or background or product_shot"
    }}
  ],
  "voiceover_script": "the full narration text or empty string if not needed"
}}

Important rules:
1. text_replacements must match the template text layers exactly by name and index.
2. If no text layers exist, still provide reasonable text content with layer_index 0.
3. Image prompts should be detailed and specific for best AI image generation.
4. For logo images, describe a clean professional logo design.
5. Keep all text concise and impactful. This is a video, not an article.
6. Output ONLY the JSON object. No other text."""

    return message


def call_gemini(system_prompt, user_message, api_key, logger):
    """Call the Gemini API and return the response text."""
    url = (
        f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent"
        f"?key={api_key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_message}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "maxOutputTokens": 2048
        }
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            response_body = response.read().decode("utf-8")
            response_json = json.loads(response_body)

            # Extract text from Gemini response
            candidates = response_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    logger.info(f"Gemini response received ({len(text)} characters).")
                    return text

            logger.error("Gemini response had no candidates.")
            logger.error(f"Full response: {response_body[:500]}")
            return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error(f"Gemini API HTTP error {e.code}: {error_body[:500]}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"Gemini API connection error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Gemini API unexpected error: {str(e)}")
        return None


def parse_gemini_response(response_text, template_summary, logger):
    """Parse the Gemini response into a structured content plan."""
    # Clean up the response - remove markdown code fences if present
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try to find JSON object in the response
    # Sometimes Gemini adds explanation text before/after
    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx == -1 or end_idx == -1:
        logger.error("No JSON object found in Gemini response.")
        logger.error(f"Response was: {text[:300]}")
        return None

    json_text = text[start_idx:end_idx + 1]

    try:
        content_plan = json.loads(json_text)
        # Validate required fields
        required_fields = ["text_replacements", "image_prompts"]
        for field in required_fields:
            if field not in content_plan:
                content_plan[field] = []

        if "voiceover_script" not in content_plan:
            content_plan["voiceover_script"] = ""

        return content_plan

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini response: {str(e)}")
        logger.error(f"JSON text was: {json_text[:300]}")

        # Attempt to fix common JSON issues
        try:
            # Try fixing trailing commas
            import re
            fixed = re.sub(r',\s*}', '}', json_text)
            fixed = re.sub(r',\s*]', ']', fixed)
            content_plan = json.loads(fixed)
            logger.info("Fixed JSON parsing issues. Content plan recovered.")
            return content_plan
        except Exception:
            pass

        return None