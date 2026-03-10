"""
MoFA Effect - Template Filler
Generates ExtendScript (.jsx) to modify the AEP template with AI-generated content.
"""

import os
import shutil

from config import TEMPLATES_DIR, OUTPUT_DIR


def generate_fill_script(aep_file_path, content_plan, generated_images,
                          voiceover_path, template_summary, logger):
    """
    Generate an ExtendScript that fills the AEP template with AI content.
    Also creates a working copy of the .aep file.
    
    Returns tuple: (jsx_file_path, modified_aep_path)
    """
    logger.section("Template Fill Script Generation")

    # Create a working copy of the AEP file
    aep_filename = os.path.basename(aep_file_path)
    aep_name, aep_ext = os.path.splitext(aep_filename)
    modified_aep_path = os.path.join(
        OUTPUT_DIR, f"{aep_name}_mofa_filled{aep_ext}"
    )

    logger.info(f"Creating working copy: {modified_aep_path}")
    shutil.copy2(aep_file_path, modified_aep_path)

    # Also copy any associated files in the same directory as the AEP
    # (AEP projects often reference files relative to their location)
    aep_dir = os.path.dirname(aep_file_path)
    modified_dir = os.path.dirname(modified_aep_path)

    # Copy the entire folder structure if the AEP is in a subfolder with assets
    copy_associated_assets(aep_dir, modified_dir, aep_filename, logger)

    # Build the ExtendScript
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
    """Copy files that might be referenced by the AEP template."""
    if source_dir == dest_dir:
        return

    try:
        for item in os.listdir(source_dir):
            if item == aep_filename:
                continue  # Already copied
            source_item = os.path.join(source_dir, item)
            dest_item = os.path.join(dest_dir, item)

            if os.path.isfile(source_item) and not os.path.exists(dest_item):
                # Copy common asset file types
                ext = os.path.splitext(item)[1].lower()
                asset_extensions = [
                    ".png", ".jpg", ".jpeg", ".tif", ".tiff",
                    ".psd", ".ai", ".mov", ".mp4", ".avi",
                    ".wav", ".mp3", ".aif", ".m4a", ".gif",
                    ".bmp", ".eps", ".svg"
                ]
                if ext in asset_extensions:
                    shutil.copy2(source_item, dest_item)
                    logger.info(f"  Copied associated asset: {item}")

            elif os.path.isdir(source_item):
                # Copy subdirectories (footage folders, etc.)
                if not os.path.exists(dest_item):
                    shutil.copytree(source_item, dest_item)
                    logger.info(f"  Copied associated folder: {item}")

    except Exception as e:
        logger.warning(f"Could not copy some associated assets: {str(e)}")


def build_fill_jsx(modified_aep_path, content_plan, generated_images,
                    voiceover_path, template_summary, logger):
    """Build the ExtendScript that modifies the AEP template."""

    # Prepare paths for JavaScript
    aep_path_js = modified_aep_path.replace("\\", "/")

    # Build text replacement commands
    text_commands = build_text_commands(content_plan, template_summary, logger)

    # Build image replacement commands
    image_commands = build_image_commands(
        generated_images, template_summary, logger
    )

    # Build audio import command
    audio_command = build_audio_command(
        voiceover_path, template_summary, logger
    )

    # Determine the main composition name
    main_comp_name = template_summary.get("main_comp_name", "")

    jsx = f"""// MoFA Effect - Template Fill Script
// Auto-generated. Modifies the AEP template with AI-generated content.

(function() {{
    // Open the project
    var projFile = new File("{aep_path_js}");
    if (!projFile.exists) {{
        alert("MoFA Effect Error: Project file not found.");
        return;
    }}

    app.open(projFile);
    var project = app.project;

    // Find the main composition
    var mainComp = null;
    var mainCompName = "{main_comp_name}";

    if (mainCompName && mainCompName.length > 0) {{
        // Try to find by name
        for (var i = 1; i <= project.numItems; i++) {{
            if (project.item(i) instanceof CompItem &&
                project.item(i).name === mainCompName) {{
                mainComp = project.item(i);
                break;
            }}
        }}
    }}

    if (!mainComp) {{
        // Fallback: use the longest composition
        var maxDuration = 0;
        for (var i = 1; i <= project.numItems; i++) {{
            if (project.item(i) instanceof CompItem) {{
                if (project.item(i).duration > maxDuration) {{
                    maxDuration = project.item(i).duration;
                    mainComp = project.item(i);
                }}
            }}
        }}
    }}

    if (!mainComp) {{
        alert("MoFA Effect Error: No composition found in project.");
        project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        return;
    }}

    // --- TEXT REPLACEMENTS ---
{text_commands}

    // --- IMAGE REPLACEMENTS ---
{image_commands}

    // --- AUDIO IMPORT ---
{audio_command}

    // Save the project
    project.save();

    // Close without additional save prompt
    // (project is already saved above)

}})();
"""
    return jsx


