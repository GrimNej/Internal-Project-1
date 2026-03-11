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
	- Generates images using AI image APIs (Model Yet to be Decided)
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

## Architecture

1. Originally Proposed (Legacy):

<img width="1376" height="768" alt="image" src="https://github.com/user-attachments/assets/78af53ea-a8ce-47f8-8892-f11b9a8fddb0" />

---

2. New Improved (Currently used) v0.0.1:

<img width="1408" height="768" alt="Pipeline whole" src="https://github.com/user-attachments/assets/8ce1d7b0-8a46-4e34-91d9-28fbbf1533a9" />

>Note: The first half of the architecture (Remix Engine in the Originally Proposed Architecture) stays the SAME for now. The changes and improvements are only being done to the (Videolizer) part.

---

3. Future Scaling:

<img width="1408" height="768" alt="Future scale hypothetical" src="https://github.com/user-attachments/assets/c50971dd-623b-485c-88c1-7897c65b04c3" />

>References: Links to examples to all the above mentioned extensions are listed below:

### .aep file (Adobe After Effects):
- An .aep file is a binary project format used by Adobe After Effects to store motion graphics and visual effects data. Rather than containing actual video footage, it acts as a metadata blueprint that saves references to external media, layer structures, keyframes, and effect settings. Because it is a project file and not a rendered video, it requires After Effects to open and must be exported (rendered) into a format like .mp4 before it can be viewed by anyone without the software.

>Example link 1: https://ae-share.com/animation-text-after-effects-videohive-57643770.html

>Example link 2: https://mixkit.co/free-after-effects-templates/splash-logo-reveal-565/



### .blend (Blender):
- A .blend file is the native project format for Blender, an open-source suite used for 3D modeling, animation, and motion graphics. Unlike most creative files, it is "packed," meaning it can optionally store all textures, sounds, and fonts directly inside a single file to prevent broken links when sharing. It contains the entire scene hierarchy—including 3D geometry, lighting rigs, and physics simulations—but requires the Blender software to open and a render process to convert the 3D data into a viewable 2D video or image.

>Example link 1: https://www.blenderkit.com/get-blenderkit/4b3ecd65-097e-4ff1-9a77-7f6612b1a617/

>Example link 2: https://www.blenderkit.com/get-blenderkit/3c421f61-f360-46be-b6af-833fc10f12d5/

### .lottie (JSON):
- A .lottie file is a JSON-based animation file format that allows designers to ship high-quality animations on any platform as easily as shipping static assets. It works by exporting skeletal animation data as code, which is then rendered in real-time by a mobile or web player rather than being played back as a pre-rendered video. This results in incredibly small file sizes and infinite scalability without pixelation, making it the industry standard for interactive UI elements, app onboarding screens, and lightweight web graphics.

>Example link 1: https://www.lottielab.com/template/bento-blocks-search-card

>Example link 2: https://www.lottielab.com/template/bento-blocks-status-card

### .drp / .comp (Davinci Resolve)
- A .drp (DaVinci Resolve Project) is a proprietary database file that contains the entire "instruction manual" for a video project, including timelines, color grading nodes, and audio configurations. Unlike a video file, it does not contain any actual media; it only stores the mathematical data and paths used to assemble your footage.
- A .comp (Fusion Composition) is a specialized sub-format used specifically for advanced visual effects and node-based motion graphics within the Resolve ecosystem, allowing for complex layering and 2D/3D compositing that must be rendered out to a standard video format to be viewed by anyone without the software.

>Example link 1: https://mixkit.co/free-davinci-resolve-templates/video-drop-story-704/

>Example link 2: https://mixkit.co/free-davinci-resolve-templates/gradient-shape-animation-story-705/

### .natron (Natron): 
- A .ntp (Natron Project) file is the native project format for Natron, an open-source, node-based compositing software used for visual effects and motion graphics. Similar to other professional project files, it functions as a procedural map that records every node, link, and parameter adjustment without containing any actual video or image data itself. It stores the logic for tasks like rotoscoping, keying, and tracking, but the project must be processed through a "Write" node to render the final composition into a viewable video or image sequence.

>Example link 1: https://www.behance.net/gallery/210944049/portfolio-2025-graphic-designer

>Example link 2: https://www.behance.net/gallery/244739993/Creative-Portfolio-2026_Muh-Yasin

### .synfig (Synfig Project):
- A .sif or .sifz (Synfig Project) file is the native format for Synfig Studio, an open-source, vector-based 2D animation software. It stores a non-destructive mathematical description of shapes, layers, and "tweened" movements, allowing for smooth animations without the need to draw every frame by hand. While the compressed .sifz format keeps file sizes tiny by storing only the XML data and animation paths, the project itself is not a viewable video and must be rendered through the software into a standard format like .mp4 or an image sequence for playback.

>Example link 1: https://www.behance.net/gallery/193029727/Animation-Portfolio-2024

>Example link 2: https://www.behance.net/gallery/245261445/Studio-Soma

### .kdenlive (Kdenlive Editor):
- A .kdenlive file is an XML-based project document used by the open-source Kdenlive video editor to store the "blueprints" of a video edit. It does not contain any actual video or audio data; instead, it tracks the precise timestamps, transitions, effects, and file paths for all clips on your timeline. Because it is a plain-text project file, it is incredibly lightweight and ideal for version control on GitHub, but it requires a render process to combine the source media into a viewable video file like an .mp4.

>Example link 1: https://store.kde.org/p/2317860

>Example link 2: https://addons.videolan.org/p/2093528

---
>Note: Half of the above mentioned extensions/file types are soly present for the sake of more accessibility. The Prime focus should be on .aep and .drp/.comp. There is also .lottie worth consideration.

---
## Image Model Cost Calculation Estimation:

### State of the Art Image Generation Models:

<img width="917" height="194" alt="Image Generation Tokens" src="https://github.com/user-attachments/assets/35a9824e-f0b7-424f-84ce-84370179a8fe" />

### Respective Pricing:

<img width="1111" height="334" alt="Image Generation Pricing" src="https://github.com/user-attachments/assets/f3482c5c-fe5f-4987-aaa7-366908ce53b7" />

### Rough Estimation given a valid task/workflow:

<img width="1408" height="768" alt="Cost calculation" src="https://github.com/user-attachments/assets/6faa1697-79bf-4721-bfd7-0e28ec2ac795" />

---
>Current Focus: Transcribe .aep(paid) and .drp/.comp(moslty free open-source) and integrate respectively.

