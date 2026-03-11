"""
MoFA Effect - Configuration
All paths, constants, and settings.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
AERENDER_PATH = r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files\aerender.exe"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")

# ---------------------------------------------------------------------------
# After Effects
# ---------------------------------------------------------------------------
AE_TIMEOUT_SECONDS = 300  # max wait for AE operations
RENDER_TIMEOUT_SECONDS = 600  # max wait for rendering

# ---------------------------------------------------------------------------
# AI Models
# ---------------------------------------------------------------------------
# GEMINI_MODEL = "gemini-2.0-flash"
# GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt"
# POLLINATIONS_TIMEOUT = 120  # seconds per image




# Using Groq instead of Gemini for free LLM access
GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast and good quality
GROQ_API_BASE = "https://api.groq.com/openai/v1"

POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt"
POLLINATIONS_TIMEOUT = 120  # seconds per image

# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------
TTS_VOICE = "en-US-GuyNeural"
TTS_RATE = "+0%"

# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------
DEFAULT_FPS = 30
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080

# ---------------------------------------------------------------------------
# Ensure directories exist
# ---------------------------------------------------------------------------
def ensure_directories():
    for directory in [OUTPUT_DIR, IMAGES_DIR, AUDIO_DIR, LOGS_DIR, TEMPLATES_DIR]:
        os.makedirs(directory, exist_ok=True)