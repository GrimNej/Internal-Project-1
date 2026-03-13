"""
MoFA Effect v2 - Fusion .comp Parser
Handles the real .comp structure:
  - Text values live in BezierSpline keyframes (NamedSpline pattern),
    NOT directly in the TextPlus tool block.
  - Image filenames live inside Clips { Clip { Filename = "..." } }
    blocks, NOT in Inputs.
  - Background colors are also driven by BezierSplines.
"""

import os
import re


def parse_comp_file(filepath, logger):
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
        # Resolution for AI helpers
        "resolution": {"width": 1920, "height": 1080},
        # Flat lists used by ai_script_generator
        "text_tools": [],
        "loader_tools": [],
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
    result["resolution"] = {"width": w, "height": h}

    logger.info(f"Range: {start}-{end} ({result['duration_frames']} frames)")
    logger.info(f"FPS: {result['fps']}")
    logger.info(f"Duration: {result['duration_seconds']}s")
    logger.info(f"Resolution: {w}x{h}")

    elements = []
    fonts_used = set()

    # ------------------------------------------------------------------
    # 1. Named BezierSplines that drive TextPlus tools
    #    Pattern: <ToolName>StyledText = BezierSpline { ... KeyFrames { ... Value = Text { Value = "..." } ... } }
    #    We find all such splines, collect their unique non-empty text
    #    values, and expose them as a single multi-value text element.
    # ------------------------------------------------------------------
    text_spline_tools = find_text_splines(content, logger)
    for tool in text_spline_tools:
        elements.append(tool)

    # Also find inline StyledText (non-animated, directly in TextPlus)
    inline_text_tools = find_inline_text_tools(content, text_spline_tools, logger)
    for tool in inline_text_tools:
        elements.append(tool)

    # Populate flat text_tools list for ai_script_generator compatibility
    for e in elements:
        if e["type"] == "text":
            result["text_tools"].append({
                "name": e["tool_name"],
                "properties": {
                    "styled_text": e["current_values"][0] if e.get("current_values") else e.get("current_value", "")
                }
            })

    # ------------------------------------------------------------------
    # 2. Loader / MediaIn tools (image/video slots)
    #    Filename is inside Clips { Clip { Filename = "..." } }
    # ------------------------------------------------------------------
    loader_tools = find_loader_tools(content, logger)
    for tool in loader_tools:
        elements.append(tool)
        result["loader_tools"].append({
            "name": tool["tool_name"],
            "properties": {"filename": tool["current_value"]}
        })

    # ------------------------------------------------------------------
    # 3. Background color tools
    #    Colors are driven by BezierSplines; we read their first keyframe value.
    # ------------------------------------------------------------------
    bg_tools = find_background_tools(content, logger)
    for tool in bg_tools:
        elements.append(tool)

    # 4. Fonts from Text splines
    font_splines = find_font_splines(content, logger)
    for font in font_splines:
        fonts_used.add(font)

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


# ======================================================================
# Render range / FPS / resolution helpers
# ======================================================================

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
    # Prefer the first Width/Height that looks like resolution (not a tool-local one)
    wm = re.search(r'\bWidth\s*=\s*Input\s*\{\s*Value\s*=\s*(\d+)', content)
    hm = re.search(r'\bHeight\s*=\s*Input\s*\{\s*Value\s*=\s*(\d+)', content)
    if wm:
        w = int(wm.group(1))
    if hm:
        h = int(hm.group(1))
    return w, h


# ======================================================================
# Text detection — BezierSpline keyframe pattern
# ======================================================================

