"""
MoFA Effect - AEP Binary Parser
Reads .aep files at the binary level to extract structural information.
This provides a first-pass analysis before ExtendScript deep introspection.
"""

import os
import struct
import re


def parse_aep_binary(filepath, logger):
    """
    Parse an .aep file at the binary level.
    Extracts readable strings, validates format, and finds metadata.
    
    Returns a dictionary with extracted information.
    """
    logger.section("AEP Binary Parser")

    result = {
        "valid": False,
        "file_size_mb": 0,
        "format": None,
        "strings_found": [],
        "possible_layer_names": [],
        "possible_comp_names": [],
        "possible_footage_refs": [],
        "possible_text_content": [],
        "raw_metadata": {}
    }

    if not os.path.isfile(filepath):
        logger.error(f"File not found: {filepath}")
        return result

    file_size = os.path.getsize(filepath)
    result["file_size_mb"] = round(file_size / (1024 * 1024), 2)
    logger.info(f"File size: {result['file_size_mb']} MB")

    try:
        with open(filepath, "rb") as f:
            header = f.read(12)

            if len(header) < 12:
                logger.error("File too small to be a valid AEP file.")
                return result

            # Check for RIFX header (After Effects uses big-endian RIFF)
            magic = header[0:4]
            container_type = header[8:12]

            if magic == b"RIFX":
                result["format"] = "RIFX (After Effects Project)"
                result["valid"] = True
                logger.info("Valid AEP file detected (RIFX format).")
            elif magic == b"RIFF":
                result["format"] = "RIFF (possibly older AE format)"
                result["valid"] = True
                logger.info("RIFF format detected. Possibly older AE version.")
            else:
                magic_str = magic.decode("ascii", errors="replace")
                logger.warning(
                    f"Unexpected header: {magic_str}. "
                    "File may not be a standard AEP project."
                )
                # Still try to parse -- some AEP files have variant headers
                result["valid"] = True

            result["raw_metadata"]["header_magic"] = magic.decode("ascii", errors="replace")
            result["raw_metadata"]["container_type"] = container_type.decode("ascii", errors="replace")

            # Read entire file for string extraction
            f.seek(0)
            raw_data = f.read()

        # Extract readable ASCII strings (minimum length 4)
        ascii_strings = extract_ascii_strings(raw_data, min_length=4)
        result["strings_found"] = ascii_strings
        logger.info(f"Extracted {len(ascii_strings)} readable strings from binary.")

        # Extract UTF-16 strings (AE often stores text in UTF-16)
        utf16_strings = extract_utf16_strings(raw_data, min_length=3)
        logger.info(f"Extracted {len(utf16_strings)} UTF-16 strings from binary.")

        # Categorize strings
        categorize_strings(result, ascii_strings + utf16_strings, logger)

    except Exception as e:
        logger.error(f"Error parsing AEP file: {str(e)}")

    return result


def extract_ascii_strings(data, min_length=4):
    """Extract readable ASCII strings from binary data."""
    pattern = re.compile(
        rb'[\x20-\x7e]{' + str(min_length).encode() + rb',}'
    )
    matches = pattern.findall(data)
    strings = []
    seen = set()
    for m in matches:
        try:
            s = m.decode("ascii").strip()
            if s and s not in seen and not is_noise_string(s):
                seen.add(s)
                strings.append(s)
        except Exception:
            pass
    return strings


def extract_utf16_strings(data, min_length=3):
    """Extract UTF-16LE encoded strings from binary data."""
    strings = []
    seen = set()
    # Look for UTF-16LE patterns (ASCII char followed by null byte)
    pattern = re.compile(rb'(?:[\x20-\x7e]\x00){' + str(min_length).encode() + rb',}')
    matches = pattern.findall(data)
    for m in matches:
        try:
            s = m.decode("utf-16-le").strip()
            if s and s not in seen and not is_noise_string(s) and len(s) >= min_length:
                seen.add(s)
                strings.append(s)
        except Exception:
            pass
    return strings


def is_noise_string(s):
    """Filter out strings that are clearly internal AE data, not content."""
    noise_patterns = [
        "ADBE", "ADBK", "tdgp", "tdbs", "cdta", "ldta", "sspc",
        "opti", "GEst", "btdk", "otda", "ppSn", "fiin",
        "CMM ", "XYZ ", "desc", "wtpt", "bkpt", "rTRC",
        "gTRC", "bTRC", "cprt", "chad",
    ]
    if len(s) <= 4 and s.upper() in [p.upper() for p in noise_patterns]:
        return True
    if all(c in "0123456789abcdefABCDEF-" for c in s):
        return True
    if len(s) > 200:
        return True
    return False


def categorize_strings(result, strings, logger):
    """Categorize extracted strings into likely layer names, comps, etc."""
    layer_keywords = [
        "layer", "text", "logo", "background", "bg", "title",
        "subtitle", "headline", "image", "photo", "footage",
        "video", "shape", "null", "adjustment", "solid",
        "placeholder", "comp", "scene", "intro", "outro",
        "overlay", "particle", "effect", "color", "mask",
        "precomp", "main", "final"
    ]

    footage_extensions = [
        ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".psd",
        ".ai", ".mov", ".mp4", ".avi", ".wav", ".mp3",
        ".aif", ".m4a"
    ]

    for s in strings:
        s_lower = s.lower()

        # Check for footage references
        if any(s_lower.endswith(ext) for ext in footage_extensions):
            result["possible_footage_refs"].append(s)
            continue

        # Check for file paths
        if "\\" in s or "/" in s:
            if any(ext in s_lower for ext in footage_extensions):
                result["possible_footage_refs"].append(s)
            continue

        # Check for likely layer/comp names
        if any(keyword in s_lower for keyword in layer_keywords):
            if len(s) < 80:
                result["possible_layer_names"].append(s)
            continue

        # Check for likely text content (readable sentences/phrases)
        if (len(s) > 5 and " " in s and
                any(c.isalpha() for c in s) and
                not s.startswith("{")):
            result["possible_text_content"].append(s)

    # Remove duplicates while preserving order
    result["possible_layer_names"] = list(dict.fromkeys(result["possible_layer_names"]))
    result["possible_footage_refs"] = list(dict.fromkeys(result["possible_footage_refs"]))
    result["possible_text_content"] = list(dict.fromkeys(result["possible_text_content"]))

    logger.info(f"Possible layer names found: {len(result['possible_layer_names'])}")
    logger.info(f"Possible footage references: {len(result['possible_footage_refs'])}")
    logger.info(f"Possible text content: {len(result['possible_text_content'])}")

    # Log what we found
    if result["possible_layer_names"]:
        logger.info("Layer names detected:")
        for name in result["possible_layer_names"][:20]:
            logger.info(f"  - {name}")

    if result["possible_footage_refs"]:
        logger.info("Footage references detected:")
        for ref in result["possible_footage_refs"][:10]:
            logger.info(f"  - {ref}")