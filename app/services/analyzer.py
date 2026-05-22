import json
import logging

from openai import OpenAI

from app.core.config import get_settings
from app.models.schemas import (
    CallAnalysis, CallType, CallResult,
    TranscriptionResult, ProcessedCall
)

logger = logging.getLogger(__name__)

ALLOWED_WORK_TYPES = [
    "Комп'ютерна діагностика", "Заміна оливи ДВЗ + масляний фільтр",
    "Комплексна діагностика", "Комплексне ТО", "Ендоскопія",
    "Заміна повітряного фільтра ДВЗ", "Заміна фільтра салону",
    "Заміна сайлентблоку", "Зняття / встановлення деталі",
    "Заміна пластичної муфти карданного валу", "Слюсарні роботи",
    "Заміна амортизатора переднього", "Заміна амортизатора заднього",
    "Заміна оливи АКПП", "Мийка / чистка деталей",
    "Заміна охолоджувальної рідини", "Заміна гальмівної рідини",
    "Заміна оливи в зд. редуктор", "Кодування опцій",
    "Заміна гальмівних дисків та колодок", "Заміна свічок запалення",
    "Заміна ланцюгів ГРМ", "Заміна приводного ременя",
    "Заміна помпи", "Заміна прокладки маслостакана",
    "Інший варіант",
]

SYSTEM_PROMPT = f"""Ти аналітик контролю якості автосервісу.
Проаналізуй транскрипцію дзвінка та поверни ТІЛЬКИ JSON об'єкт — без markdown, без пояснень.

Оціни кожен критерій і поверни 1 (так/добре) або 0 (ні/погано):

КРИТЕРІЇ:
1. greeting_ok — Чи представився менеджер на початку? (1=так, 0=ні)
2. asked_body — Чи дізнався менеджер тип кузова? (1=так, 0=ні)
3. asked_year — Чи дізнався менеджер рік випуску? (1=так, 0=ні)
4. asked_mileage — Чи дізнався менеджер пробіг? (1=так, 0=ні)
5. offered_diagnostics — Чи запропонував комплексну діагностику? (1=так, 0=ні)
6. asked_previous_work — Чи дізнався, які роботи проводились раніше? (1=так, 0=ні)
7. goodbye_ok — Чи попрощався менеджер належним чином? (1=так, 0=ні)
8. followed_top100 — Чи дотримався всіх інструкцій для визначеного типу робіт (топ-100)? (1=так, 0=ні)

ТИПИ РОБІТ (обери найближчий збіг або "Інший варіант"):
{chr(10).join(f'- {w}' for w in ALLOWED_WORK_TYPES)}

ТИПИ ДЗВІНКІВ:
- "Авто в роботі"
- "Вхідний дзвінок"
- "Запис на сервіс"
- "Консультація"
- "Інше"

РЕЗУЛЬТАТИ:
- "Передзвонити"
- "Запис"
- "Запис на сервіс"
- "Повторно консультація"
- "Передано іншому філіалу"
- "Інше"

ЗАПЧАСТИНИ:
- "Наші"
- "Клієнта"
- ""

Поверни ТОЧНО таку JSON схему:
{{
  "call_type": "<один з типів дзвінків>",
  "greeting_ok": 0 або 1,
  "asked_body": 0 або 1,
  "asked_year": 0 або 1,
  "asked_mileage": 0 або 1,
  "offered_diagnostics": 0 або 1,
  "asked_previous_work": 0 або 1,
  "booked_date": "<рядок з датою або null>",
  "goodbye_ok": 0 або 1,
  "work_type": "<тип роботи зі списку>",
  "followed_top100": 0 або 1,
  "top100_violations": "<які інструкції не виконано, або порожній рядок>",
  "result": "<один зі значень результату>",
  "parts_source": "<Наші / Клієнта / порожньо>",
  "comment": "<детальний коментар, виділи проблеми якщо є>"
}}"""

def _get_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)

def _parse(raw: str, filename: str) -> CallAnalysis:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Недійсний JSON від LLM для {filename}: {e}\nRaw: {raw}")

    def safe_call_type(v: str) -> CallType:
        try:
            return CallType(v)
        except ValueError:
            logger.warning(f"Невідомий call_type '{v}', встановлено OTHER")
            return CallType.OTHER

    def safe_result(v: str) -> CallResult:
        try:
            return CallResult(v)
        except ValueError:
            logger.warning(f"Невідомий result '{v}', встановлено OTHER")
            return CallResult.OTHER

    def safe_int(v) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    try:
        return CallAnalysis(
            call_type=safe_call_type(data["call_type"]),
            greeting_ok=safe_int(data.get("greeting_ok")),
            asked_body=safe_int(data.get("asked_body")),
            asked_year=safe_int(data.get("asked_year")),
            asked_mileage=safe_int(data.get("asked_mileage")),
            offered_diagnostics=safe_int(data.get("offered_diagnostics")),
            asked_previous_work=safe_int(data.get("asked_previous_work")),
            booked_date=data.get("booked_date") or None,
            goodbye_ok=safe_int(data.get("goodbye_ok")),
            work_type=data.get("work_type", "Інший варіант"),
            followed_top100=safe_int(data.get("followed_top100")),
            top100_violations=data.get("top100_violations", ""),
            result=safe_result(data.get("result", "Інше")),
            parts_source=data.get("parts_source", ""),
            comment=data.get("comment", ""),
        )
    except KeyError as e:
        raise ValueError(f"Відсутнє обов'язкове поле для {filename}: {e}\nData: {data}")

def analyze(transcription: TranscriptionResult) -> ProcessedCall:
    settings = get_settings()
    client = _get_client()
    logger.info(f"Аналіз: {transcription.audio_filename}")

    response = client.chat.completions.create(
        model=settings.gpt_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"File: {transcription.audio_filename}\n\n"
                f"Transcript:\n{transcription.transcript}"
            )},
        ],
    )

    raw = response.choices[0].message.content or ""
    analysis = _parse(raw, transcription.audio_filename)

    logger.info(
        f"Завершено {transcription.audio_filename}: "
        f"оцінка={ProcessedCall(transcription=transcription, analysis=analysis).score()}/8"
    )
    return ProcessedCall(transcription=transcription, analysis=analysis)

def analyze_all(transcriptions: list[TranscriptionResult]) -> list[ProcessedCall]:
    results = []
    for t in transcriptions:
        try:
            results.append(analyze(t))
        except Exception as e:
            logger.error(f"Помилка аналізу {t.audio_filename}: {e}")
    logger.info(f"Проаналізовано {len(results)}/{len(transcriptions)} файл(ів).")
    return results