def build_text_commands(content_plan, template_summary, logger):
    """Build ExtendScript commands for text layer replacements."""
    text_replacements = content_plan.get("text_replacements", [])

    if not text_replacements:
        logger.info("No text replacements to apply.")
        return "    // No text replacements specified."

    commands = []
    commands.append("    // Replace text layers with AI-generated content")

    for tr in text_replacements:
        layer_name = tr.get("layer_name", "")
        layer_index = tr.get("layer_index", 0)
        new_text = tr.get("new_text", "")

        if not new_text:
            continue

        # Escape the text for JavaScript
        escaped_text = (
            new_text.replace("\\", "\\\\")
                     .replace('"', '\\"')
                     .replace("\n", "\\n")
                     .replace("\r", "")
        )
        escaped_name = layer_name.replace("\\", "\\\\").replace('"', '\\"')

        commands.append(f"""
    // Replace text: "{layer_name}"
    (function() {{
        var found = false;
        // Try by name first
        try {{
            for (var i = 1; i <= mainComp.numLayers; i++) {{
                var layer = mainComp.layer(i);
                if (layer instanceof TextLayer && layer.name === "{escaped_name}") {{
                    var textProp = layer.property("Source Text");
                    var textDoc = textProp.value;
                    textDoc.text = "{escaped_text}";
                    textProp.setValue(textDoc);
                    found = true;
                    break;
                }}
            }}
        }} catch(e) {{}}

        // If not found by name and we have an index, try by index
        if (!found && {layer_index} > 0) {{
            try {{
                var layer = mainComp.layer({layer_index});
                if (layer instanceof TextLayer) {{
                    var textProp = layer.property("Source Text");
                    var textDoc = textProp.value;
                    textDoc.text = "{escaped_text}";
                    textProp.setValue(textDoc);
                }}
            }} catch(e) {{}}
        }}

        // If still not found, search all compositions
        if (!found) {{
            try {{
                for (var c = 1; c <= project.numItems; c++) {{
                    if (project.item(c) instanceof CompItem) {{
                        var comp = project.item(c);
                        for (var j = 1; j <= comp.numLayers; j++) {{
                            var lyr = comp.layer(j);
                            if (lyr instanceof TextLayer && lyr.name === "{escaped_name}") {{
                                var tp = lyr.property("Source Text");
                                var td = tp.value;
                                td.text = "{escaped_text}";
                                tp.setValue(td);
                                break;
                            }}
                        }}
                    }}
                }}
            }} catch(e) {{}}
        }}
    }})();""")

        logger.info(f"  Text replacement: [{layer_name}] -> \"{new_text[:50]}...\"")

    return "\n".join(commands)


def build_image_commands(generated_images, template_summary, logger):
    """Build ExtendScript commands for image/footage replacements."""
    if not generated_images:
        logger.info("No image replacements to apply.")
        return "    // No image replacements specified."

    commands = []
    commands.append("    // Replace footage items with AI-generated images")

    for img in generated_images:
        img_path = img["path"].replace("\\", "/")
        layer_name = img.get("layer_name", "")
        layer_index = img.get("layer_index", 0)
        purpose = img.get("purpose", "general")

        escaped_name = layer_name.replace("\\", "\\\\").replace('"', '\\"')

        commands.append(f"""
    // Replace image: "{layer_name}" ({purpose})
    (function() {{
        var imgFile = new File("{img_path}");
        if (!imgFile.exists) return;

        var importOptions = new ImportOptions(imgFile);
        var newFootage = project.importFile(importOptions);

        // Try to find the layer and replace its source
        var found = false;

        // Search by layer name in main comp
        try {{
            for (var i = 1; i <= mainComp.numLayers; i++) {{
                var layer = mainComp.layer(i);
                if (layer.name === "{escaped_name}" && layer.source) {{
                    layer.replaceSource(newFootage, false);
                    found = true;
                    break;
                }}
            }}
        }} catch(e) {{}}

        // If not found by exact name, try partial match
        if (!found) {{
            try {{
                for (var i = 1; i <= mainComp.numLayers; i++) {{
                    var layer = mainComp.layer(i);
                    var lowerName = layer.name.toLowerCase();
                    var searchTerm = "{purpose}".toLowerCase();
                    if (layer.source && layer.source instanceof FootageItem &&
                        (lowerName.indexOf(searchTerm) >= 0 ||
                         lowerName.indexOf("logo") >= 0 ||
                         lowerName.indexOf("image") >= 0 ||
                         lowerName.indexOf("placeholder") >= 0 ||
                         lowerName.indexOf("photo") >= 0)) {{
                        layer.replaceSource(newFootage, false);
                        found = true;
                        break;
                    }}
                }}
            }} catch(e) {{}}
        }}

        // Also search all compositions
        if (!found) {{
            try {{
                for (var c = 1; c <= project.numItems; c++) {{
                    if (project.item(c) instanceof CompItem) {{
                        var comp = project.item(c);
                        for (var j = 1; j <= comp.numLayers; j++) {{
                            var lyr = comp.layer(j);
                            if (lyr.name === "{escaped_name}" && lyr.source) {{
                                lyr.replaceSource(newFootage, false);
                                found = true;
                                break;
                            }}
                        }}
                        if (found) break;
                    }}
                }}
            }} catch(e) {{}}
        }}
    }})();""")

        logger.info(f"  Image replacement: [{layer_name}] -> {os.path.basename(img['path'])}")

    return "\n".join(commands)


def build_audio_command(voiceover_path, template_summary, logger):
    """Build ExtendScript command to import and place voiceover audio."""
    if not voiceover_path:
        logger.info("No voiceover to import.")
        return "    // No voiceover audio to import."

    audio_path_js = voiceover_path.replace("\\", "/")

    command = f"""
    // Import and place voiceover audio
    (function() {{
        var audioFile = new File("{audio_path_js}");
        if (!audioFile.exists) return;

        try {{
            var importOptions = new ImportOptions(audioFile);
            var audioItem = project.importFile(importOptions);

            // Add audio layer to main composition
            var audioLayer = mainComp.layers.add(audioItem);
            audioLayer.startTime = 0;

            // If audio is longer than comp, trim it
            if (audioLayer.outPoint > mainComp.duration) {{
                audioLayer.outPoint = mainComp.duration;
            }}

            // Move audio layer to bottom of layer stack
            audioLayer.moveToEnd();
        }} catch(e) {{
            // Audio import failed, continue without it
        }}
    }})();"""

    logger.info(f"  Voiceover will be imported: {os.path.basename(voiceover_path)}")
    return command