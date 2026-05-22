from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class CallType(str, Enum):
    CAR_IN_WORK = "Авто в роботі"
    INCOMING = "Вхідний дзвінок"
    BOOKING = "Запис на сервіс"
    CONSULTATION = "Консультація"
    OTHER = "Інше"

class CallResult(str, Enum):
    CALLBACK = "Передзвонити"
    BOOKED = "Запис"
    BOOKED_SERVICE = "Запис на сервіс"
    CONSULTATION = "Повторно консультація"
    TRANSFERRED = "Передано іншому філіалу"
    OTHER = "Інше"

class PartsSource(str, Enum):
    OURS = "Наші"
    CLIENT = "Клієнта"
    NOT_APPLICABLE = ""

class CallAnalysis(BaseModel):
    call_type: CallType = Field(description="Тип звернення")
    greeting_ok: int = Field(description="Початок розмови, представлення. 1 = менеджер представився, 0 = ні")
    asked_body: int = Field(description="Чи дізнався менеджер кузов автомобіля. 1/0")
    asked_year: int = Field(description="Чи дізнався менеджер рік автомобіля. 1/0")
    asked_mileage: int = Field(description="Чи дізнався менеджер пробіг. 1/0")
    offered_diagnostics: int = Field(description="Пропозиція про комплексну діагностику. 1/0")
    asked_previous_work: int = Field(description="Дізнався які роботи робилися раніше. 1/0")
    booked_date: Optional[str] = Field(default=None, description="Запис на сервіс, дата. Конкретна дата якщо є, інакше null")
    goodbye_ok: int = Field(description="Завершення розмови прощання. 1/0")
    work_type: str = Field(description="Яка робота з топ 100. Назва роботи або 'Інший варіант'")
    followed_top100: int = Field(description="Чи дотримувався всіх інструкцій з топ 100 робіт. 1/0")
    top100_violations: str = Field(default="", description="Яких рекомендацій менеджер не дотримувався з топ 100 робіт. Порожньо якщо немає")
    result: CallResult = Field(description="Результат дзвінка")
    parts_source: str = Field(default="", description="Запчастини: 'Наші', 'Клієнта', або порожньо")
    comment: str = Field(description="Коментар. Детальний опис проблем якщо є, або загальний підсумок")

class TranscriptionResult(BaseModel):
    audio_filename: str
    transcript: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None

class ProcessedCall(BaseModel):
    transcription: TranscriptionResult
    analysis: CallAnalysis
    transcription_date: Optional[str] = None
    drive_file_id: Optional[str] = None

    def score(self) -> int:
        a = self.analysis
        return (
            a.greeting_ok + a.asked_body + a.asked_year + a.asked_mileage
            + a.offered_diagnostics + a.asked_previous_work
            + a.goodbye_ok + a.followed_top100
        )

class SheetRow(BaseModel):
    date: str
    call_type: str
    phone: str
    branch: str = ""
    manager: str = ""
    greeting_ok: int
    asked_body: int
    asked_year: int
    asked_mileage: int
    offered_diagnostics: int
    asked_previous_work: int
    booked_date: str
    goodbye_ok: int
    work_type: str
    followed_top100: int
    top100_violations: str
    result: str
    score: int
    parts_source: str
    comment: str

    @classmethod
    def from_processed_call(cls, call: ProcessedCall, phone: str = "") -> "SheetRow":
        a = call.analysis
        return cls(
            date=call.transcription_date or "",
            call_type=a.call_type.value,
            phone=phone,
            branch="",
            manager="",
            greeting_ok=a.greeting_ok,
            asked_body=a.asked_body,
            asked_year=a.asked_year,
            asked_mileage=a.asked_mileage,
            offered_diagnostics=a.offered_diagnostics,
            asked_previous_work=a.asked_previous_work,
            booked_date=a.booked_date or "",
            goodbye_ok=a.goodbye_ok,
            work_type=a.work_type,
            followed_top100=a.followed_top100,
            top100_violations=a.top100_violations,
            result=a.result.value,
            score=call.score(),
            parts_source=a.parts_source,
            comment=a.comment,
        )