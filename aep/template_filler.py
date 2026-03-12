"""
MoFA Effect - Template Filler
Generates ExtendScript (.jsx) to modify the AEP template with AI-generated content.
"""

import os
import shutil
import time

from config import TEMPLATES_DIR, OUTPUT_DIR


def generate_fill_script(aep_file_path, content_plan, generated_images,
                          voiceover_path, template_summary, logger):
    """Generate an ExtendScript that fills the AEP template with AI content."""
    logger.section("Template Fill Script Generation")

    aep_filename = os.path.basename(aep_file_path)
    aep_name, aep_ext = os.path.splitext(aep_filename)

    timestamp = int(time.time())
    modified_aep_path = os.path.join(OUTPUT_DIR, f"{aep_name}_mofa_{timestamp}{aep_ext}")

    logger.info(f"Creating working copy: {modified_aep_path}")
    shutil.copy2(aep_file_path, modified_aep_path)

    aep_dir = os.path.dirname(aep_file_path)
    modified_dir = os.path.dirname(modified_aep_path)
    copy_associated_assets(aep_dir, modified_dir, aep_filename, logger)

    jsx_content = build_fill_jsx(
        modified_aep_path, content_plan, generated_images,
        voiceover_path, template_summary, logger
    )

    jsx_file_path = os.path.join(TEMPLATES_DIR, "fill_template.jsx")

    with open(jsx_file_path, "w", encoding="utf-8") as f:
        f.write(jsx_content)

    logger.info(f"Fill script generated: {jsx_file_path}")
    return jsx_file_path, modified_aep_path


def copy_associated_assets(source_dir, dest_dir, aep_filename, logger):
    """Copy associated assets."""
    if source_dir == dest_dir:
        return

    try:
        for item in os.listdir(source_dir):
            if item == aep_filename:
                continue
            source_item = os.path.join(source_dir, item)
            dest_item = os.path.join(dest_dir, item)

            if os.path.isfile(source_item) and not os.path.exists(dest_item):
                ext = os.path.splitext(item)[1].lower()
                asset_extensions = [
                    ".png", ".jpg", ".jpeg", ".tif", ".psd", ".ai",
                    ".mov", ".mp4", ".wav", ".mp3"
                ]
                if ext in asset_extensions:
                    shutil.copy2(source_item, dest_item)
                    logger.info(f"  Copied: {item}")
            elif os.path.isdir(source_item) and not os.path.exists(dest_item):
                shutil.copytree(source_item, dest_item)
                logger.info(f"  Copied folder: {item}")
    except Exception as e:
        logger.warning(f"Asset copy error: {str(e)}")


def build_fill_jsx(modified_aep_path, content_plan, generated_images,
                    voiceover_path, template_summary, logger):
    """Build the ExtendScript with fixed image replacement."""

    aep_path_js = modified_aep_path.replace("\\", "/")
    debug_log_path = os.path.join(OUTPUT_DIR, "jsx_debug.log").replace("\\", "/")

    text_commands = build_text_commands(content_plan, logger)
    image_commands = build_image_commands(generated_images, logger)
    audio_command = build_audio_command(voiceover_path, logger)

    jsx = f"""// MoFA Effect - Template Fill Script
(function() {{
    var debugLog = [];

    function log(msg) {{
        debugLog.push(msg);
    }}

    function saveLog() {{
        var logFile = new File("{debug_log_path}");
        logFile.open("w");
        logFile.write(debugLog.join("\\n"));
        logFile.close();
    }}

    try {{
        log("=== MoFA Effect Fill Script Started ===");
        log("Timestamp: " + new Date().toString());

        var projFile = new File("{aep_path_js}");
        if (!projFile.exists) {{
            log("ERROR: Project file not found: {aep_path_js}");
            saveLog();
            return;
        }}
        log("Project file found: " + projFile.fsName);

        app.open(projFile);
        var project = app.project;
        log("Project opened successfully");
        log("Total items in project: " + project.numItems);

        // Log all items
        for (var i = 1; i <= project.numItems; i++) {{
            var item = project.item(i);
            var itemType = "Unknown";
            if (item instanceof CompItem) itemType = "CompItem";
            else if (item instanceof FootageItem) itemType = "FootageItem";
            else if (item instanceof FolderItem) itemType = "FolderItem";
            log("Item " + i + ": " + item.name + " (" + itemType + ")");
        }}

        // Find Main Comp
        var mainComp = null;
        for (var i = 1; i <= project.numItems; i++) {{
            if (project.item(i) instanceof CompItem && project.item(i).name === "Main Comp") {{
                mainComp = project.item(i);
                log("Found Main Comp at index " + i);
                break;
            }}
        }}

        if (!mainComp) {{
            log("ERROR: Main Comp not found. Trying longest comp...");
            var maxDur = 0;
            for (var i = 1; i <= project.numItems; i++) {{
                if (project.item(i) instanceof CompItem && project.item(i).duration > maxDur) {{
                    maxDur = project.item(i).duration;
                    mainComp = project.item(i);
                }}
            }}
            if (mainComp) {{
                log("Using comp: " + mainComp.name + " (duration: " + mainComp.duration + ")");
            }} else {{
                log("FATAL: No compositions found at all");
                saveLog();
                return;
            }}
        }}

        log("Main Comp: " + mainComp.name);
        log("  Duration: " + mainComp.duration + "s");
        log("  Size: " + mainComp.width + "x" + mainComp.height);
        log("  Layers: " + mainComp.numLayers);

        for (var i = 1; i <= mainComp.numLayers; i++) {{
            var layer = mainComp.layer(i);
            var lType = "Unknown";
            if (layer instanceof TextLayer) lType = "TextLayer";
            else if (layer instanceof ShapeLayer) lType = "ShapeLayer";
            else if (layer instanceof AVLayer) lType = "AVLayer";
            log("  Layer " + i + ": " + layer.name + " (" + lType + ")");
        }}

{text_commands}
{image_commands}
{audio_command}

        log("=== Saving Project ===");
        project.save();
        log("Project saved to: " + project.file.fsName);
        log("=== Script Completed Successfully ===");
        saveLog();

    }} catch(e) {{
        log("FATAL ERROR: " + e.toString());
        if (e.line) log("Line: " + e.line);
        saveLog();
    }}
}})();
"""
    return jsx


