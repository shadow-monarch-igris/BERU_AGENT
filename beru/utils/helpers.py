from __future__ import annotations

import json
import re
import hashlib
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from functools import wraps
import time


def generate_id() -> str:
    return hashlib.md5(
        f"{time.time()}{datetime.now().microsecond}".encode()
    ).hexdigest()[:12]


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
        r"\{[\s\S]*\}",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    return None


def extract_code_blocks(text: str, language: Optional[str] = None) -> List[str]:
    if language:
        pattern = rf"```{language}\s*([\s\S]*?)\s*```"
    else:
        pattern = r"```[\w]*\s*([\s\S]*?)\s*```"

    return re.findall(pattern, text)


def sanitize_path(path: str, base_dir: str = ".") -> Path:
    resolved_path = Path(path).expanduser().resolve()
    base = Path(base_dir).resolve()

    try:
        resolved_path.relative_to(base)
    except ValueError:
        if not str(resolved_path).startswith(str(base)):
            raise ValueError(
                f"Path '{resolved_path}' is outside allowed directory '{base}'"
            )

    return resolved_path


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


def measure_time(func):
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def format_size(size_bytes: int) -> str:
    bytes_float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_float < 1024:
            return f"{bytes_float:.2f} {unit}"
        bytes_float /= 1024
    return f"{bytes_float:.2f} PB"


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def deep_merge(base: Dict, update: Dict) -> Dict:
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Timer:
    def __init__(self):
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start_time

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, *args):
        self.elapsed = time.time() - self.start_time
