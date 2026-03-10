"""
MoFA Effect - AEP Deep Introspection via ExtendScript
Generates and runs a .jsx script inside After Effects to extract
complete project structure.
"""

import os
import json
import subprocess
import time

from config import AERENDER_PATH, AE_TIMEOUT_SECONDS, TEMPLATES_DIR, OUTPUT_DIR
from utils import validate_file_exists


# The ExtendScript that runs inside After Effects to analyze the project.
# It opens the .aep, walks every composition and layer, and writes
# a JSON file with the complete structure.
INTROSPECT_JSX_TEMPLATE = r"""
// MoFA Effect - Template Introspection Script
// This script runs inside After Effects via aerender.
// It analyzes the project structure and writes results to a JSON file.

(function() {{
    var outputPath = "{output_json_path}";
    var projectPath = "{aep_file_path}";

    // Open the project
    var projFile = new File(projectPath);
    if (!projFile.exists) {{
        writeError("Project file not found: " + projectPath);
        return;
    }}

    app.open(projFile);
    var project = app.project;

    var result = {{
        "project_name": project.file ? project.file.name : "Unknown",
        "num_items": project.numItems,
        "compositions": [],
        "footage_items": [],
        "folder_structure": []
    }};

    // Walk all items in the project
    for (var i = 1; i <= project.numItems; i++) {{
        var item = project.item(i);

        if (item instanceof CompItem) {{
            var compData = analyzeComp(item);
            result.compositions.push(compData);
        }} else if (item instanceof FootageItem) {{
            var footageData = {{
                "name": item.name,
                "id": item.id,
                "width": item.width,
                "height": item.height,
                "duration": item.duration,
                "has_video": item.hasVideo,
                "has_audio": item.hasAudio,
                "file_path": (item.file) ? item.file.fsName : "none",
                "is_placeholder": (item.footageMissing || false)
            }};
            result.footage_items.push(footageData);
        }} else if (item instanceof FolderItem) {{
            result.folder_structure.push({{
                "name": item.name,
                "num_children": item.numItems
            }});
        }}
    }}

    // Write output
    var outFile = new File(outputPath);
    outFile.encoding = "UTF-8";
    outFile.open("w");
    outFile.write(jsonStringify(result));
    outFile.close();

    // Close project without saving
    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);

    function analyzeComp(comp) {{
        var compInfo = {{
            "name": comp.name,
            "id": comp.id,
            "duration": comp.duration,
            "frame_rate": comp.frameRate,
            "width": comp.width,
            "height": comp.height,
            "num_layers": comp.numLayers,
            "bg_color": [comp.bgColor[0], comp.bgColor[1], comp.bgColor[2]],
            "layers": []
        }};

        for (var j = 1; j <= comp.numLayers; j++) {{
            var layer = comp.layer(j);
            var layerInfo = {{
                "index": j,
                "name": layer.name,
                "type": getLayerType(layer),
                "enabled": layer.enabled,
                "in_point": layer.inPoint,
                "out_point": layer.outPoint,
                "start_time": layer.startTime,
                "has_video": layer.hasVideo,
                "has_audio": layer.hasAudio,
                "is_3d": layer.threeDLayer,
                "label_color": layer.label
            }};

            // Extract text content if it is a text layer
            if (layer instanceof TextLayer) {{
                try {{
                    var textProp = layer.property("Source Text");
                    var textDoc = textProp.value;
                    layerInfo.text_content = textDoc.text;
                    layerInfo.font = textDoc.font;
                    layerInfo.font_size = textDoc.fontSize;
                    layerInfo.fill_color = [
                        textDoc.fillColor[0],
                        textDoc.fillColor[1],
                        textDoc.fillColor[2]
                    ];
                    layerInfo.justification = textDoc.justification.toString();
                }} catch(e) {{
                    layerInfo.text_content = "[could not read]";
                }}
            }}

            // Extract source info if it is a footage layer
            if (layer.source && layer.source instanceof FootageItem) {{
                layerInfo.source_name = layer.source.name;
                layerInfo.source_file = (layer.source.file) ?
                    layer.source.file.fsName : "none";
                layerInfo.source_width = layer.source.width;
                layerInfo.source_height = layer.source.height;
                layerInfo.is_missing_footage = layer.source.footageMissing || false;
            }}

            // Check if layer is a precomp
            if (layer.source && layer.source instanceof CompItem) {{
                layerInfo.is_precomp = true;
                layerInfo.precomp_name = layer.source.name;
                layerInfo.precomp_duration = layer.source.duration;
            }}

            compInfo.layers.push(layerInfo);
        }}

        return compInfo;
    }}

    function getLayerType(layer) {{
        if (layer instanceof TextLayer) return "text";
        if (layer instanceof ShapeLayer) return "shape";
        if (layer instanceof CameraLayer) return "camera";
        if (layer instanceof LightLayer) return "light";
        if (layer.source) {{
            if (layer.source instanceof CompItem) return "precomp";
            if (layer.source.mainSource instanceof SolidSource) return "solid";
            if (layer.source.mainSource instanceof PlaceholderSource) return "placeholder";
            if (layer.source instanceof FootageItem) return "footage";
        }}
        if (layer.adjustmentLayer) return "adjustment";
        if (layer.nullLayer) return "null";
        return "unknown";
    }}

    function writeError(msg) {{
        var outFile = new File(outputPath);
        outFile.encoding = "UTF-8";
        outFile.open("w");
        outFile.write(jsonStringify({{"error": msg}}));
        outFile.close();
    }}

    // Simple JSON stringify since ExtendScript does not have JSON.stringify
    function jsonStringify(obj) {{
        if (obj === null) return "null";
        if (obj === undefined) return "null";
        var t = typeof obj;
        if (t === "number" || t === "boolean") return String(obj);
        if (t === "string") {{
            return '"' + obj.replace(/\\/g, '\\\\')
                             .replace(/"/g, '\\"')
                             .replace(/\n/g, '\\n')
                             .replace(/\r/g, '\\r')
                             .replace(/\t/g, '\\t') + '"';
        }}
        if (obj instanceof Array) {{
            var arrParts = [];
            for (var i = 0; i < obj.length; i++) {{
                arrParts.push(jsonStringify(obj[i]));
            }}
            return "[" + arrParts.join(",") + "]";
        }}
        if (t === "object") {{
            var objParts = [];
            for (var key in obj) {{
                if (obj.hasOwnProperty(key)) {{
                    objParts.push('"' + key + '":' + jsonStringify(obj[key]));
                }}
            }}
            return "{{" + objParts.join(",") + "}}";
        }}
        return '""';
    }}
}})();
"""


