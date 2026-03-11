# Internal-Project-1

## Overview
Internal-Project-1 is an AI-powered video generation tool that uses After Effects templates to create custom videos. It automates the process of filling video templates with AI-generated content, including text, images, and voiceover, and renders the final video.

## Workflow
1. **Template Analysis**: Analyzes the provided After Effects (.aep) template to extract its structure and editable layers.
2. **AI Content Generation**: Uses an AI model (Groq API) to generate a content plan based on the template and user creative brief. This includes:
	- Text replacements
	- Image generation prompts
	- Voiceover script
3. **Asset Generation**:
	- Generates images using free AI image APIs
	- Creates voiceover audio using Edge-TTS
4. **Template Filling**: Fills the template with generated assets using ExtendScript (.jsx) and After Effects.
5. **Rendering**: Renders the modified template to a final video file (MP4).

## Main Scripts
- `main.py`: Entry point. Handles user input, coordinates the workflow, and manages logging.
- `aep_introspect.py`: Analyzes After Effects templates to extract structure and editable layers.
- `ai_script_generator.py`: Generates content plans using Groq API.
- `image_generator.py`: Generates images from AI prompts.
- `voice_generator.py`: Generates voiceover audio.
- `template_filler.py`: Creates scripts to fill templates with AI content.
- `render_engine.py`: Handles rendering and video conversion.
- `utils.py`: Helper functions and logging.
- `config.py`: Configuration settings and paths.

## Requirements
Install dependencies with:
```
pip install -r requirements.txt
```
Required packages:
- edge-tts
- imageio-ffmpeg
- requests
- pillow

## Usage
1. Run `python main.py`.
2. Follow prompts to provide:
	- After Effects template path (.aep)
	- Groq API key
	- Template description
	- Creative brief
3. The tool will generate assets, fill the template, and render the final video.

## Notes
- Requires After Effects and `aerender.exe`/`AfterFX.exe` for script execution and rendering.
- Output files and logs are saved in the `OUTPUT_DIR` specified in `config.py`.
- Example templates are in the `downloads/` folder.

---
For questions or issues, check the logs or review the code for troubleshooting.