def build_text_commands(content_plan, logger):
    """Build text replacement commands."""
    text_replacements = content_plan.get("text_replacements", [])

    if not text_replacements:
        return '    log("No text replacements specified");'

    website = ""
    for tr in text_replacements:
        layer_name = tr.get("layer_name", "").lower()
        new_text = tr.get("new_text", "")
        if "website" in layer_name or "url" in layer_name or "web" in layer_name:
            website = new_text

    if not website and len(text_replacements) > 1:
        website = text_replacements[1].get("new_text", "")

    if not website:
        website = "example.com"

    escaped_website = website.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    logger.info(f"  Text: [Text_01] -> \"{website}\"")

    return f'''
    log("=== TEXT REPLACEMENT ===");
    try {{
        var textFound = false;
        for (var i = 1; i <= mainComp.numLayers; i++) {{
            var layer = mainComp.layer(i);
            if (layer.name === "Text_01") {{
                log("Found Text_01 at layer " + i);

                var textProp = null;
                try {{
                    textProp = layer.property("ADBE Text Properties").property("ADBE Text Document");
                }} catch(e1) {{
                    log("ADBE path failed, trying Source Text...");
                    try {{
                        textProp = layer.property("Source Text");
                    }} catch(e2) {{
                        log("Source Text also failed: " + e2.toString());
                    }}
                }}

                if (textProp) {{
                    var textDoc = textProp.value;
                    log("Current text: " + textDoc.text);
                    textDoc.text = "{escaped_website}";
                    textProp.setValue(textDoc);
                    var verify = textProp.value;
                    log("New text: " + verify.text);
                    textFound = true;
                }} else {{
                    log("ERROR: Could not access text property");
                }}
                break;
            }}
        }}
        if (!textFound) {{
            log("WARNING: Text_01 not found or text not changed");
        }}
    }} catch(e) {{
        log("ERROR in text replacement: " + e.toString());
    }}
'''


