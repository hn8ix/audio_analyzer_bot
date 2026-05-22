import logging
import shutil
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import SheetRow
from app.services import google_api, transcriber, analyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_local_files(local_dir: str) -> None:
    path = Path(local_dir)
    if path.exists():
        shutil.rmtree(path)
        logger.info(f"Очищено локальну папку аудіо: {local_dir}")


def run() -> None:
    settings = get_settings()
    today = date.today().isoformat()

    logger.info("Запуск Audio Analyzer Bot ")
    logger.info(f"Дата: {today}")
    logger.info(f"Вихідна папка: {settings.google_drive_source_folder_id}")
    logger.info(f"Робоча папка:   {settings.google_drive_work_folder_id}")
    logger.info(f"ID таблиці:      {settings.google_sheet_id}")

    logger.info("Крок 1: Завантаження аудіофайлів з Google Drive...")
    downloaded = google_api.download_all_audio(
        folder_id=settings.google_drive_source_folder_id,
        local_dir=settings.local_audio_dir,
    )

    if not downloaded:
        logger.warning("Аудіофайли у вихідній папці не знайдені. Завершення.")
        return

    local_paths = [path for path, _ in downloaded]
    filenames = [name for _, name in downloaded]
    logger.info(f"Завантажено {len(local_paths)} файл(ів).")

    logger.info("Крок 2: Копіювання файлів у робочу папку Drive...")
    source_files = google_api.list_audio_files(settings.google_drive_source_folder_id)
    id_by_name = {f["name"]: f["id"] for f in source_files}

    drive_ids: dict[str, str] = {}
    for filename in filenames:
        if filename in id_by_name:
            new_id = google_api.copy_to_work_folder(
                file_id=id_by_name[filename],
                filename=filename,
                work_folder_id=settings.google_drive_work_folder_id,
            )
            drive_ids[filename] = new_id

    logger.info("Крок 3: Транскрибація файлів через Whisper...")
    transcriptions = transcriber.transcribe_all(local_paths)

    if not transcriptions:
        logger.error("Усі транскрибації завершилися з помилкою. Завершення.")
        cleanup_local_files(settings.local_audio_dir)
        return

    logger.info("Крок 4: Аналіз дзвінків через GPT-4o...")
    processed_calls = analyzer.analyze_all(transcriptions)

    if not processed_calls:
        logger.error("Усі аналізи завершилися з помилкою. Завершення.")
        cleanup_local_files(settings.local_audio_dir)
        return

    logger.info("Крок 5: Запис результатів у Google Sheets...")

    sheet_rows = []
    for call in processed_calls:
        call.transcription_date = today
        call.drive_file_id = drive_ids.get(call.transcription.audio_filename)
        sheet_rows.append(SheetRow.from_processed_call(call))

    google_api.append_rows(
        sheet_id=settings.google_sheet_id,
        sheet_name=settings.google_sheet_name,
        rows=sheet_rows,
    )

    cleanup_local_files(settings.local_audio_dir)

    ok_count = sum(1 for r in sheet_rows if r.is_ok == "OK")
    not_ok_count = len(sheet_rows) - ok_count

    logger.info(" Готово ")
    logger.info(f"Оброблено: {len(sheet_rows)} дзвінків")
    logger.info(f"OK: {ok_count}  |  NOT OK (червоні): {not_ok_count}")


if __name__ == "__main__":
    run()