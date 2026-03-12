"""
MoFA Effect v2 - AI Script Generator
Uses Groq API (Llama) to generate content matched to Fusion template structure.
"""

import json
import requests

from config import GROQ_MODEL, GROQ_API_BASE


def generate_content_plan(template_data, user_prompt, api_key, logger):
    logger.section("AI Content Generation (Groq - Llama)")

    system_prompt = (
        "You are MoFA Effect, an AI system that generates content for video templates. "
        "You receive a Fusion composition template structure and a user creative brief. "
        "Generate content that fills the template. "
        "Output ONLY valid JSON. No markdown, no code fences, no explanation."
    )

    user_message = build_user_message(template_data, user_prompt)

    logger.info(f"Sending request to Groq API (model: {GROQ_MODEL})...")

    url = f"{GROQ_API_BASE}/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 2048
    }

    try:
        response = requests.post(
            url, json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=60
        )
        if response.status_code != 200:
            logger.error(f"Groq API error {response.status_code}: {response.text[:500]}")
            return None

        content = response.json()["choices"][0]["message"]["content"]
        logger.info(f"Groq response received ({len(content)} chars).")

    except Exception as e:
        logger.error(f"Groq API error: {str(e)}")
        return None

    plan = parse_response(content, template_data, logger)
    if plan:
        logger.info(f"Text replacements: {len(plan.get('text_replacements', []))}")
        logger.info(f"Image prompts: {len(plan.get('image_prompts', []))}")
        voiceover = plan.get("voiceover_script", "")
        logger.info(f"Voiceover: {'Yes' if voiceover else 'No'}")
    return plan


def build_user_message(template_data, user_prompt):
    duration = template_data.get("duration_seconds", 10)
    width = template_data["resolution"]["width"]
    height = template_data["resolution"]["height"]
    text_tools = template_data.get("text_tools", [])
    loader_tools = template_data.get("loader_tools", [])

    text_desc = ""
    if text_tools:
        text_desc = "TEXT TOOLS IN TEMPLATE:\n"
        for t in text_tools:
            current = t["properties"].get("styled_text", "placeholder")
            text_desc += f'  - Tool name: "{t["name"]}", current text: "{current}"\n'
    else:
        text_desc = "No text tools detected. Generate 1-2 text items anyway.\n"

    image_desc = ""
    if loader_tools:
        image_desc = "IMAGE TOOLS IN TEMPLATE:\n"
        for l in loader_tools:
            fname = l["properties"].get("filename", "unknown")
            image_desc += f'  - Tool name: "{l["name"]}", current file: "{fname}"\n'
    else:
        image_desc = "No image tools detected. Generate 1 image prompt for a logo.\n"

    voiceover_note = ""
    if duration >= 8:
        voiceover_note = f"Generate a voiceover script timed to ~{duration:.0f} seconds (~2.5 words/sec).\n"
    else:
        voiceover_note = f"Video is only {duration:.1f}s. Set voiceover_script to empty string.\n"

    return f"""TEMPLATE INFO:
- Duration: {duration:.1f}s
- Resolution: {width}x{height}
- Format: DaVinci Resolve Fusion .comp

{text_desc}
{image_desc}
{voiceover_note}
USER BRIEF: {user_prompt}

Generate JSON:
{{
  "brand_name": "brand name",
  "tagline": "short tagline",
  "tone": "tone description",
  "color_scheme": {{"primary": "#hex", "secondary": "#hex", "accent": "#hex"}},
  "text_replacements": [
    {{"tool_name": "exact tool name from template", "new_text": "replacement text"}}
  ],
  "image_prompts": [
    {{"tool_name": "tool name or descriptive name", "prompt": "image description", "width": {width}, "height": {height}, "purpose": "logo or background"}}
  ],
  "voiceover_script": "narration or empty string"
}}

Output ONLY the JSON."""


def parse_response(text, template_data, logger):
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        logger.error("No JSON found in response.")
        return None

    try:
        plan = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        try:
            import re
            fixed = re.sub(r',\s*}', '}', text[start:end + 1])
            fixed = re.sub(r',\s*]', ']', fixed)
            plan = json.loads(fixed)
        except Exception:
            logger.error("Failed to parse JSON from response.")
            return None

    for field in ["text_replacements", "image_prompts"]:
        if field not in plan:
            plan[field] = []
    if "voiceover_script" not in plan:
        plan["voiceover_script"] = ""

    if not plan["text_replacements"]:
        brand = plan.get("brand_name", "Brand")
        plan["text_replacements"] = [{"tool_name": "Text1", "new_text": brand}]

    if not plan["image_prompts"]:
        brand = plan.get("brand_name", "Brand")
        w = template_data["resolution"]["width"]
        h = template_data["resolution"]["height"]
        plan["image_prompts"] = [{
            "tool_name": "Logo",
            "prompt": f"professional logo for {brand}",
            "width": w, "height": h, "purpose": "logo"
        }]

    return plan