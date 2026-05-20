# Audio Analyzer Bot

Automated call quality analyzer for sales managers.  
The bot fetches audio files from Google Drive, transcribes them via Whisper, evaluates manager performance using GPT-4o, and writes structured results into Google Sheets — including red-highlighted comments for problematic calls.

## How It Works

1. Fetches audio files from a source Google Drive folder
2. Copies them to your working Drive folder
3. Transcribes each file via OpenAI Whisper
4. Analyzes the transcript with GPT-4o — extracts call type, work type, issues, and a score
5. Writes everything to Google Sheets; problem calls are flagged with red comments

## Quick Start

### 1. Clone the repository
```bash
git clone <repo-url>
cd audio_analyzer_bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Open .env and fill in your values
```

### 4. Set up Google Service Account
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a service account with access to Drive API and Sheets API
- Download the JSON key and save it as `service_account.json` in the project root
- Share your Drive folders and the Sheets spreadsheet with the service account email

### 5. Run
```bash
python -m app.main
```

## Project Structure

```
audio_analyzer_bot/
├── app/
│   ├── core/
│   │   └── config.py       # Environment config (Pydantic BaseSettings)
│   ├── models/
│   │   └── schemas.py      # Data schemas (Pydantic)
│   ├── services/
│   │   ├── google_api.py   # Google Drive & Sheets logic
│   │   ├── transcriber.py  # Whisper transcription
│   │   └── analyzer.py     # GPT-4o call analysis & prompts
│   └── main.py             # Entry point & orchestrator
├── data/                   # Temporary audio files (gitignored)
├── .env.example            # Environment variable template
├── requirements.txt
└── README.md
```

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to service account JSON key |
| `GOOGLE_DRIVE_SOURCE_FOLDER_ID` | ID of the Drive folder with audio files |
| `GOOGLE_DRIVE_WORK_FOLDER_ID` | ID of your working Drive folder |
| `GOOGLE_SHEET_ID` | ID of the Google Sheets spreadsheet |
| `GOOGLE_SHEET_NAME` | Sheet tab name (default: `Sheet1`) |
| `OPENAI_API_KEY` | OpenAI API key |
| `WHISPER_MODEL` | Whisper model (default: `whisper-1`) |
| `GPT_MODEL` | GPT model (default: `gpt-4o`) |

## Progress

- [x] Project structure
- [x] Pydantic schemas (`CallAnalysis`, `TranscriptionResult`, `ProcessedCall`, `SheetRow`)
- [x] Config via `BaseSettings`
- [x] Orchestrator with stubs (`main.py`)
- [ ] Google Drive API (`google_api.py`)
- [ ] Whisper transcription (`transcriber.py`)
- [ ] GPT-4o analysis (`analyzer.py`)
- [ ] Google Sheets write with red comment highlighting