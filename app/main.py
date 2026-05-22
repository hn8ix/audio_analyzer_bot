import logging
import shutil
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import SheetRow
from app.services import google_api, transcriber, analyzer
from app.services.File_utills import parse_filename, save_transcript_locally

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_local_files(local_dir: str) -> None:
    path = Path(local_dir)
    if path.exists():
        shutil.rmtree(path)
        logger.info(f"Очищено локальну папку: {local_dir}")


def run() -> None:
    settings = get_settings()
    today = date.today().isoformat()

    logger.info("апуск Audio Analyzer Bot")
    logger.info(f"Дата: {today}")
    logger.info(f"Вихідна папка: {settings.google_drive_source_folder_id}")
    logger.info(f"Робоча папка:   {settings.google_drive_work_folder_id}")
    logger.info(f"ID таблиці:      {settings.google_sheet_id}")

    logger.info("Крок 1: Завантаження аудіофайлів...")
    downloaded = google_api.download_all_audio(
        folder_id=settings.google_drive_source_folder_id,
        local_dir=settings.local_audio_dir,
    )
    if not downloaded:
        logger.warning("Аудіофайли не знайдені. Завершення.")
        return

    logger.info(f"Завантажено {len(downloaded)} файл(ів).")

    logger.info("Крок 2: Парсинг імен файлів...")
    source_files = google_api.list_audio_files(settings.google_drive_source_folder_id)
    id_by_name = {f["name"]: f["id"] for f in source_files}

    file_meta = {}
    for local_path, filename in downloaded:
        parsed = parse_filename(filename)
        if parsed:
            file_meta[filename] = parsed
            logger.info(
                f"  {filename} → телефон={parsed.phone}, "
                f"дата={parsed.date}, напрямок={parsed.direction}"
            )
        else:
            logger.warning(f"  {filename} → не вдалося розпізнати, буде використано поточну дату")

    logger.info("Крок 3: Переміщення файлів до робочої папки...")
    drive_ids: dict[str, str] = {}
    for local_path, filename in downloaded:
        if filename in id_by_name:
            new_id = google_api.copy_to_work_folder(
                file_id=id_by_name[filename],
                filename=filename,
                work_folder_id=settings.google_drive_work_folder_id,
            )
            drive_ids[filename] = new_id

    logger.info("Крок 4: Транскрибація файлів...")
    local_paths = [p for p, _ in downloaded]
    transcriptions = transcriber.transcribe_all(local_paths)

    if not transcriptions:
        logger.error("Усі транскрибації завершилися з помилкою. Завершення.")
        cleanup_local_files(settings.local_audio_dir)
        return

    logger.info("Крок 5: Завантаження транскрипцій на Drive...")
    for t in transcriptions:
        txt_path = save_transcript_locally(
            transcript=t.transcript,
            audio_path=str(Path(settings.local_audio_dir) / t.audio_filename),
            local_dir=settings.local_audio_dir,
        )
        try:
            google_api.upload_transcript(
                txt_path=txt_path,
                audio_filename=t.audio_filename,
                work_folder_id=settings.google_drive_work_folder_id,
            )
        except Exception as e:
            logger.error(f"Помилка завантаження транскрипції для {t.audio_filename}: {e}")

    logger.info("Крок 6: Аналіз дзвінків через GPT-4o...")
    processed_calls = analyzer.analyze_all(transcriptions)

    if not processed_calls:
        logger.error("Усі аналізи завершилися з помилкою. Завершення.")
        cleanup_local_files(settings.local_audio_dir)
        return

    logger.info("Крок 7: Запис результатів у Google Sheets...")
    sheet_rows = []
    for call in processed_calls:
        filename = call.transcription.audio_filename
        parsed = file_meta.get(filename)

        call.transcription_date = parsed.date if parsed else today
        call.drive_file_id = drive_ids.get(filename)

        phone = parsed.phone if parsed else ""
        sheet_rows.append(SheetRow.from_processed_call(call, phone=phone))

    google_api.append_rows(
        sheet_id=settings.google_sheet_id,
        sheet_name=settings.google_sheet_name,
        rows=sheet_rows,
    )

    cleanup_local_files(settings.local_audio_dir)

    ok_count = sum(1 for r in sheet_rows if r.score >= 5)
    logger.info("Готово")
    logger.info(f"Оброблено: {len(sheet_rows)} дзвінків")
    logger.info(f"Оцінка ≥5 (OK): {ok_count}  |  Оцінка <5 (червоні): {len(sheet_rows) - ok_count}")


if __name__ == "__main__":
    run()