"""
MoFA Effect - Utilities
Logging, file operations, and helper functions.
"""

import os
import sys
import json
import datetime


class Logger:
    """Simple logger that writes to both console and file."""

    def __init__(self, log_dir):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"mofa_run_{timestamp}.log")
        self.entries = []

    def log(self, level, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        self.entries.append(entry)
        print(entry)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
        except Exception:
            pass

    def info(self, message):
        self.log("INFO", message)

    def error(self, message):
        self.log("ERROR", message)

    def warning(self, message):
        self.log("WARNING", message)

    def section(self, title):
        separator = "=" * 70
        self.log("INFO", separator)
        self.log("INFO", f"  {title}")
        self.log("INFO", separator)


def save_json(data, filepath):
    """Save dictionary to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(filepath):
    """Load JSON file to dictionary."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_file_exists(filepath, description="File"):
    """Check if a file exists and return boolean."""
    if not os.path.isfile(filepath):
        print(f"[ERROR] {description} not found: {filepath}")
        return False
    return True


def get_file_size_mb(filepath):
    """Get file size in megabytes."""
    if os.path.isfile(filepath):
        return os.path.getsize(filepath) / (1024 * 1024)
    return 0


def sanitize_filename(name):
    """Remove characters that are invalid in filenames."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()


def ask_user(prompt, default=None):
    """Ask user for input with optional default."""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        user_input = input(f"{prompt}: ").strip()
        return user_input