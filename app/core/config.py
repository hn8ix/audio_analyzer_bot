from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
 
 
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
 
    google_service_account_path: str = "service_account.json"
 
    google_drive_source_folder_id: str
 
    google_drive_work_folder_id: str
 
    google_sheet_id: str
 
    google_sheet_name: str = "Sheet1"
 
    openai_api_key: str
 
    whisper_model: str = "whisper-1"
 
    gpt_model: str = "gpt-4o"
 
    local_audio_dir: str = "data"
 
    llm_max_tokens: int = 1000
 
    llm_temperature: float = 0.0
 
 
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Повертає синглтон налаштувань.
    lru_cache гарантує, що .env читається лише один раз.
 
    Використання:
        from app.core.config import get_settings
        settings = get_settings()
        print(settings.google_sheet_id)
    """
    return Settings()
 
