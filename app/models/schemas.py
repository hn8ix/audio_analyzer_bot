from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
 

class CallType(str, Enum):
    CLIENT = "client"
    INTERNAL = "internal"
    OTHER = "other"
 
 
class ManagerScore(int, Enum):
    OK = 1
    NOT_OK = 0
 
 
 
class CallAnalysis(BaseModel):
 
    call_type: CallType = Field(
        description="Тип дзвінка: з клієнтом, внутрішній або інший."
    )
 
    work_type: str = Field(
        description=(
            "Тип роботи, яку обговорюють у дзвінку. "
            "Обирати тільки з переліку допустимих робіт."
        )
    )
 
    is_ok: bool = Field(
        description=(
            "True — дзвінок пройшов нормально, менеджер відповідав коректно. "
            "False — є проблеми, що потребують реагування."
        )
    )
 
    issues: list[str] = Field(
        default_factory=list,
        description=(
            "Список конкретних проблем у дзвінку: "
            "некоректні відповіді, ігнорування клієнта, груба мова тощо. "
            "Порожній список, якщо is_ok=True."
        )
    )
 
    comment: str = Field(
        description=(
            "Розгорнутий коментар для таблиці. "
            "Якщо is_ok=False — обов'язково пояснює причину. "
            "Цей текст буде позначено червоним у Google Sheets."
        )
    )
 
    score: ManagerScore = Field(
        description="Підсумкова оцінка менеджера: 1 (добре) або 0 (погано)."
    )
 
 

 
class TranscriptionResult(BaseModel):
 
    audio_filename: str = Field(description="Ім'я оригінального аудіофайлу.")
    transcript: str = Field(description="Повний текст транскрибації.")
    language: Optional[str] = Field(
        default=None,
        description="Мова, яку визначив Whisper (наприклад, 'uk', 'ru')."
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Тривалість аудіо в секундах."
    )
 
 
 
class ProcessedCall(BaseModel):
    
    transcription: TranscriptionResult
    analysis: CallAnalysis
 
    transcription_date: Optional[str] = Field(
        default=None,
        description="Дата транскрибації у форматі YYYY-MM-DD."
    )
 
    drive_file_id: Optional[str] = Field(
        default=None,
        description="ID файлу в Google Drive після копіювання."
    )
 
 
class SheetRow(BaseModel):
    
    date: str = Field(description="Дата транскрибації (YYYY-MM-DD).")
    audio_filename: str = Field(description="Ім'я аудіофайлу.")
    call_type: str = Field(description="Тип дзвінка.")
    work_type: str = Field(description="Тип роботи.")
    is_ok: str = Field(description="OK / НЕ OK.")
    comment: str = Field(description="Коментар (червоний якщо НЕ OK).")
    score: int = Field(description="Оцінка: 0 або 1.")
 
    @classmethod
    def from_processed_call(cls, call: ProcessedCall) -> "SheetRow":
        return cls(
            date=call.transcription_date or "",
            audio_filename=call.transcription.audio_filename,
            call_type=call.analysis.call_type.value,
            work_type=call.analysis.work_type,
            is_ok="OK" if call.analysis.is_ok else "НЕ OK",
            comment=call.analysis.comment,
            score=call.analysis.score.value,
        )
 
