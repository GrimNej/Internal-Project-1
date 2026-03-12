"""
MoFA Effect v2 - Font Manager
Checks if fonts referenced in the .comp file are available on the system.
Provides fallback suggestions for missing fonts.
"""

import os
import re
import glob

from config import WINDOWS_FONTS_DIR, SAFE_FALLBACK_FONTS


def check_fonts(template_data, logger):
    """
    Check availability of all fonts used in the template.
    Returns a font report with status and fallback suggestions.
    """
    logger.section("Font Availability Check")

    fonts_used = template_data.get("all_fonts_used", [])
    if not fonts_used:
        logger.info("No fonts referenced in template.")
        return {"fonts": [], "all_available": True}

    # Build index of installed fonts
    installed = scan_installed_fonts(logger)
    logger.info(f"System fonts indexed: {len(installed)}")

    report = {"fonts": [], "all_available": True}

    for font_name in fonts_used:
        available = is_font_available(font_name, installed)
        fallback = None

        if not available:
            report["all_available"] = False
            fallback = find_best_fallback(font_name, installed)
            logger.warning(
                f"  MISSING: \"{font_name}\" -> fallback: \"{fallback}\""
            )
        else:
            logger.info(f"  OK: \"{font_name}\"")

        report["fonts"].append({
            "name": font_name,
            "available": available,
            "fallback": fallback,
        })

    return report


def scan_installed_fonts(logger):
    """
    Scan the Windows Fonts directory and build a set of available
    font family names (lowercased for matching).
    """
    installed = set()

    if not os.path.isdir(WINDOWS_FONTS_DIR):
        logger.warning(f"Fonts directory not found: {WINDOWS_FONTS_DIR}")
        return installed

    font_files = (
        glob.glob(os.path.join(WINDOWS_FONTS_DIR, "*.ttf")) +
        glob.glob(os.path.join(WINDOWS_FONTS_DIR, "*.otf")) +
        glob.glob(os.path.join(WINDOWS_FONTS_DIR, "*.ttc"))
    )

    for fpath in font_files:
        basename = os.path.splitext(os.path.basename(fpath))[0]

        # Clean up filename to approximate font family name
        # "arialbd" -> "arial"
        # "OpenSans-Bold" -> "opensans"
        # "SegoeUI-Semibold" -> "segoeui"
        clean = basename.lower()
        clean = re.sub(r'[-_](bold|italic|light|thin|medium|semibold|regular|condensed|narrow|black|heavy|extra|demi|book|oblique|bd|bi|it|lt|bl|sb|md).*', '', clean)
        clean = re.sub(r'[^a-z0-9]', '', clean)

        installed.add(clean)

        # Also add the full basename for exact matching
        installed.add(basename.lower())

    # Add common font family names explicitly
    common_mappings = {
        "arial": "arial",
        "segoeui": "segoe ui",
        "segoe ui": "segoeui",
        "calibri": "calibri",
        "verdana": "verdana",
        "tahoma": "tahoma",
        "timesnewroman": "times new roman",
        "times new roman": "timesnewroman",
        "couriernew": "courier new",
        "courier new": "couriernew",
        "consolas": "consolas",
        "georgia": "georgia",
        "trebuchetms": "trebuchet ms",
        "trebuchet ms": "trebuchetms",
        "impact": "impact",
        "comicsansms": "comic sans ms",
        "palatino": "palatino",
        "garamond": "garamond",
        "cambria": "cambria",
        "candara": "candara",
        "franklin gothic": "franklingothic",
        "lucida": "lucida",
        "century gothic": "centurygothic",
    }
    for key, val in common_mappings.items():
        normalized = re.sub(r'[^a-z0-9]', '', key.lower())
        if normalized in installed:
            installed.add(re.sub(r'[^a-z0-9]', '', val.lower()))
            installed.add(val.lower())
            installed.add(key.lower())

    return installed


def is_font_available(font_name, installed_set):
    """Check if a font name matches any installed font."""
    if not font_name:
        return True

    name_lower = font_name.lower()
    normalized = re.sub(r'[^a-z0-9]', '', name_lower)

    if name_lower in installed_set:
        return True
    if normalized in installed_set:
        return True

    # Partial match: check if the main word is in any installed font
    words = re.findall(r'[a-z]+', name_lower)
    if words:
        main_word = words[0]
        if len(main_word) >= 4:
            for inst in installed_set:
                if main_word in inst:
                    return True

    return False


def find_best_fallback(font_name, installed_set):
    """Find the best available fallback for a missing font."""
    name_lower = font_name.lower()

    # Categorize the missing font
    serif_keywords = ["serif", "times", "georgia", "garamond", "palatino", "cambria", "book"]
    mono_keywords = ["mono", "courier", "consolas", "code", "terminal", "fixed"]
    display_keywords = ["display", "impact", "poster", "headline", "title"]

    is_serif = any(kw in name_lower for kw in serif_keywords)
    is_mono = any(kw in name_lower for kw in mono_keywords)
    is_display = any(kw in name_lower for kw in display_keywords)

    if is_mono:
        preferred = ["Consolas", "Courier New", "Lucida Console"]
    elif is_serif:
        preferred = ["Georgia", "Times New Roman", "Cambria", "Palatino Linotype"]
    elif is_display:
        preferred = ["Impact", "Arial Black", "Trebuchet MS", "Segoe UI"]
    else:
        preferred = ["Arial", "Segoe UI", "Calibri", "Verdana", "Tahoma"]

    for candidate in preferred:
        if is_font_available(candidate, installed_set):
            return candidate

    # Last resort
    for candidate in SAFE_FALLBACK_FONTS:
        if is_font_available(candidate, installed_set):
            return candidate

    return "Arial"


def apply_font_fallbacks(template_data, font_report, logger):
    """
    Update changeable elements with font fallback information.
    Returns a mapping of original font -> fallback font for modification.
    """
    fallback_map = {}

    for font_info in font_report.get("fonts", []):
        if not font_info["available"] and font_info["fallback"]:
            fallback_map[font_info["name"]] = font_info["fallback"]

    # Annotate elements with font status
    for elem in template_data.get("changeable_elements", []):
        if elem["type"] == "text":
            font = elem.get("font", "")
            if font in fallback_map:
                elem["font_available"] = False
                elem["font_fallback"] = fallback_map[font]
            else:
                elem["font_available"] = True
                elem["font_fallback"] = None

    return fallback_map