def find_text_splines(content, logger):
    """
    Find all  <ToolBaseName>StyledText = BezierSpline { ... }  blocks.

    The TextPlus tool has its StyledText driven by a named spline, e.g.:
        Text1StyledText = BezierSpline {
            KeyFrames = {
                [4.98] = { ..., Value = Text { Value = "GET" } },
                [11.9] = { ..., Value = Text { Value = "A NEW" } },
                ...
            }
        }

    We collect all unique non-empty text values across all keyframes.
    The modifier will replace ALL keyframe values with the user's new texts.
    """
    elements = []
    # Match the spline block
    spline_pattern = re.compile(
        r'(\w+)StyledText\s*=\s*BezierSpline\s*\{', re.MULTILINE
    )

    for match in spline_pattern.finditer(content):
        base_name = match.group(1)           # e.g. "Text1"
        spline_name = f"{base_name}StyledText"
        tool_name = base_name                 # logical name shown to user

        # Extract the full spline block (find matching closing brace)
        block_start = match.end()
        block = extract_block(content, block_start)

        # Find all  Value = Text { Value = "..." }  entries
        text_values = re.findall(
            r'Value\s*=\s*Text\s*\{\s*Value\s*=\s*"([^"]*)"\s*\}',
            block
        )

        # Deduplicate while preserving order, skip empty
        seen = set()
        unique_vals = []
        for v in text_values:
            if v and v not in seen:
                seen.add(v)
                unique_vals.append(v)

        display = unique_vals if unique_vals else ["(empty)"]

        logger.info(
            f"  Text spline [{spline_name}]: {unique_vals} "
            f"({len(text_values)} keyframes)"
        )

        elements.append({
            "type": "text",
            "tool_name": tool_name,
            "spline_name": spline_name,
            "source": "spline",
            "current_values": unique_vals,       # list of distinct text values
            "current_value": " / ".join(display),
            "new_value": None,                   # user will fill this in
            "new_values": None,                  # optional: list matching current_values
            "keyframe_count": len(text_values),
            "position": match.start(),
        })

    return elements


def find_inline_text_tools(content, spline_tools, logger):
    """
    Find TextPlus/Text3D tools where StyledText is set directly (not via SourceOp).
    Skip any whose name already appears in spline_tools.
    """
    already_found = {t["tool_name"] for t in spline_tools}
    elements = []
    pattern = re.compile(r'(\w+)\s*=\s*(TextPlus|Text3D)\s*\{', re.MULTILINE)

    for match in pattern.finditer(content):
        name = match.group(1)
        if name in already_found or name in ("Input", "Value", "Source", "SourceOp"):
            continue

        region = content[match.end():match.end() + 8000]

        # Only include if StyledText has an inline Value (not a SourceOp)
        tm = re.search(
            r'\["StyledText"\]\s*=\s*Input\s*\{\s*Value\s*=\s*"([^"]*)"',
            region
        )
        if not tm:
            continue

        text_val = tm.group(1)
        font_val = ""
        fm = re.search(r'\["Font"\]\s*=\s*Input\s*\{\s*Value\s*=\s*"([^"]*)"', region)
        if fm:
            font_val = fm.group(1)

        logger.info(f"  Inline text [{name}]: \"{text_val}\" (font: {font_val})")
        elements.append({
            "type": "text",
            "tool_name": name,
            "spline_name": None,
            "source": "inline",
            "current_values": [text_val] if text_val else [],
            "current_value": text_val if text_val else "(empty)",
            "new_value": None,
            "new_values": None,
            "font": font_val,
            "position": match.start(),
        })

    return elements


# ======================================================================
# Font detection from BezierSpline (e.g. Text1Font = BezierSpline)
# ======================================================================

def find_font_splines(content, logger):
    """Extract font family names from <ToolName>Font = BezierSpline blocks."""
    fonts = set()
    pattern = re.compile(r'\w+Font\s*=\s*BezierSpline\s*\{', re.MULTILINE)
    for match in pattern.finditer(content):
        block = extract_block(content, match.end())
        for font_name in re.findall(
            r'Value\s*=\s*Text\s*\{\s*Value\s*=\s*"([^"]+)"\s*\}', block
        ):
            fonts.add(font_name)
    return fonts


# ======================================================================
# Loader / MediaIn detection (Clips > Clip > Filename pattern)
# ======================================================================

def find_loader_tools(content, logger):
    """
    Find Loader tools.  Filename lives inside:
        MediaIn1 = Loader {
            ...
            Clips {
                Clip {
                    Filename = "/path/to/file.png",
                    ...
                }
            }
        }
    Also handles MEDIA_PATH in CustomData as a fallback.
    """
    elements = []
    pattern = re.compile(r'(\w+)\s*=\s*Loader\s*\{', re.MULTILINE)

    for match in pattern.finditer(content):
        name = match.group(1)
        if name in ("Input", "Value", "Source", "SourceOp"):
            continue

        block = extract_block(content, match.end())

        # Primary: Filename inside Clips = { Clip { ... } } block
        filename = ""
        clips_m = re.search(r'Clips\s*=\s*\{', block)
        if clips_m:
            clips_block = extract_block(block, clips_m.end())
            fn_m = re.search(r'Filename\s*=\s*"([^"]*)"', clips_block)
            if fn_m:
                filename = fn_m.group(1)

        # Fallback: MEDIA_PATH in CustomData
        if not filename:
            mp_m = re.search(r'MEDIA_PATH\s*=\s*"([^"]+)"', block)
            if mp_m:
                filename = mp_m.group(1)

        ext = os.path.splitext(filename)[1].lower() if filename else ""
        media_type = "video" if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm") else "image"

        logger.info(f"  {media_type.capitalize()} slot [{name}]: \"{filename}\"")
        elements.append({
            "type": "image",
            "tool_name": name,
            "tool_type": "Loader",
            "media_subtype": media_type,
            "current_value": filename if filename else "(empty slot)",
            "new_value": None,
            "position": match.start(),
        })

    return elements


