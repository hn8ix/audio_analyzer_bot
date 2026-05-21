import logging
import os
from pathlib import Path
 
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
 
from app.core.config import get_settings
from app.models.schemas import SheetRow
 
logger = logging.getLogger(__name__)
 
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
 
AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/aac",
    "video/mp4",   
}
 
RED_COLOR = {"red": 0.957, "green": 0.800, "blue": 0.800}
 
 
def _get_credentials() -> Credentials:
    settings = get_settings()
    return Credentials.from_service_account_file(
        settings.google_service_account_path,
        scopes=SCOPES,
    )
 
 
def _drive_service():
    return build("drive", "v3", credentials=_get_credentials(), cache_discovery=False)
 
 
def _sheets_service():
    return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)
 
 
def list_audio_files(folder_id: str) -> list[dict]:
    drive = _drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
 
    results = []
    page_token = None
 
    while True:
        response = drive.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()
 
        files = response.get("files", [])
        audio_files = [f for f in files if f.get("mimeType") in AUDIO_MIME_TYPES]
        results.extend(audio_files)
 
        page_token = response.get("nextPageToken")
        if not page_token:
            break
 
    logger.info(f"Знайдено {len(results)} аудіофайлів у папці {folder_id}")
    return results
 
 
def download_file(file_id: str, filename: str, local_dir: str) -> str:
    drive = _drive_service()
    local_path = str(Path(local_dir) / filename)
 
    os.makedirs(local_dir, exist_ok=True)
 
    request = drive.files().get_media(fileId=file_id)
 
    with open(local_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug(f"Завантаження {filename}: {int(status.progress() * 100)}%")
 
    logger.info(f"Завантажено: {filename} -> {local_path}")
    return local_path
 
 
def download_all_audio(folder_id: str, local_dir: str) -> list[tuple[str, str]]:
    files = list_audio_files(folder_id)
    results = []
 
    for file in files:
        local_path = download_file(
            file_id=file["id"],
            filename=file["name"],
            local_dir=local_dir,
        )
        results.append((local_path, file["name"]))
 
    return results
 
 
def copy_to_work_folder(file_id: str, filename: str, work_folder_id: str) -> str:
    drive = _drive_service()
 
    body = {
        "name": filename,
        "parents": [work_folder_id],
    }
    copied = drive.files().copy(fileId=file_id, body=body).execute()
    new_id = copied["id"]
 
    logger.info(f"Файл {filename} скопійовано в робочу папку (новий id: {new_id})")
    return new_id
 

SHEET_HEADERS = ["Дата", "Файл", "Тип дзвінка", "Тип роботи", "Статус", "Коментар", "Оцінка"]
 
 
def ensure_headers(sheet_id: str, sheet_name: str) -> None:
    sheets = _sheets_service()
    range_ = f"{sheet_name}!A1:G1"
 
    result = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_,
    ).execute()
 
    existing = result.get("values", [])
    if existing and existing[0] == SHEET_HEADERS:
        return  
 
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range,
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]},
    ).execute()
 
    logger.info("Заголовки таблиці успішно записані.")
 
 
def _get_next_empty_row(sheets_svc, sheet_id: str, sheet_name: str) -> int:
    result = sheets_svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A:A",
    ).execute()
    values = result.get("values", [])
    return len(values) + 1
 
 
def append_rows(sheet_id: str, sheet_name: str, rows: list[SheetRow]) -> int:
    if not rows:
        logger.warning("Немає рядків для запису.")
        return 0
 
    sheets = _sheets_service()
    ensure_headers(sheet_id, sheet_name)
 
    start_row = _get_next_empty_row(sheets, sheet_id, sheet_name)
 
    values = [
        [
            row.date,
            row.audio_filename,
            row.call_type,
            row.work_type,
            row.is_ok,
            row.comment,
            row.score,
        ]
        for row in rows
    ]
 
    range_ = f"{sheet_name}!A{start_row}"
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
 
    logger.info(f"Записано {len(rows)} рядків, починаючи з рядка {start_row}.")
 
    _highlight_problem_rows(sheets, sheet_id, sheet_name, rows, start_row)
 
    return start_row
 
 
def _highlight_problem_rows(
    sheets_svc,
    sheet_id: str,
    sheet_name: str,
    rows: list[SheetRow],
    start_row: int,
) -> None:
    
    meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheet_gid = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == sheet_name
    )
 
    requests = []
    for i, row in enumerate(rows):
        if row.is_ok == "НЕ OK":
            row_index = start_row - 1 + i   
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_gid,
                        "startRowIndex": row_index,
                        "endRowIndex": row_index + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 7,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": RED_COLOR,
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })
 
    if requests:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests},
        ).execute()
        count = len(requests)
        logger.info(f"Підсвічено червоним кольором {count} проблемних рядків.")