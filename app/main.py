import logging
from datetime import date
 
from app.core.config import get_settings
from app.models.schemas import ProcessedCall, SheetRow
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)
 
 
def download_audio_files() -> list[str]:
    logger.info("Завантаження аудіофайлів з Google Drive...")
    raise NotImplementedError
 
 
def copy_to_work_folder(local_paths: list[str]) -> dict[str, str]:
    logger.info("Копіювання файлів у робочу папку Drive...")
    raise NotImplementedError
 
 
def transcribe_file(local_path: str) -> str:
    logger.info(f"Транскрибація файлу: {local_path}")
    raise NotImplementedError
 
 
def analyze_call(transcript: str, filename: str) -> ProcessedCall:
    logger.info(f"Аналіз дзвінка: {filename}")
    raise NotImplementedError
 
 
def write_to_sheet(rows: list[SheetRow]) -> None:
    logger.info(f"Запис {len(rows)} рядків у Google Sheets...")
    raise NotImplementedError
 
 
def run() -> None:
    settings = get_settings()
    logger.info("Старт аналізатора дзвінків")
    logger.info(f"Source folder: {settings.google_drive_source_folder_id}")
    logger.info(f"Sheet ID: {settings.google_sheet_id}")
 
    today = date.today().isoformat()
 
    local_paths = download_audio_files()
    logger.info(f"Знайдено файлів: {len(local_paths)}")
 
    drive_ids = copy_to_work_folder(local_paths)
 
    sheet_rows: list[SheetRow] = []
    for local_path in local_paths:
        filename = local_path.split("/")[-1]
        transcript = transcribe_file(local_path)
        processed = analyze_call(transcript, filename)
        processed.transcription_date = today
        processed.drive_file_id = drive_ids.get(filename)
        sheet_rows.append(SheetRow.from_processed_call(processed))
 

    write_to_sheet(sheet_rows)
    logger.info("Готово!")
 
 
if __name__ == "__main__":
    run()
 