# ======================================================================
# Background color detection (values live in named BezierSplines)
# ======================================================================

def find_background_tools(content, logger):
    """
    Find Background tools.  Colors are driven by named splines:
        Background1TopLeftRed = BezierSpline { KeyFrames { [t] = { 0.96, ... } } }

    We read the first numeric keyframe value for R/G/B.
    We also need to detect the Background tool itself so we know the name.
    """
    elements = []
    bg_pattern = re.compile(r'(\w+)\s*=\s*Background\s*\{', re.MULTILINE)

    for match in bg_pattern.finditer(content):
        name = match.group(1)
        if name in ("Input", "Value", "Source", "SourceOp"):
            continue

        block = extract_block(content, match.end())

        # Check whether TopLeftRed is inline or via SourceOp
        r_val = g_val = b_val = None

        # Inline case
        for key, label in [("TopLeftRed", "r"), ("TopLeftGreen", "g"), ("TopLeftBlue", "b")]:
            cm = re.search(
                rf'\["{key}"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*([\d.]+)', block
            )
            if cm:
                if label == "r":
                    r_val = float(cm.group(1))
                elif label == "g":
                    g_val = float(cm.group(1))
                elif label == "b":
                    b_val = float(cm.group(1))

        # SourceOp case — look up the named spline
        for key, label in [("TopLeftRed", "r"), ("TopLeftGreen", "g"), ("TopLeftBlue", "b")]:
            if label == "r" and r_val is not None:
                continue
            if label == "g" and g_val is not None:
                continue
            if label == "b" and b_val is not None:
                continue

            src_m = re.search(
                rf'\["{key}"\]\s*=\s*Input\s*\{{\s*SourceOp\s*=\s*"(\w+)"', block
            )
            if src_m:
                spline_name = src_m.group(1)
                val = read_first_spline_value(content, spline_name)
                if val is not None:
                    if label == "r":
                        r_val = val
                    elif label == "g":
                        g_val = val
                    elif label == "b":
                        b_val = val

        r_val = r_val or 0.0
        g_val = g_val or 0.0
        b_val = b_val or 0.0
        hex_color = rgb_float_to_hex(r_val, g_val, b_val)

        logger.info(f"  Color slot [{name}]: {hex_color}")
        elements.append({
            "type": "color",
            "tool_name": name,
            "tool_type": "Background",
            "current_value": hex_color,
            "current_rgb": {"r": r_val, "g": g_val, "b": b_val},
            "new_value": None,
            "position": match.start(),
        })

    return elements


# ======================================================================
# Helpers
# ======================================================================

def extract_block(content, start_pos):
    """
    Extract the content of a Lua-style { } block starting at start_pos.
    start_pos should point just AFTER the opening '{'.
    Returns the inner content string (without the outer braces).
    """
    depth = 1
    i = start_pos
    n = len(content)
    while i < n and depth > 0:
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return content[start_pos:i - 1]


def read_first_spline_value(content, spline_name):
    """
    Read the first numeric keyframe value from a named BezierSpline.
    E.g. Background1TopLeftRed = BezierSpline { KeyFrames { [t] = { 0.96, ... } } }
    Returns float or None.
    """
    pattern = re.compile(
        rf'{re.escape(spline_name)}\s*=\s*BezierSpline\s*\{{', re.MULTILINE
    )
    m = pattern.search(content)
    if not m:
        return None
    block = extract_block(content, m.end())
    # First keyframe: [timestamp] = { numeric_value, ...}
    val_m = re.search(r'\[\s*[\d.]+\s*\]\s*=\s*\{\s*([\d.]+)', block)
    if val_m:
        return float(val_m.group(1))
    return None


def rgb_float_to_hex(r, g, b):
    ri = max(0, min(255, int(r * 255)))
    gi = max(0, min(255, int(g * 255)))
    bi = max(0, min(255, int(b * 255)))
    return f"#{ri:02x}{gi:02x}{bi:02x}"