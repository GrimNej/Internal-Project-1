"""
MoFA Effect v2 - Fusion .comp Parser
Detects ALL changeable elements as replaceable slots.
We do not care if original referenced files exist since
the user will overwrite them with their own content.
"""

import os
import re


def parse_comp_file(filepath, logger):
    """
    Parse a Fusion .comp file. Returns a dictionary with complete
    template structure and a list of all changeable element slots.
    """
    logger.section("Parsing Fusion .comp File")

    result = {
        "valid": False,
        "file_path": filepath,
        "file_size_kb": 0,
        "render_range": [0, 100],
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "duration_frames": 100,
        "duration_seconds": 3.33,
        "raw_content": "",
        "changeable_elements": [],
        "all_fonts_used": [],
    }

    if not os.path.isfile(filepath):
        logger.error(f"File not found: {filepath}")
        return result

    result["file_size_kb"] = round(os.path.getsize(filepath) / 1024, 2)
    logger.info(f"File: {filepath}")
    logger.info(f"Size: {result['file_size_kb']} KB")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="latin-1") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Cannot read file: {e}")
            return result

    result["raw_content"] = content

    if "Composition" not in content and "Tools" not in content:
        logger.error("File does not look like a Fusion .comp file.")
        return result

    result["valid"] = True
    logger.info("Valid Fusion .comp file detected.")

    start, end = extract_render_range(content)
    result["render_range"] = [start, end]
    result["duration_frames"] = end - start + 1
    result["fps"] = extract_fps(content)
    result["duration_seconds"] = round(result["duration_frames"] / result["fps"], 2)

    w, h = extract_resolution(content)
    result["width"] = w
    result["height"] = h

    logger.info(f"Range: {start}-{end} ({result['duration_frames']} frames)")
    logger.info(f"FPS: {result['fps']}")
    logger.info(f"Duration: {result['duration_seconds']}s")
    logger.info(f"Resolution: {w}x{h}")

    elements = []
    fonts_used = set()

    text_tools = find_text_tools(content, logger)
    for tool in text_tools:
        elements.append(tool)
        font = tool.get("font", "")
        if font:
            fonts_used.add(font)

    loader_tools = find_loader_tools(content, logger)
    for tool in loader_tools:
        elements.append(tool)

    bg_tools = find_background_tools(content, logger)
    for tool in bg_tools:
        elements.append(tool)

    media_tools = find_mediain_tools(content, logger)
    for tool in media_tools:
        elements.append(tool)

    for i, elem in enumerate(elements):
        elem["index"] = i + 1

    result["changeable_elements"] = elements
    result["all_fonts_used"] = sorted(fonts_used)

    logger.info(f"Changeable element slots found: {len(elements)}")
    logger.info(f"  Text slots: {sum(1 for e in elements if e['type'] == 'text')}")
    logger.info(f"  Image/Video slots: {sum(1 for e in elements if e['type'] == 'image')}")
    logger.info(f"  Color slots: {sum(1 for e in elements if e['type'] == 'color')}")
    logger.info(f"Fonts used: {len(fonts_used)}")

    return result


def extract_render_range(content):
    m = re.search(r'RenderRange\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}', content)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'GlobalRange\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}', content)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 100


def extract_fps(content):
    for pat in [r'FrameRate\s*=\s*(\d+)', r'FPS\s*=\s*(\d+)']:
        m = re.search(pat, content)
        if m:
            return int(m.group(1))
    return 30


def extract_resolution(content):
    w, h = 1920, 1080
    wm = re.search(r'Width\s*=\s*Input\s*\{\s*Value\s*=\s*(\d+)', content)
    hm = re.search(r'Height\s*=\s*Input\s*\{\s*Value\s*=\s*(\d+)', content)
    if wm:
        w = int(wm.group(1))
    if hm:
        h = int(hm.group(1))
    return w, h


