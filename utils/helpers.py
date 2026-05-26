"""
BulkWave Pro - General Helper Utilities
"""

import os
import sys
import random
import time
import datetime
import json
from pathlib import Path


# ─── Path helpers ─────────────────────────────────────────────────────────────

def get_app_root() -> Path:
    """Return the absolute path to the application root directory."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Return (and ensure) the data directory."""
    d = get_app_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_chrome_data_dir() -> Path:
    """Return (and ensure) the Chrome profile directory for WhatsApp sessions."""
    d = get_app_root() / "chrome_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_exports_dir() -> Path:
    """Return (and ensure) the exports directory for failed-number files."""
    d = get_data_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── Time helpers ─────────────────────────────────────────────────────────────

def random_delay(min_sec: float, max_sec: float) -> None:
    """Sleep for a random duration between min_sec and max_sec."""
    duration = random.uniform(min_sec, max_sec)
    time.sleep(duration)


def now_str() -> str:
    """Return current local time as HH:MM:SS string."""
    return datetime.datetime.now().strftime("%H:%M:%S")


def now_timestamp() -> str:
    """Return current local datetime as ISO-like string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def estimate_completion(remaining: int, min_delay: float, max_delay: float) -> str:
    """Return a human-readable estimated completion time string."""
    avg_delay = (min_delay + max_delay) / 2
    total_seconds = remaining * avg_delay
    if total_seconds < 60:
        return f"~{int(total_seconds)}s"
    elif total_seconds < 3600:
        return f"~{int(total_seconds / 60)}m"
    else:
        hours = int(total_seconds / 3600)
        mins = int((total_seconds % 3600) / 60)
        return f"~{hours}h {mins}m"


# ─── Message helpers ──────────────────────────────────────────────────────────

def apply_placeholders(message: str, name: str = "", number: str = "") -> str:
    """Replace {name} and {number} placeholders in a message."""
    result = message
    result = result.replace("{name}", name or "")
    result = result.replace("{number}", number or "")
    return result


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text and append ellipsis if it exceeds max_len."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ─── File helpers ─────────────────────────────────────────────────────────────

def load_json(path: str | Path, default=None):
    """Load a JSON file, returning default if the file doesn't exist or is invalid."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(path: str | Path, data) -> bool:
    """Persist data as JSON to path. Returns True on success."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def open_folder(path: str | Path) -> None:
    """Open a folder in Windows Explorer."""
    import subprocess
    subprocess.Popen(f'explorer "{path}"')


def get_file_size_str(path: str | Path) -> str:
    """Return human-readable file size."""
    try:
        size = os.path.getsize(path)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    except Exception:
        return "Unknown"
