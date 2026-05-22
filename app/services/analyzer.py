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

SYSTEM_PROMPT = f"""Ти — аналітик з контролю якості для автосервісу.
Проаналізуй транскрибацію дзвінка та поверни ТІЛЬКИ JSON-об'єкт — без markdown розмітки та пояснень.

Оціни кожен критерій та поверни 1 (так/добре) або 0 (ні/погано):

КРИТЕРІЇ:
1. greeting_ok — Чи привітався менеджер на початку розмови? (1=так, 0=ні)
2. asked_body — Чи запитав менеджер про тип кузова авто? (1=так, 0=ні)
3. asked_year — Чи запитав менеджер про рік випуску авто? (1=так, 0=ні)
4. asked_mileage — Чи запитав менеджер про пробіг? (1=так, 0=ні)
5. offered_diagnostics — Чи запропонував менеджер комплексну діагностику? (1=так, 0=ні)
6. asked_previous_work — Чи запитав менеджер, які роботи проводилися раніше? (1=так, 0=ні)
7. goodbye_ok — Чи попрощався менеджер належним чином наприкінці розмови? (1=так, 0=ні)
8. followed_top100 — Чи дотримався менеджер усіх інструкцій для визначеного типу робіт із топ-100? (1=так, 0=ні)

ТИПИ РОБІТ (вибери найближчий варіант або "Інший варіант"):
{chr(10).join(f'- {w}' for w in ALLOWED_WORK_TYPES)}

ТИПИ ДЗВІНКІВ (call_type):
- "Авто в роботі" — клієнт телефонує щодо авто, яке вже на сервісі
- "Вхідний дзвінок" — загальний вхідний дзвінок
- "Запис на сервіс" — запис на обслуговування
- "Консультація" — дзвінок для отримання консультації
- "Інше" — інше

РЕЗУЛЬТАТИ (result):
- "Передзвонити" — потрібно перетелефонувати
- "Запис" — записано
- "Запис на сервіс" — записано на сервіс
- "Повторно консультація" — повторна консультація
- "Передано іншому філіалу" — передано до іншої філії
- "Інше" — інше

ЗАПЧАСТИНИ (parts_source):
- "Наші" — запчастини автосервісу
- "Клієнта" — власні запчастини клієнта
- "" — не обговорювалося

Поверни ТОЧНО таку JSON-схему:
{{
  "call_type": "<один із типів дзвінків>",
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
  "top100_violations": "<які інструкції не були виконані, або порожній рядок>",
  "result": "<один із варіантів результату>",
  "parts_source": "<Наші / Клієнта / порожній рядок>",
  "comment": "<детальний коментар, виділіть проблеми, якщо вони є>"
}}"""


def _get_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


def _parse(raw: str, filename: str) -> CallAnalysis:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Некоректний JSON від LLM для файлу {filename}: {e}\nОригінал: {raw}")

    try:
        return CallAnalysis(
            call_type=CallType(data["call_type"]),
            greeting_ok=int(data["greeting_ok"]),
            asked_body=int(data["asked_body"]),
            asked_year=int(data["asked_year"]),
            asked_mileage=int(data["asked_mileage"]),
            offered_diagnostics=int(data["offered_diagnostics"]),
            asked_previous_work=int(data["asked_previous_work"]),
            booked_date=data.get("booked_date") or None,
            goodbye_ok=int(data["goodbye_ok"]),
            work_type=data["work_type"],
            followed_top100=int(data["followed_top100"]),
            top100_violations=data.get("top100_violations", ""),
            result=CallResult(data["result"]),
            parts_source=data.get("parts_source", ""),
            comment=data["comment"],
        )
    except (KeyError, ValueError) as e:
        raise ValueError(f"Невідповідність схемі для файлу {filename}: {e}\nДані: {data}")


def analyze(transcription: TranscriptionResult) -> ProcessedCall:
    settings = get_settings()
    client = _get_client()
    logger.info(f"Аналіз файлу: {transcription.audio_filename}")

    response = client.chat.completions.create(
        model=settings.gpt_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Файл: {transcription.audio_filename}\n\n"
                f"Транскрибація:\n{transcription.transcript}"
            )},
        ],
    )

    raw = response.choices[0].message.content or ""
    analysis = _parse(raw, transcription.audio_filename)

    logger.info(
        f"Завершено обробку {transcription.audio_filename}: "
        f"оцінка={ProcessedCall(transcription=transcription, analysis=analysis).score()}/8"
    )
    return ProcessedCall(transcription=transcription, analysis=analysis)


def analyze_all(transcriptions: list[TranscriptionResult]) -> list[ProcessedCall]:
    results = []
    for t in transcriptions:
        try:
            results.append(analyze(t))
        except Exception as e:
            logger.error(f"Помилка аналізу файлу {t.audio_filename}: {e}")
    logger.info(f"Проаналізовано {len(results)} з {len(transcriptions)} файлів.")
    return results