def build_image_commands(generated_images, logger):
    """Build image replacement using File object."""
    if not generated_images:
        logger.info("  No images - keeping template default")
        return '    log("No images to replace");'

    img = generated_images[0]
    img_path = img["path"].replace("\\", "/")
    logger.info(f"  Logo: {os.path.basename(img['path'])}")

    return f'''
    log("=== IMAGE REPLACEMENT ===");
    log("Logo file: {img_path}");
    try {{
        var logoFile = new File("{img_path}");
        log("File exists: " + logoFile.exists);

        if (!logoFile.exists) {{
            log("ERROR: Logo file not found");
        }} else {{
            var replaced = false;

            // Method 1: Search top-level project items
            log("Searching top-level items...");
            for (var i = 1; i <= project.numItems; i++) {{
                var item = project.item(i);
                if (item instanceof FootageItem && item.name.indexOf("Multi Color") >= 0) {{
                    log("Found footage: " + item.name + " at index " + i);
                    item.replace(logoFile);
                    log("Replaced successfully via top-level search");
                    replaced = true;
                    break;
                }}
            }}

            // Method 2: Search inside ALL folders recursively
            if (!replaced) {{
                log("Not found at top level. Searching folders...");
                for (var i = 1; i <= project.numItems; i++) {{
                    var item = project.item(i);
                    if (item instanceof FolderItem) {{
                        log("Checking folder: " + item.name + " (" + item.numItems + " items)");
                        for (var j = 1; j <= item.numItems; j++) {{
                            var sub = item.item(j);
                            if (sub instanceof FootageItem) {{
                                log("  Footage in folder: " + sub.name);
                                if (sub.name.indexOf("Multi Color") >= 0) {{
                                    log("  Found it! Replacing...");
                                    sub.replace(logoFile);
                                    log("  Replaced successfully via folder search");
                                    replaced = true;
                                    break;
                                }}
                            }}
                            // Check sub-folders too
                            if (sub instanceof FolderItem) {{
                                log("  Sub-folder: " + sub.name + " (" + sub.numItems + " items)");
                                for (var k = 1; k <= sub.numItems; k++) {{
                                    var subsub = sub.item(k);
                                    if (subsub instanceof FootageItem) {{
                                        log("    Footage: " + subsub.name);
                                        if (subsub.name.indexOf("Multi Color") >= 0) {{
                                            log("    Found it! Replacing...");
                                            subsub.replace(logoFile);
                                            log("    Replaced successfully via sub-folder");
                                            replaced = true;
                                            break;
                                        }}
                                    }}
                                }}
                                if (replaced) break;
                            }}
                        }}
                        if (replaced) break;
                    }}
                }}
            }}

            // Method 3: Find the layer in Your Logo Here comp and replace its source
            if (!replaced) {{
                log("Folder search failed. Trying comp layer replacement...");
                for (var i = 1; i <= project.numItems; i++) {{
                    if (project.item(i) instanceof CompItem && project.item(i).name === "Your Logo Here") {{
                        var logoComp = project.item(i);
                        log("Found Your Logo Here comp with " + logoComp.numLayers + " layers");
                        for (var j = 1; j <= logoComp.numLayers; j++) {{
                            var lyr = logoComp.layer(j);
                            log("  Layer: " + lyr.name);
                            if (lyr.source && lyr.source instanceof FootageItem) {{
                                log("  Has footage source: " + lyr.source.name);
                                lyr.source.replace(logoFile);
                                log("  Replaced via comp layer source!");
                                replaced = true;
                                break;
                            }}
                        }}
                        break;
                    }}
                }}
            }}

            if (!replaced) {{
                log("WARNING: Could not replace logo through any method");
                log("Listing all project items with types:");
                for (var i = 1; i <= project.numItems; i++) {{
                    var it = project.item(i);
                    var tp = "unknown";
                    if (it instanceof CompItem) tp = "Comp";
                    else if (it instanceof FootageItem) tp = "Footage";
                    else if (it instanceof FolderItem) tp = "Folder";
                    log("  " + i + ": [" + tp + "] " + it.name);
                }}
            }}
        }}
    }} catch(e) {{
        log("ERROR in image replacement: " + e.toString());
        if (e.line) log("Line: " + e.line);
    }}
'''


def build_audio_command(voiceover_path, logger):
    """Build audio import command."""
    if not voiceover_path:
        return '    log("No voiceover to import");'

    audio_path_js = voiceover_path.replace("\\", "/")
    logger.info(f"  Audio: {os.path.basename(voiceover_path)}")

    return f'''
    log("=== AUDIO IMPORT ===");
    try {{
        var audioFile = new File("{audio_path_js}");
        log("Audio file exists: " + audioFile.exists);

        if (!audioFile.exists) {{
            log("ERROR: Audio file not found");
        }} else {{
            var importOptions = new ImportOptions(audioFile);
            var audioItem = project.importFile(importOptions);
            log("Audio imported: " + audioItem.name);
            var audioLayer = mainComp.layers.add(audioItem);
            audioLayer.moveToEnd();
            log("Audio layer added and moved to end");
        }}
    }} catch(e) {{
        log("ERROR in audio import: " + e.toString());
    }}
'''