import logging
import os
from pathlib import Path

from openai import OpenAI

from app.core.config import get_settings
from app.models.schemas import TranscriptionResult

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".webm", ".flac"}

MAX_FILE_SIZE_MB = 25


def _get_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


def _check_file(local_path: str) -> None:
    path = Path(local_path)

    if not path.exists():
        raise FileNotFoundError(f"Аудіофайл не знайдено: {local_path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Непідтримуваний формат аудіо: {path.suffix}. "
            f"Підтримуються: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"Файл {path.name} має розмір {size_mb:.1f} МБ — "
            f"це перевищує ліміт Whisper у {MAX_FILE_SIZE_MB} МБ."
        )


def transcribe(local_path: str) -> TranscriptionResult:
    settings = get_settings()
    _check_file(local_path)

    filename = Path(local_path).name
    logger.info(f"Транскрибування: {filename}")

    client = _get_client()

    with open(local_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=audio_file,
            response_format="verbose_json",
        )

    transcript = response.text.strip()
    language = getattr(response, "language", None)
    duration = getattr(response, "duration", None)

    logger.info(
        f"Транскрибовано {filename}: {len(transcript)} символів, "
        f"мова={language}, тривалість={duration}с"
    )

    return TranscriptionResult(
        audio_filename=filename,
        transcript=transcript,
        language=language,
        duration_seconds=float(duration) if duration is not None else None,
    )


def transcribe_all(local_paths: list[str]) -> list[TranscriptionResult]:
    results = []

    for path in local_paths:
        try:
            result = transcribe(path)
            results.append(result)
        except Exception as e:
            logger.error(f"Помилка транскрибування {path}: {e}")
            continue

    logger.info(f"Транскрибовано {len(results)} з {len(local_paths)} файлів.")
    return results