"""
MoFA Effect v2 - Fusion .comp Modifier
Applies user changes to the .comp file: text, images, colors, fonts.
"""

import os
import re
import shutil
import time

from config import OUTPUT_DIR


def apply_changes(original_path, template_data, font_fallback_map, logger):
    """
    Create a modified copy of the .comp file with all user changes applied.
    Returns path to the modified .comp file.
    """
    logger.section("Applying Changes to .comp File")

    basename = os.path.splitext(os.path.basename(original_path))[0]
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
            content, ok = replace_text_in_tool(
                content, elem["tool_name"], elem["new_value"]
            )
            if ok:
                logger.info(f"  Text [{elem['tool_name']}] -> \"{elem['new_value']}\"")
                changes += 1

        elif elem["type"] == "image":
            new_path = elem["new_value"]
            if os.path.isfile(new_path):
                norm_path = new_path.replace("\\", "/")
                content, ok = replace_loader_filename(
                    content, elem["tool_name"], norm_path
                )
                if ok:
                    logger.info(f"  Image [{elem['tool_name']}] -> {os.path.basename(new_path)}")
                    changes += 1
            else:
                logger.warning(f"  Image file not found: {new_path}")

        elif elem["type"] == "color":
            content, ok = replace_background_color(
                content, elem["tool_name"], elem["new_value"]
            )
            if ok:
                logger.info(f"  Color [{elem['tool_name']}] -> {elem['new_value']}")
                changes += 1

    # Apply font fallbacks for missing fonts
    for original_font, fallback_font in font_fallback_map.items():
        content, ok = replace_font_globally(content, original_font, fallback_font)
        if ok:
            logger.info(f"  Font \"{original_font}\" -> \"{fallback_font}\" (fallback)")
            changes += 1

    with open(modified_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Total changes applied: {changes}")
    logger.info(f"Modified file saved: {modified_path}")

    return modified_path


def replace_text_in_tool(content, tool_name, new_text):
    """Replace StyledText value in a named TextPlus tool."""
    escaped_name = re.escape(tool_name)
    tool_match = re.search(rf'{escaped_name}\s*=\s*(TextPlus|Text3D)\s*\{{', content)
    if not tool_match:
        return content, False

    start = tool_match.end()
    region = content[start:start + 8000]

    pattern = re.compile(r'(\["StyledText"\]\s*=\s*Input\s*\{\s*Value\s*=\s*)"([^"]*)"')
    m = pattern.search(region)
    if not m:
        return content, False

    # Escape special characters for Lua string
    safe_text = new_text.replace("\\", "\\\\").replace('"', '\\"')

    abs_start = start + m.start(2)
    abs_end = start + m.end(2)
    content = content[:abs_start] + safe_text + content[abs_end:]
    return content, True


def replace_loader_filename(content, tool_name, new_path):
    """Replace Filename in a named Loader tool."""
    escaped_name = re.escape(tool_name)
    tool_match = re.search(rf'{escaped_name}\s*=\s*Loader\s*\{{', content)
    if not tool_match:
        return content, False

    start = tool_match.end()
    region = content[start:start + 5000]

    pattern = re.compile(r'(Filename\s*=\s*)"([^"]*)"')
    m = pattern.search(region)
    if not m:
        return content, False

    abs_start = start + m.start(2)
    abs_end = start + m.end(2)
    content = content[:abs_start] + new_path + content[abs_end:]
    return content, True


def replace_background_color(content, tool_name, hex_color):
    """Replace background color in a named Background tool."""
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
    tool_match = re.search(rf'{escaped_name}\s*=\s*Background\s*\{{', content)
    if not tool_match:
        return content, False

    start = tool_match.end()
    region_end = min(start + 3000, len(content))

    changed = False
    for key, val in [("TopLeftRed", r), ("TopLeftGreen", g), ("TopLeftBlue", b)]:
        pattern = re.compile(
            rf'(\["{key}"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*)[\d.]+'
        )
        region = content[start:region_end]
        m = pattern.search(region)
        if m:
            abs_pos = start + m.start()
            abs_end_pos = start + m.end()
            replacement = m.group(1) + f"{val:.6f}"
            content = content[:abs_pos] + replacement + content[abs_end_pos:]
            changed = True

    return content, changed


def replace_font_globally(content, original_font, fallback_font):
    """Replace all occurrences of a font name with its fallback."""
    pattern = re.compile(
        rf'(\["Font"\]\s*=\s*Input\s*\{{\s*Value\s*=\s*"){re.escape(original_font)}"'
    )
    new_content, count = pattern.subn(rf'\g<1>{fallback_font}"', content)
    return new_content, count > 0