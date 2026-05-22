import json
import logging

from openai import OpenAI

from app.core.config import get_settings
from app.models.schemas import CallAnalysis, CallType, ManagerScore, TranscriptionResult, ProcessedCall

logger = logging.getLogger(__name__)

ALLOWED_WORK_TYPES = [
    "Комп'ютерна діагностика",
    "Заміна оливи ДВЗ + масляний фільтр",
    "Комплексна діагностика",
    "Ендоскопія",
    "Заміна повітряного фільтра ДВЗ",
    "Заміна фільтра салону в салоновому відділенні",
    "Заміна сайлентблоку",
    "Зняття / встановлення важків",
    "Заміна пластичної муфти карданного валу",
    "Слюсарні роботи",
    "Діагностична підвіска (НЕ ВИКОРИСТОВУЄМО/ВИКОРИСТОВУЄМО КОМПЛЕКСНО)",
    "Зняття / встановлення важків пр.",
    "Заміна амортизатора переднього",
    "Заміна оливи АКПП",
    "Мийка / чистка деталей",
    "Зняття / встановлення випускного патрубка",
    "Заміна охолоджувальної рідини",
    "Заміна гальмівної рідини з прокачкою",
    "Заміна оливи в зд. редуктор",
    "Кодування опцій",
    "Заміна амортизатора зд.",
    "Заміна гальмівних дисків та колодок пр.",
    "Інше",
]

RESPONSE_SCHEMA = """
{
  "call_type": "client" | "internal" | "other",
  "work_type": "<одне значення з дозволеного списку, або 'Інше'>",
  "is_ok": true | false,
  "issues": ["<проблема 1>", "<проблема 2>"],
  "comment": "<детальний коментар для таблиці>",
  "score": 1 | 0
}
"""

SYSTEM_PROMPT = f"""Ти — асистент з контролю якості для автосервісу.
Твоє завдання — аналізувати транскрибації розмов між менеджерами та клієнтами (або внутрішні дзвінки).

Обов'язки:
1. Визнач тип дзвінка: "client" (менеджер + клієнт), "internal" (між персоналом) або "other".
2. Визнач тип обговорюваних робіт. Вибирай ТІЛЬКИ з цього списку:
{chr(10).join(f'- {w}' for w in ALLOWED_WORK_TYPES)}
   Якщо жоден тип роботи не підходить, використовуй "Інше".
3. Оціни роботу менеджера:
   - is_ok = true  → менеджер відповів правильно, був ввічливим, задовольнив потреби клієнта.
   - is_ok = false → менеджер поводився грубо, ігнорував клієнта, надав невірну інформацію або не допоміг.
4. Перерахуй конкретні проблеми, якщо is_ok = false. Якщо is_ok = true, залиш список порожнім [].
5. Напиши детальний коментар для Google Таблиці. Якщо is_ok = false, чітко поясни, що пішло не так.
6. Постав оцінку: 1, якщо is_ok = true, або 0, якщо is_ok = false.

КРИТИЧНІ ПРАВИЛА:
- Відповідай ТІЛЬКИ у форматі valid JSON. Без вступних слів, без розмітки markdown, без пояснень поза межами JSON.
- Дотримуйся саме цієї схеми:
{RESPONSE_SCHEMA}
- work_type повинен точно збігатися з одним із значень зі списку дозволених.
- score має бути строго цілим числом 1 або 0 (integer).
"""


def _get_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


def _build_user_message(transcript: str, filename: str) -> str:
    return (
        f"Аудіофайл: {filename}\n\n"
        f"Транскрибація:\n{transcript}"
    )


def _parse_response(raw: str, filename: str) -> CallAnalysis:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM повернула некоректний JSON для файлу {filename}: {e}\nОригінал: {raw}")

    try:
        return CallAnalysis(
            call_type=CallType(data["call_type"]),
            work_type=data["work_type"],
            is_ok=bool(data["is_ok"]),
            issues=data.get("issues", []),
            comment=data["comment"],
            score=ManagerScore(int(data["score"])),
        )
    except (KeyError, ValueError) as e:
        raise ValueError(f"Відповідь LLM не відповідає схемі для файлу {filename}: {e}\nДані: {data}")


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
            {
                "role": "user",
                "content": _build_user_message(
                    transcription.transcript,
                    transcription.audio_filename,
                ),
            },
        ],
    )

    raw = response.choices[0].message.content or ""
    analysis = _parse_response(raw, transcription.audio_filename)

    logger.info(
        f"Оброблено файл {transcription.audio_filename}: "
        f"call_type={analysis.call_type.value}, "
        f"work_type={analysis.work_type}, "
        f"score={analysis.score.value}"
    )

    return ProcessedCall(
        transcription=transcription,
        analysis=analysis,
    )


def analyze_all(transcriptions: list[TranscriptionResult]) -> list[ProcessedCall]:
    results = []

    for t in transcriptions:
        try:
            result = analyze(t)
            results.append(result)
        except Exception as e:
            logger.error(f"Помилка аналізу файлу {t.audio_filename}: {e}")
            continue

    logger.info(f"Успішно проаналізовано {len(results)} з {len(transcriptions)} файлів.")
    return results