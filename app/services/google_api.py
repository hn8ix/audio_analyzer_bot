import logging
import os
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import get_settings
from app.models.schemas import SheetRow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

AUDIO_MIME_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav",
    "audio/ogg", "audio/webm", "audio/flac", "audio/aac", "video/mp4",
}

RED_COLOR = {"red": 0.957, "green": 0.800, "blue": 0.800}

SHEET_HEADERS = [
    "Дата", "Тип звернення", "Номер телефону", "Філія", "Менеджер",
    "Початок розмови, представлення",
    "Чи дізнався менеджер кузов автомобіля",
    "Чи дізнався менеджер рік автомобіля",
    "Чи дізнався менеджер пробіг",
    "Пропозиція про комплексну діагностику",
    "Дізнався які роботи робилися раніше",
    "Запис на сервіс, Дата",
    "Завершення розмови прощання",
    "Яка робота з топ 100",
    "Чи дотримувався всіх інструкцій з топ 100 робіт",
    "Яких рекомендацій менеджер не дотримувався",
    "Результат", "Оцінка", "Запчастини", "Коментар",
]

def _creds() -> Credentials:
    return Credentials.from_service_account_file(
        get_settings().google_service_account_path, scopes=SCOPES
    )

def _drive():
    return build("drive", "v3", credentials=_creds(), cache_discovery=False)

def _sheets():
    return build("sheets", "v4", credentials=_creds(), cache_discovery=False)

def list_audio_files(folder_id: str) -> list[dict]:
    drive = _drive()
    query = f"'{folder_id}' in parents and trashed = false"
    results, page_token = [], None
    while True:
        resp = drive.files().list(
            q=query, spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()
        results.extend(f for f in resp.get("files", []) if f.get("mimeType") in AUDIO_MIME_TYPES)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    logger.info(f"Знайдено {len(results)} аудіофайл(ів)")
    return results

def download_file(file_id: str, filename: str, local_dir: str) -> str:
    local_path = str(Path(local_dir) / filename)
    os.makedirs(local_dir, exist_ok=True)
    request = _drive().files().get_media(fileId=file_id)
    with open(local_path, "wb") as f:
        dl = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
    logger.info(f"Завантажено: {filename}")
    return local_path

def download_all_audio(folder_id: str, local_dir: str) -> list[tuple[str, str]]:
    files = list_audio_files(folder_id)
    return [(download_file(f["id"], f["name"], local_dir), f["name"]) for f in files]

def copy_to_work_folder(file_id: str, filename: str, work_folder_id: str) -> str:
    drive = _drive()
    file = drive.files().get(fileId=file_id, fields="parents").execute()
    current_parents = ",".join(file.get("parents", []))

    updated = drive.files().update(
        fileId=file_id,
        addParents=work_folder_id,
        removeParents=current_parents,
        fields="id, parents",
    ).execute()

    logger.info(f"Переміщено {filename} до робочої папки ({updated['id']})")
    return updated["id"]

def ensure_headers(sheet_id: str, sheet_name: str) -> None:
    sheets = _sheets()
    result = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{sheet_name}!A1:T1"
    ).execute()
    existing = result.get("values", [])
    if existing and existing[0] == SHEET_HEADERS:
        return
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{sheet_name}!A1",
        valueInputOption="RAW", body={"values": [SHEET_HEADERS]},
    ).execute()
    logger.info("Заголовки записані.")

def _next_empty_row(sheets_svc, sheet_id: str, sheet_name: str) -> int:
    result = sheets_svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{sheet_name}!A:A"
    ).execute()
    return len(result.get("values", [])) + 1

def append_rows(sheet_id: str, sheet_name: str, rows: list[SheetRow]) -> int:
    if not rows:
        return 0
    sheets = _sheets()
    ensure_headers(sheet_id, sheet_name)
    start_row = _next_empty_row(sheets, sheet_id, sheet_name)

    values = [[
        r.date, r.call_type, r.phone, r.branch, r.manager,
        r.greeting_ok, r.asked_body, r.asked_year, r.asked_mileage,
        r.offered_diagnostics, r.asked_previous_work, r.booked_date,
        r.goodbye_ok, r.work_type, r.followed_top100, r.top100_violations,
        r.result, r.score, r.parts_source, r.comment,
    ] for r in rows]

    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{sheet_name}!A{start_row}",
        valueInputOption="RAW", body={"values": values},
    ).execute()
    logger.info(f"Записано {len(rows)} рядок(ів), починаючи з {start_row}.")

    _highlight_bad_rows(sheets, sheet_id, sheet_name, rows, start_row)
    return start_row

def _highlight_bad_rows(sheets_svc, sheet_id, sheet_name, rows, start_row):
    meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheet_gid = next(
        s["properties"]["sheetId"] for s in meta["sheets"]
        if s["properties"]["title"] == sheet_name
    )
    requests = []
    for i, row in enumerate(rows):
        if row.score < 5:
            idx = start_row - 1 + i
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_gid, "startRowIndex": idx,
                           "endRowIndex": idx + 1, "startColumnIndex": 0, "endColumnIndex": 20},
                "cell": {"userEnteredFormat": {"backgroundColor": RED_COLOR}},
                "fields": "userEnteredFormat.backgroundColor",
            }})
    if requests:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body={"requests": requests}
        ).execute()
        logger.info(f"Виділено {len(requests)} рядок(ів) червоним кольором.")

def upload_transcript(txt_path: str, audio_filename: str, work_folder_id: str) -> str:
    from googleapiclient.http import MediaFileUpload

    drive = _drive()
    txt_filename = Path(txt_path).name

    file_metadata = {
        "name": txt_filename,
        "parents": [work_folder_id],
        "mimeType": "text/plain",
    }
    media = MediaFileUpload(txt_path, mimetype="text/plain")

    uploaded = drive.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()

    logger.info(f"Транскрипцію завантажено на Drive: {txt_filename} ({uploaded['id']})")
    return uploaded["id"]