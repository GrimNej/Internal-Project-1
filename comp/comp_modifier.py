"""
MoFA Effect v2 - Fusion .comp Modifier
Applies user changes to the .comp file: text (spline keyframes), images, colors, fonts.

Key fixes vs v1:
  - Text lives in BezierSpline keyframes, not directly in TextPlus.
    We replace ALL keyframe Text values inside the named spline.
  - Image Filename lives inside Clips { Clip { Filename = "..." } },
    not in Inputs directly. We also update MEDIA_PATH in CustomData.
  - Background colors are driven by named BezierSplines; we patch
    every numeric keyframe value in those splines.
"""

import os
import re
import shutil
import time

from config import OUTPUT_DIR


def apply_changes(original_path, template_data, font_fallback_map, logger):
    logger.section("Applying Changes to .comp File")

    basename = os.path.splitext(os.path.basename(original_path))[0]
    basename = basename.replace(" ", "_")   # spaces in filenames break Resolve's ImportMedia
    timestamp = int(time.time())
    modified_path = os.path.join(OUTPUT_DIR, f"{basename}_mofa_{timestamp}.comp")

    shutil.copy2(original_path, modified_path)
    logger.info(f"Working copy: {modified_path}")

    try:
        with open(modified_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(modified_path, "r", encoding="latin-1") as f:
            content = f.read()

    changes = 0
    elements = template_data.get("changeable_elements", [])

    for elem in elements:
        if elem.get("new_value") is None:
            continue

        if elem["type"] == "text":
            source = elem.get("source", "inline")

            if source == "spline":
                # Replace all keyframe text values in the named BezierSpline
                spline_name = elem.get("spline_name")
                new_vals = elem.get("new_values") or _expand_new_values(
                    elem["new_value"],
                    elem.get("current_values", [])
                )
                content, ok = replace_spline_text_keyframes(
                    content, spline_name, new_vals
                )
                if ok:
                    logger.info(
                        f"  Text spline [{spline_name}] -> {new_vals}"
                    )
                    changes += 1
                else:
                    logger.warning(f"  Could not find spline: {spline_name}")

            else:
                # Inline StyledText inside TextPlus block
                content, ok = replace_inline_text(
                    content, elem["tool_name"], elem["new_value"]
                )
                if ok:
                    logger.info(
                        f"  Text [{elem['tool_name']}] -> \"{elem['new_value']}\""
                    )
                    changes += 1

        elif elem["type"] == "image":
            new_path = elem["new_value"]
            if os.path.isfile(new_path):
                norm_path = new_path.replace("\\", "/")
                content, ok = replace_loader_filename(
                    content, elem["tool_name"], norm_path
                )
                if ok:
                    logger.info(
                        f"  Image [{elem['tool_name']}] -> {os.path.basename(new_path)}"
                    )
                    changes += 1
            else:
                logger.warning(f"  Image file not found: {new_path}")

        elif elem["type"] == "color":
            content, ok = replace_background_color(
                content, elem["tool_name"], elem["new_value"]
            )
            if ok:
                logger.info(
                    f"  Color [{elem['tool_name']}] -> {elem['new_value']}"
                )
                changes += 1

    # Font fallbacks (specific mappings, legacy)
    for original_font, fallback_font in font_fallback_map.items():
        content, ok = replace_font_globally(content, original_font, fallback_font)
        if ok:
            logger.info(f"  Font \"{original_font}\" -> \"{fallback_font}\" (fallback)")
            changes += 1

    # Always rewrite ALL font+style splines to a single safe installed font.
    # This eliminates "Could not find font: X: Light" errors entirely.
    replacement_font = template_data.get("replacement_font", "Arial")
    content, font_changes = rewrite_all_fonts(content, replacement_font, logger)
    changes += font_changes

    with open(modified_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Total changes applied: {changes}")
    logger.info(f"Modified file saved: {modified_path}")
    return modified_path


# ======================================================================
# Text replacement
# ======================================================================

def _expand_new_values(new_value_str, current_values):
    """
    Turn the user's single new_value string into a list matching
    the number of distinct text slots in the spline.

    If the user types "WELCOME / TO / MOFA" we split on " / ".
    If they type a single value, we replicate it for all slots.
    If there are more slots than provided values, we cycle the last value.
    """
    parts = [p.strip() for p in new_value_str.split(" / ") if p.strip()]
    if not parts:
        parts = [new_value_str]

    n = max(len(current_values), 1)
    if len(parts) < n:
        # Pad with the last provided value
        parts = parts + [parts[-1]] * (n - len(parts))

    return parts[:n] if len(parts) > n else parts


def replace_spline_text_keyframes(content, spline_name, new_values):
    """
    Find the BezierSpline named `spline_name` and replace every
    `Value = Text { Value = "OLD" }` entry with successive values
    from `new_values`.

    If new_values has fewer entries than keyframes, the last value is reused.
    If new_values has more entries, extras are ignored.
    """
    pattern = re.compile(
        rf'{re.escape(spline_name)}\s*=\s*BezierSpline\s*\{{',
        re.MULTILINE
    )
    m = pattern.search(content)
    if not m:
        return content, False

    block_start = m.end()
    block_end = find_block_end(content, block_start)
    block = content[block_start:block_end]

    # Replace each  Value = Text { Value = "..." }  in order
    kf_pattern = re.compile(
        r'(Value\s*=\s*Text\s*\{\s*Value\s*=\s*)"([^"]*)"'
    )

    replace_idx = [0]  # mutable counter inside closure

    def replacer(mo):
        idx = replace_idx[0]
        replace_idx[0] += 1
        val = new_values[min(idx, len(new_values) - 1)]
        safe = val.replace("\\", "\\\\").replace('"', '\\"')
        return mo.group(1) + f'"{safe}"'

    new_block, count = kf_pattern.subn(replacer, block)

    if count == 0:
        return content, False

    content = content[:block_start] + new_block + content[block_end:]
    return content, True


def replace_inline_text(content, tool_name, new_text):
    """Replace StyledText inline value in a TextPlus tool block."""
    escaped_name = re.escape(tool_name)
    tool_match = re.search(
        rf'{escaped_name}\s*=\s*(TextPlus|Text3D)\s*\{{', content
    )
    if not tool_match:
        return content, False

    start = tool_match.end()
    region = content[start:start + 8000]

    pattern = re.compile(
        r'(\["StyledText"\]\s*=\s*Input\s*\{\s*Value\s*=\s*)"([^"]*)"'
    )
    mo = pattern.search(region)
    if not mo:
        return content, False

    safe_text = new_text.replace("\\", "\\\\").replace('"', '\\"')
    abs_start = start + mo.start(2)
    abs_end = start + mo.end(2)
    content = content[:abs_start] + safe_text + content[abs_end:]
    return content, True


# ======================================================================
# Image / Loader replacement
# ======================================================================

def replace_loader_filename(content, tool_name, new_path):
    """
    Replace the Filename inside Clips { Clip { Filename = "..." } }
    for a named Loader tool. Also updates MEDIA_PATH in CustomData.
    """
    escaped_name = re.escape(tool_name)
    tool_m = re.search(
        rf'{escaped_name}\s*=\s*Loader\s*\{{', content
    )
    if not tool_m:
        return content, False

    # Find the full Loader block
    block_start = tool_m.end()
    block_end = find_block_end(content, block_start)
    block = content[block_start:block_end]

    changed = False

    # 1. Replace Filename inside Clips = { Clip { ... } } block
    clips_m = re.search(r'Clips\s*=\s*\{', block)
    if clips_m:
        clips_block_start = clips_m.end()
        clips_block_end = find_block_end(block, clips_block_start)
        clips_inner = block[clips_block_start:clips_block_end]

        fn_pattern = re.compile(r'(Filename\s*=\s*)"([^"]*)"')
        fn_mo = fn_pattern.search(clips_inner)
        if fn_mo:
            new_clips_inner = (
                clips_inner[:fn_mo.start(2)]
                + new_path
                + clips_inner[fn_mo.end(2):]
            )
            block = (
                block[:clips_block_start]
                + new_clips_inner
                + block[clips_block_end:]
            )
            changed = True

    # 2. Update MEDIA_PATH in CustomData (cosmetic, keeps Resolve happy)
    media_path_pattern = re.compile(r'(MEDIA_PATH\s*=\s*)"([^"]*)"')
    mp_mo = media_path_pattern.search(block)
    if mp_mo:
        block = (
            block[:mp_mo.start(2)]
            + new_path
            + block[mp_mo.end(2):]
        )

    # 3. Update MEDIA_NAME
    media_name_pattern = re.compile(r'(MEDIA_NAME\s*=\s*)"([^"]*)"')
    mn_mo = media_name_pattern.search(block)
    if mn_mo:
        block = (
            block[:mn_mo.start(2)]
            + os.path.basename(new_path)
            + block[mn_mo.end(2):]
        )

    if changed:
        content = content[:block_start] + block + content[block_end:]

    return content, changed


# ======================================================================
# Background color replacement
# ======================================================================

def replace_background_color(content, tool_name, hex_color):
    """
    Replace background color. The Background tool's TopLeftRed/Green/Blue
    may be either inline or driven by named BezierSplines.
    We handle both cases.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return content, False

    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
    except ValueError:
        return content, False

    escaped_name = re.escape(tool_name)
    tool_m = re.search(
        rf'{escaped_name}\s*=\s*Background\s*\{{', content
    )
    if not tool_m:
        return content, False

    block_start = tool_m.end()
    block_end = find_block_end(content, block_start)
    block = content[block_start:block_end]

    changed = False

    for key, val in [("TopLeftRed", r), ("TopLeftGreen", g), ("TopLeftBlue", b)]:
        # Check if inline
        inline_pat = re.compile(
            rf'(\["{key}"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*)[\d.]+'
        )
        mo = inline_pat.search(block)
        if mo:
            block = block[:mo.end(1)] + f"{val:.6f}" + block[mo.end():]
            changed = True
            continue

        # Check if driven by a SourceOp spline
        src_pat = re.compile(
            rf'\["{key}"\]\s*=\s*Input\s*\{{\s*SourceOp\s*=\s*"(\w+)"'
        )
        src_mo = src_pat.search(block)
        if src_mo:
            spline_name = src_mo.group(1)
            content, ok = replace_all_spline_numeric_values(
                content, spline_name, val
            )
            if ok:
                changed = True

    if changed and not any(
        re.search(
            rf'\["TopLeft{c}"\]\s*=\s*Input\s*\{{\s*SourceOp', block
        )
        for c in ("Red", "Green", "Blue")
    ):
        content = content[:block_start] + block + content[block_end:]

    return content, changed


def replace_all_spline_numeric_values(content, spline_name, new_val):
    """
    Replace every numeric keyframe value in a BezierSpline with new_val.
    Used for color channel splines (Background1TopLeftRed, etc.)
    """
    pattern = re.compile(
        rf'{re.escape(spline_name)}\s*=\s*BezierSpline\s*\{{',
        re.MULTILINE
    )
    m = pattern.search(content)
    if not m:
        return content, False

    block_start = m.end()
    block_end = find_block_end(content, block_start)
    block = content[block_start:block_end]

    # Replace the primary value at each keyframe: [t] = { VALUE, RH/LH... }
    kf_val_pat = re.compile(
        r'(\[\s*[\d.]+\s*\]\s*=\s*\{)\s*([\d.]+)'
    )
    new_block = kf_val_pat.sub(
        lambda mo: mo.group(1) + f" {new_val:.6f}", block
    )

    if new_block == block:
        return content, False

    content = content[:block_start] + new_block + content[block_end:]
    return content, True


# ======================================================================
# Font replacement
# ======================================================================

def replace_font_globally(content, original_font, fallback_font):
    pattern = re.compile(
        rf'(\["Font"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*"){re.escape(original_font)}"'
    )
    new_content, count = pattern.subn(rf'\g<1>{fallback_font}"', content)
    # Also replace inside BezierSpline keyframes
    spline_pattern = re.compile(
        rf'(Value\s*=\s*Text\s*\{{\s*Value\s*=\s*"){re.escape(original_font)}"'
    )
    new_content, count2 = spline_pattern.subn(rf'\g<1>{fallback_font}"', new_content)
    return new_content, (count + count2) > 0




def rewrite_all_fonts(content, replacement_font, logger):
    """
    Replace every font name AND style value inside ALL *Font and *Style
    BezierSpline keyframes with a single safe font and "Regular" style.

    This is the nuclear option that completely eliminates Resolve's
    "Could not find font: X: Light" errors — no downloads needed.

    Before: Value = Text { Value = "Bebas Neue" }  (in Text1Font spline)
    After:  Value = Text { Value = "Arial" }

    Before: Value = Text { Value = "Light" }       (in Text1Style spline)
    After:  Value = Text { Value = "Regular" }
    """
    changes = 0

    # Replace all font names inside *Font splines
    # Matches: Value = Text {\n\t\t\t\t\tValue = "Anything"
    font_text_pat = re.compile(
        r'(Value\s*=\s*Text\s*\{\s*\n\s*Value\s*=\s*")([^"]+)(")',
    )

    def _replace_font_or_style(spline_name, replacement_value, spline_content):
        return font_text_pat.sub(
            lambda m: m.group(1) + replacement_value + m.group(3),
            spline_content
        )

    # Find all *Font splines and replace their keyframe text values
    font_spline_pat = re.compile(r'(\w+Font)\s*=\s*BezierSpline\s*\{', re.MULTILINE)
    for m in list(font_spline_pat.finditer(content))[::-1]:  # reverse to preserve offsets
        spline_name = m.group(1)
        block_start = m.end()
        block_end = find_block_end(content, block_start)
        block = content[block_start:block_end]
        new_block = _replace_font_or_style(spline_name, replacement_font, block)
        if new_block != block:
            content = content[:block_start] + new_block + content[block_end:]
            changes += 1
            logger.info(f"  Font spline [{spline_name}] -> all keyframes set to \"{replacement_font}\"")

    # Find all *Style splines and replace with "Regular"
    style_spline_pat = re.compile(r'(\w+Style)\s*=\s*BezierSpline\s*\{', re.MULTILINE)
    for m in list(style_spline_pat.finditer(content))[::-1]:
        spline_name = m.group(1)
        block_start = m.end()
        block_end = find_block_end(content, block_start)
        block = content[block_start:block_end]
        new_block = _replace_font_or_style(spline_name, "Regular", block)
        if new_block != block:
            content = content[:block_start] + new_block + content[block_end:]
            changes += 1
            logger.info(f"  Style spline [{spline_name}] -> all keyframes set to \"Regular\"")

    return content, changes

# ======================================================================
# Block extraction helper
# ======================================================================

def find_block_end(content, start_pos):
    """
    Find the position just after the closing '}' of a Lua-style block.
    `start_pos` should be just after the opening '{'.
    Returns the index of the char after the closing '}'.
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
    return i