def generate_introspect_script(aep_file_path, output_json_path):
    """Generate the ExtendScript (.jsx) content for template analysis."""
    # Normalize paths for JavaScript (forward slashes)
    aep_path_js = aep_file_path.replace("\\", "/")
    out_path_js = output_json_path.replace("\\", "/")

    jsx_content = INTROSPECT_JSX_TEMPLATE.format(
        aep_file_path=aep_path_js,
        output_json_path=out_path_js
    )
    return jsx_content


def run_introspection(aep_file_path, logger):
    """
    Run deep introspection on an .aep file using After Effects.
    Returns the parsed project structure as a dictionary.
    """
    logger.section("AEP Deep Introspection (ExtendScript)")

    # Validate aerender exists
    if not validate_file_exists(AERENDER_PATH, "aerender.exe"):
        logger.error(
            f"aerender.exe not found at: {AERENDER_PATH}\n"
            "Please verify your After Effects installation path in config.py"
        )
        return None

    # Validate AEP file exists
    if not validate_file_exists(aep_file_path, "AEP template"):
        return None

    # Set up paths
    output_json_path = os.path.join(OUTPUT_DIR, "template_analysis.json")
    jsx_file_path = os.path.join(TEMPLATES_DIR, "introspect_generated.jsx")

    # Generate the ExtendScript
    jsx_content = generate_introspect_script(aep_file_path, output_json_path)

    # Write the .jsx file
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    with open(jsx_file_path, "w", encoding="utf-8") as f:
        f.write(jsx_content)
    logger.info(f"Generated introspection script: {jsx_file_path}")

    # Remove old output if exists
    if os.path.exists(output_json_path):
        os.remove(output_json_path)

    # Build aerender command to run the script
    # -r flag runs a script, -s flag is for running scripts in some versions
    # We use AfterFX.exe directly for script execution since aerender
    # is primarily for rendering, not script execution.
    # The approach: use aerender with -r to run the script
    afterfx_path = os.path.join(
        os.path.dirname(AERENDER_PATH), "AfterFX.exe"
    )

    # Try AfterFX.exe first (more reliable for script execution)
    if os.path.isfile(afterfx_path):
        cmd = [afterfx_path, "-r", jsx_file_path]
        logger.info(f"Running introspection via AfterFX.exe")
    else:
        # Fallback: use aerender with -r flag
        cmd = [AERENDER_PATH, "-r", jsx_file_path]
        logger.info(f"Running introspection via aerender.exe")

    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("Waiting for After Effects to analyze the template...")
    logger.info("(This may take 30-60 seconds as AE starts up)")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )

        # Wait with timeout
        stdout, stderr = process.communicate(timeout=AE_TIMEOUT_SECONDS)

        if stdout:
            logger.info(f"AE stdout: {stdout.decode('utf-8', errors='replace')[:500]}")
        if stderr:
            logger.warning(f"AE stderr: {stderr.decode('utf-8', errors='replace')[:500]}")

    except subprocess.TimeoutExpired:
        process.kill()
        logger.error(f"After Effects timed out after {AE_TIMEOUT_SECONDS} seconds.")
        return None
    except Exception as e:
        logger.error(f"Error running After Effects: {str(e)}")
        return None

    # Wait a moment for file to be written
    time.sleep(2)

    # Check if output was generated
    if not os.path.isfile(output_json_path):
        logger.warning(
            "ExtendScript introspection did not produce output. "
            "This can happen if After Effects requires user interaction "
            "(license dialog, update prompt, etc.). "
            "Falling back to binary parser results."
        )
        return None

    # Parse the output
    try:
        with open(output_json_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Handle potential BOM
            if content.startswith('\ufeff'):
                content = content[1:]
            analysis = json.loads(content)

        if "error" in analysis:
            logger.error(f"ExtendScript reported error: {analysis['error']}")
            return None

        logger.info("Template analysis completed successfully.")
        logger.info(f"Project: {analysis.get('project_name', 'Unknown')}")
        logger.info(f"Compositions found: {len(analysis.get('compositions', []))}")
        logger.info(f"Footage items found: {len(analysis.get('footage_items', []))}")

        # Log composition details
        for comp in analysis.get("compositions", []):
            logger.info(
                f"  Composition: {comp['name']} | "
                f"{comp['width']}x{comp['height']} | "
                f"{comp['duration']:.1f}s | "
                f"{comp['frame_rate']}fps | "
                f"{comp['num_layers']} layers"
            )
            for layer in comp.get("layers", []):
                layer_desc = f"    Layer {layer['index']}: [{layer['type']}] {layer['name']}"
                if layer.get("text_content"):
                    layer_desc += f" -> \"{layer['text_content']}\""
                if layer.get("source_file") and layer["source_file"] != "none":
                    layer_desc += f" -> {layer['source_file']}"
                logger.info(layer_desc)

        return analysis

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse introspection output: {str(e)}")
        logger.error(f"Raw content: {content[:500]}")
        return None
    except Exception as e:
        logger.error(f"Error reading introspection output: {str(e)}")
        return None


def build_template_summary(analysis, binary_info, user_description, logger):
    """
    Build a clean summary of the template for the AI content generator.
    Combines ExtendScript analysis with binary parser results and user input.
    """
    logger.section("Building Template Summary")

    summary = {
        "description": user_description,
        "source": "unknown",
        "duration": 0,
        "width": 0,
        "height": 0,
        "frame_rate": 0,
        "compositions": [],
        "replaceable_text_layers": [],
        "replaceable_image_layers": [],
        "artistic_layers": [],
        "total_layers": 0,
        "has_audio": False
    }

    if analysis:
        summary["source"] = "extendscript"
        # Use the first (main) composition, or find the longest one
        comps = analysis.get("compositions", [])
        if comps:
            # Find main comp (usually the longest or the first one)
            main_comp = max(comps, key=lambda c: c.get("duration", 0))
            summary["duration"] = main_comp.get("duration", 0)
            summary["width"] = main_comp.get("width", 1920)
            summary["height"] = main_comp.get("height", 1080)
            summary["frame_rate"] = main_comp.get("frame_rate", 30)
            summary["main_comp_name"] = main_comp.get("name", "")
            summary["total_layers"] = main_comp.get("num_layers", 0)

            for comp in comps:
                comp_summary = {
                    "name": comp["name"],
                    "duration": comp["duration"],
                    "layers_count": comp["num_layers"]
                }
                summary["compositions"].append(comp_summary)

            # Categorize layers
            for layer in main_comp.get("layers", []):
                layer_type = layer.get("type", "unknown")

                if layer_type == "text":
                    summary["replaceable_text_layers"].append({
                        "name": layer["name"],
                        "index": layer["index"],
                        "current_text": layer.get("text_content", ""),
                        "font": layer.get("font", ""),
                        "font_size": layer.get("font_size", 0)
                    })
                elif layer_type == "footage":
                    is_replaceable = True
                    source_file = layer.get("source_file", "none")
                    # Footage with missing files or placeholder names are replaceable
                    summary["replaceable_image_layers"].append({
                        "name": layer["name"],
                        "index": layer["index"],
                        "source_name": layer.get("source_name", ""),
                        "source_file": source_file,
                        "width": layer.get("source_width", 0),
                        "height": layer.get("source_height", 0),
                        "is_missing": layer.get("is_missing_footage", False)
                    })
                elif layer_type == "precomp":
                    summary["artistic_layers"].append({
                        "name": layer["name"],
                        "type": "precomp",
                        "index": layer["index"]
                    })
                else:
                    summary["artistic_layers"].append({
                        "name": layer["name"],
                        "type": layer_type,
                        "index": layer["index"]
                    })

                if layer.get("has_audio"):
                    summary["has_audio"] = True

    elif binary_info and binary_info.get("valid"):
        summary["source"] = "binary_parser"
        # Use binary parser data as fallback
        summary["possible_layers"] = binary_info.get("possible_layer_names", [])
        summary["possible_text"] = binary_info.get("possible_text_content", [])
        summary["possible_footage"] = binary_info.get("possible_footage_refs", [])

    logger.info(f"Template summary built from: {summary['source']}")
    logger.info(f"Duration: {summary['duration']:.1f}s")
    logger.info(f"Resolution: {summary['width']}x{summary['height']}")
    logger.info(f"Replaceable text layers: {len(summary['replaceable_text_layers'])}")
    logger.info(f"Replaceable image layers: {len(summary['replaceable_image_layers'])}")
    logger.info(f"Artistic layers (preserved): {len(summary['artistic_layers'])}")

    return summary