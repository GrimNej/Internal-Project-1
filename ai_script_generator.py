"""
MoFA Effect - AI Script Generator
Uses Groq API (Llama model, free) to generate video content matched to template structure.
"""

import json

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
    import ssl

from config import GROQ_MODEL, GROQ_API_BASE


def generate_content_plan(template_summary, user_prompt, api_key, logger):
    """
    Use Groq (Llama) to generate a complete content plan for the video.
    The plan includes text replacements, image prompts, and voiceover script.
    """
    logger.section("AI Content Generation (Groq - Llama)")

    system_prompt = build_system_prompt(template_summary)
    user_message = build_user_message(template_summary, user_prompt)

    logger.info("Sending request to Groq API...")
    logger.info(f"Model: {GROQ_MODEL}")

    if HAS_REQUESTS:
        logger.info("Using requests library for HTTP calls.")
        response_text = call_groq_requests(system_prompt, user_message, api_key, logger)
    else:
        logger.warning("requests library not found. Using urllib (less reliable).")
        logger.warning("Install requests with: pip install requests")
        response_text = call_groq_urllib(system_prompt, user_message, api_key, logger)

    if not response_text:
        logger.error("Failed to get response from Groq.")
        return None

    content_plan = parse_llm_response(response_text, template_summary, logger)

    if content_plan:
        logger.info("Content plan generated successfully.")
        logger.info(f"Text replacements: {len(content_plan.get('text_replacements', []))}")
        logger.info(f"Image prompts: {len(content_plan.get('image_prompts', []))}")
        logger.info(f"Voiceover: {'Yes' if content_plan.get('voiceover_script') else 'No'}")
    else:
        logger.error("Failed to parse Groq response into content plan.")

    return content_plan


def build_system_prompt(template_summary):
    """Build the system instruction for Groq."""
    return (
        "You are MoFA Effect, an AI system that generates content for video templates. "
        "You receive a template structure description and a user creative brief. "
        "You must generate content that precisely fills the template. "
        "Your output must be valid JSON and nothing else. No markdown, no explanation, "
        "no code fences, no extra text. Just the raw JSON object. "
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

    include_voiceover = duration >= 10

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
            "Generate 1-2 text items anyway (a headline and optional tagline) "
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
            f"About 2.5 words per second.\n"
        )
    else:
        voiceover_instruction = (
            f"VOICEOVER: The video is only {duration:.1f} seconds long. "
            f"This is likely a short intro/reveal animation. "
            f"Set voiceover_script to an empty string.\n"
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

Generate a JSON object with this EXACT structure:
{{
  "brand_name": "the brand name from the user brief",
  "tagline": "a short catchy tagline for the brand",
  "tone": "the overall tone (energetic, professional, elegant, etc)",
  "color_scheme": {{
    "primary": "#hexcolor",
    "secondary": "#hexcolor",
    "accent": "#hexcolor"
  }},
  "text_replacements": [
    {{
      "layer_name": "exact layer name from template or generic name like Brand Name",
      "layer_index": 0,
      "new_text": "the replacement text content"
    }}
  ],
  "image_prompts": [
    {{
      "layer_name": "exact layer name from template or descriptive name like Logo",
      "layer_index": 0,
      "prompt": "detailed image generation prompt describing the visual",
      "width": {width},
      "height": {height},
      "purpose": "logo or background or product_shot"
    }}
  ],
  "voiceover_script": "the full narration text or empty string if not needed"
}}

IMPORTANT RULES:
1. For a 7-second logo reveal template, generate at least 1 text layer (brand name) and 1 image (logo).
2. Text should be short and impactful for video.
3. Image prompts must be detailed and specific for AI image generation.
4. For logos, describe a clean professional logo design that matches the brand.
5. Output ONLY the JSON object. No markdown. No code fences. No explanations before or after."""

    return message


def call_groq_requests(system_prompt, user_message, api_key, logger):
    """Call Groq API using requests library (more reliable)."""
    url = f"{GROQ_API_BASE}/chat/completions"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 1,
        "stream": False
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "MoFA-Effect/1.0"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            response_json = response.json()
            choices = response_json.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    logger.info(f"Groq response received ({len(content)} characters).")
                    return content

            logger.error("Groq response had no choices.")
            logger.error(f"Full response: {response.text[:500]}")
            return None
        else:
            logger.error(f"Groq API HTTP error {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            logger.error(f"Headers: {dict(response.headers)}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Groq API request error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Groq API unexpected error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def call_groq_urllib(system_prompt, user_message, api_key, logger):
    """Fallback: Call Groq API using urllib."""
    url = f"{GROQ_API_BASE}/chat/completions"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 1,
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "MoFA-Effect/1.0"
        },
        method="POST"
    )

    try:
        context = ssl.create_default_context()
        
        with urllib.request.urlopen(req, timeout=60, context=context) as response:
            response_body = response.read().decode("utf-8")
            response_json = json.loads(response_body)

            choices = response_json.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    logger.info(f"Groq response received ({len(content)} characters).")
                    return content

            logger.error("Groq response had no choices.")
            return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error(f"Groq API HTTP error {e.code}: {error_body[:500]}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"Groq API connection error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Groq API error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def parse_llm_response(response_text, template_summary, logger):
    """Parse the LLM response into a structured content plan."""
    text = response_text.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()

    # Find JSON object boundaries
    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx == -1 or end_idx == -1:
        logger.error("No JSON object found in Groq response.")
        logger.error(f"Response preview: {text[:500]}")
        return None

    json_text = text[start_idx:end_idx + 1]

    try:
        content_plan = json.loads(json_text)
        
        # Validate and ensure required fields exist
        required_fields = ["text_replacements", "image_prompts"]
        for field in required_fields:
            if field not in content_plan:
                content_plan[field] = []

        if "voiceover_script" not in content_plan:
            content_plan["voiceover_script"] = ""

        # For logo templates, ensure we have at least one image
        if not content_plan["image_prompts"]:
            brand_name = content_plan.get("brand_name", "Brand")
            logger.info("No image prompts found. Generating default logo prompt.")
            content_plan["image_prompts"] = [{
                "layer_name": "Logo",
                "layer_index": 0,
                "prompt": f"professional modern logo design for {brand_name}, clean vector style, centered, simple background, high contrast",
                "width": template_summary.get("width", 1920),
                "height": template_summary.get("height", 1080),
                "purpose": "logo"
            }]

        # Ensure we have at least one text replacement
        if not content_plan["text_replacements"]:
            brand_name = content_plan.get("brand_name", "Brand")
            logger.info("No text replacements found. Generating default brand name text.")
            content_plan["text_replacements"] = [{
                "layer_name": "Brand Name",
                "layer_index": 0,
                "new_text": brand_name
            }]

        return content_plan

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Groq response: {str(e)}")
        logger.error(f"JSON text preview: {json_text[:500]}")

        # Attempt to fix common JSON issues
        try:
            import re
            # Remove trailing commas before closing braces/brackets
            fixed = re.sub(r',\s*}', '}', json_text)
            fixed = re.sub(r',\s*]', ']', fixed)
            content_plan = json.loads(fixed)
            logger.info("Fixed JSON parsing issues. Content plan recovered.")
            return content_plan
        except Exception:
            logger.error("Could not recover from JSON parsing error.")
            pass

        return None