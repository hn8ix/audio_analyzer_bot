# Audio Analyzer Bot

Automated quality control tool for car service center call managers.

The bot fetches audio recordings from Google Drive, transcribes them with OpenAI Whisper, evaluates manager performance using GPT-4o against a defined checklist, and writes structured results into Google Sheets — with low-scoring rows automatically highlighted in red.

---

## What It Does

1. **Downloads** audio files from a source Google Drive folder
2. **Parses filenames** to extract call date, phone number, and direction (incoming/outgoing)
3. **Moves** audio files to a working Drive folder
4. **Transcribes** each call using OpenAI Whisper
5. **Uploads** the transcript as a `.txt` file next to the audio in Drive
6. **Analyzes** the transcript with GPT-4o against 8 quality criteria:
   - Did the manager introduce themselves?
   - Did they ask about car body type, year, mileage?
   - Did they offer comprehensive diagnostics?
   - Did they ask about previous work done?
   - Did they follow Top-100 work instructions?
   - Did they end the call properly?
7. **Writes** results to Google Sheets — one row per call
8. **Highlights** rows with score below 5/8 in red for easy review

---

## Project Structure

```
audio_analyzer_bot/
├── app/
│   ├── core/
│   │   └── config.py          # Environment config (Pydantic BaseSettings)
│   ├── models/
│   │   └── schemas.py         # Data schemas matching spreadsheet columns
│   ├── services/
│   │   ├── google_api.py      # Google Drive & Sheets logic
│   │   ├── transcriber.py     # Whisper transcription
│   │   ├── analyzer.py        # GPT-4o call analysis
│   │   └── file_utils.py      # Filename parsing, transcript saving
│   └── main.py                # Entry point & orchestrator
├── data/                      # Temporary audio files (gitignored)
├── .env                       # Your secrets (gitignored, never push!)
├── .env.example               # Template — copy this to .env
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.10+
- OpenAI account with billing enabled ([platform.openai.com](https://platform.openai.com))
- Google Cloud project with **Drive API** and **Sheets API** enabled
- Google Service Account with a JSON key

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/hn8ix/audio_analyzer_bot.git
cd audio_analyzer_bot
```

### 2. Create virtual environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

pip install google-api-python-client google-auth google-auth-httplib2 \
            openai pydantic pydantic-settings python-dotenv
```

### 3. Set up Google Cloud

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or select existing)
3. Enable **Google Drive API** and **Google Sheets API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Grant role: **Editor**
6. Open the account → **Keys → Add Key → JSON** → download
7. Rename the file to `service_account.json` and place it in the project root

### 4. Set up Google Drive & Sheets

1. Create two folders in your Google Drive:
   - `Дзвінки` — source folder (put audio files here)
   - `Дзвінки_робоча` — working folder (bot moves files here)
2. Create a Google Sheets spreadsheet for results
3. Share all three (both folders + spreadsheet) with the service account email from `service_account.json` → role **Editor**

### 5. Configure environment variables
```bash
cp .env.example .env
```

Open `.env` and fill in:
```env
GOOGLE_SERVICE_ACCOUNT_PATH=service_account.json
GOOGLE_DRIVE_SOURCE_FOLDER_ID=<ID from folder URL>
GOOGLE_DRIVE_WORK_FOLDER_ID=<ID from folder URL>
GOOGLE_SHEET_ID=<ID from spreadsheet URL>
GOOGLE_SHEET_NAME=Лист1
OPENAI_API_KEY=sk-...
```

**How to find IDs from URLs:**
- Folder: `drive.google.com/drive/folders/`**`THIS_PART`**
- Sheet: `docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

---

## Usage

### Add audio files
Upload MP3/WAV/M4A files to your source Drive folder (`Дзвінки`).

Expected filename format:
```
YYYY-MM-DD_HH-MM_PHONENUMBER_incoming.mp3
2024-11-13_12-13_0672891962_incoming.mp3
```
The bot automatically extracts date and phone number from the filename.

### Run
```bash
source .venv/bin/activate
python -m app.main
```

### Output
- Audio files moved to working folder in Drive
- Transcript `.txt` files saved next to each audio file in Drive
- Google Sheets filled with one row per call:

| Column | Description |
|---|---|
| Дата | Call date (from filename) |
| Тип звернення | Call type |
| Номер телефону | Phone number (from filename) |
| Початок розмови | Manager introduced themselves (1/0) |
| Кузов / Рік / Пробіг | Car info collected (1/0 each) |
| Комплексна діагностика | Diagnostics offered (1/0) |
| Попередні роботи | Previous work asked (1/0) |
| Топ-100 | Followed work instructions (1/0) |
| Результат | Call outcome |
| Оцінка | Total score (0–8) |
| Коментар | Detailed comment, problems explained |

Rows with **score < 5** are highlighted red automatically.

---

## Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to service account JSON | `service_account.json` |
| `GOOGLE_DRIVE_SOURCE_FOLDER_ID` | Source audio folder ID | required |
| `GOOGLE_DRIVE_WORK_FOLDER_ID` | Working folder ID | required |
| `GOOGLE_SHEET_ID` | Spreadsheet ID | required |
| `GOOGLE_SHEET_NAME` | Sheet tab name | `Лист1` |
| `OPENAI_API_KEY` | OpenAI API key | required |
| `WHISPER_MODEL` | Whisper model | `whisper-1` |
| `GPT_MODEL` | GPT model | `gpt-4o` |
| `LOCAL_AUDIO_DIR` | Temp folder for downloads | `data` |
| `LLM_MAX_TOKENS` | Max tokens in LLM response | `1000` |
| `LLM_TEMPERATURE` | LLM temperature | `0.0` |

---

## Security

**Never push these files to GitHub:**
- `.env` — contains your API keys
- `service_account.json` — contains Google credentials

Both are already listed in `.gitignore`.

---

## Progress

- [x] Project structure & schemas
- [x] Filename parsing (date, phone, direction)
- [x] Google Drive: download, move, upload transcripts
- [x] Whisper transcription
- [x] GPT-4o analysis with 8-point checklist
- [x] Google Sheets write with red highlighting
- [x] README