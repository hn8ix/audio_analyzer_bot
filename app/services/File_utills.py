import logging
import re
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

FILENAME_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"_(?P<time>\d{2}-\d{2})"
    r"_(?P<phone>\d+)"
    r"_(?P<direction>\w+)"
    r"\.\w+$"
)

@dataclass
class ParsedFilename:
    date: str
    time: str
    phone: str
    direction: str
    original: str

def parse_filename(filename: str) -> Optional[ParsedFilename]:
    m = FILENAME_PATTERN.match(filename)
    if not m:
        logger.warning(f"Не вдалося розпізнати ім'я файлу: {filename}")
        return None

    return ParsedFilename(
        date=m.group("date"),
        time=m.group("time"),
        phone=m.group("phone"),
        direction=m.group("direction"),
        original=filename,
    )

def save_transcript_locally(transcript: str, audio_path: str, local_dir: str) -> str:
    stem = Path(audio_path).stem
    txt_path = str(Path(local_dir) / f"{stem}_transcript.txt")

    os.makedirs(local_dir, exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    logger.info(f"Транскрибацію збережено локально: {txt_path}")
    return txt_path