def find_text_tools(content, logger):
    """Find all TextPlus and Text3D tools."""
    elements = []
    pattern = re.compile(r'(\w+)\s*=\s*(TextPlus|Text3D)\s*\{', re.MULTILINE)

    for match in pattern.finditer(content):
        name = match.group(1)
        tool_type = match.group(2)

        if name in ["Input", "Value", "Source", "SourceOp"]:
            continue

        region = content[match.end():match.end() + 8000]

        text_val = ""
        tm = re.search(r'\["StyledText"\]\s*=\s*Input\s*\{\s*Value\s*=\s*"([^"]*)"', region)
        if tm:
            text_val = tm.group(1)

        font_val = ""
        fm = re.search(r'\["Font"\]\s*=\s*Input\s*\{\s*Value\s*=\s*"([^"]*)"', region)
        if fm:
            font_val = fm.group(1)

        style_val = ""
        sm = re.search(r'\["Style"\]\s*=\s*Input\s*\{\s*Value\s*=\s*"([^"]*)"', region)
        if sm:
            style_val = sm.group(1)

        size_val = 0.05
        szm = re.search(r'\["Size"\]\s*=\s*Input\s*\{\s*Value\s*=\s*([\d.]+)', region)
        if szm:
            size_val = float(szm.group(1))

        color = {}
        for key, label in [("Red1", "r"), ("Green1", "g"), ("Blue1", "b")]:
            cm = re.search(rf'\["{key}"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*([\d.]+)', region)
            if cm:
                color[label] = float(cm.group(1))

        elements.append({
            "type": "text",
            "tool_name": name,
            "tool_type": tool_type,
            "current_value": text_val if text_val else "(empty)",
            "new_value": None,
            "font": font_val,
            "font_style": style_val,
            "font_size": size_val,
            "text_color": color,
            "position": match.start(),
        })

        logger.info(f"  Text slot [{name}]: \"{text_val}\" (font: {font_val})")

    return elements


def find_loader_tools(content, logger):
    """Find all Loader tools. These are image/video slots to fill."""
    elements = []
    pattern = re.compile(r'(\w+)\s*=\s*Loader\s*\{', re.MULTILINE)

    for match in pattern.finditer(content):
        name = match.group(1)

        if name in ["Input", "Value", "Source", "SourceOp"]:
            continue

        region = content[match.end():match.end() + 5000]

        filename = ""
        fm = re.search(r'Filename\s*=\s*"([^"]*)"', region)
        if fm:
            filename = fm.group(1)

        # Determine what kind of media this likely is
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        if ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
            media_type = "video"
        else:
            media_type = "image"

        elements.append({
            "type": "image",
            "tool_name": name,
            "tool_type": "Loader",
            "media_subtype": media_type,
            "current_value": filename if filename else "(empty slot)",
            "new_value": None,
            "position": match.start(),
        })

        logger.info(f"  {media_type.capitalize()} slot [{name}]: \"{filename}\"")

    return elements


def find_background_tools(content, logger):
    """Find all Background tools with their colors."""
    elements = []
    pattern = re.compile(r'(\w+)\s*=\s*Background\s*\{', re.MULTILINE)

    for match in pattern.finditer(content):
        name = match.group(1)

        if name in ["Input", "Value", "Source", "SourceOp"]:
            continue

        region = content[match.end():match.end() + 3000]

        color = {"r": 0.0, "g": 0.0, "b": 0.0}
        for key, label in [("TopLeftRed", "r"), ("TopLeftGreen", "g"), ("TopLeftBlue", "b")]:
            cm = re.search(rf'\["{key}"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*([\d.]+)', region)
            if cm:
                color[label] = float(cm.group(1))

        hex_color = rgb_float_to_hex(color["r"], color["g"], color["b"])

        elements.append({
            "type": "color",
            "tool_name": name,
            "tool_type": "Background",
            "current_value": hex_color,
            "current_rgb": color,
            "new_value": None,
            "position": match.start(),
        })

        logger.info(f"  Color slot [{name}]: {hex_color}")

    return elements


def find_mediain_tools(content, logger):
    """Find MediaIn tools (Resolve Fusion page media references)."""
    elements = []
    pattern = re.compile(r'(\w+)\s*=\s*MediaIn\s*\{', re.MULTILINE)

    for match in pattern.finditer(content):
        name = match.group(1)
        if name in ["Input", "Value", "Source", "SourceOp"]:
            continue

        elements.append({
            "type": "image",
            "tool_name": name,
            "tool_type": "MediaIn",
            "media_subtype": "timeline_media",
            "current_value": "(Resolve timeline media)",
            "new_value": None,
            "position": match.start(),
        })
        logger.info(f"  Media slot [{name}]: (timeline reference)")

    return elements


def rgb_float_to_hex(r, g, b):
    ri = max(0, min(255, int(r * 255)))
    gi = max(0, min(255, int(g * 255)))
    bi = max(0, min(255, int(b * 255)))
    return f"#{ri:02x}{gi:02x}{bi:02x}"