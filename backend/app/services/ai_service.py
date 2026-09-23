import json
import os
from typing import Any

from openai import OpenAI

from app.schemas import AIAssessmentResult, AIQuestionsResult

# Вставьте сюда свой промпт генерации вопросов.
QUESTION_PROMPT = """
TODO: ВСТАВЬТЕ СЮДА ПРОМПТ ДЛЯ ГЕНЕРАЦИИ УТОЧНЯЮЩИХ ВОПРОСОВ.
Верните только JSON вида: {"questions":[{"id":"q1","text":"...","placeholder":"..."}]}.
Сформируйте вопросы для текущего блока так, чтобы постепенно уточнить задачу.
""".strip()

# Вставьте сюда свой промпт оценки полноты и подготовки карточки.
ASSESSMENT_PROMPT = """
TODO: ВСТАВЬТЕ СЮДА ПРОМПТ ДЛЯ ОЦЕНКИ ОТВЕТОВ И ГОТОВНОСТИ ЗАДАЧИ.
Верните только JSON. Если информации недостаточно: {"ready":false,
"questions":[...],"message":"..."}.
Если всё ясно: {"ready":true,"finalText":"...","taskFields":{...},"rating":0}.
Поля taskFields: title, context, need, users, data, constraints,
expectedResult, successCriteria, contact, collaboration.
""".strip()


def _client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Добавьте OPENAI_API_KEY в backend/.env и перезапустите FastAPI.")
    return OpenAI(api_key=key)


def _json_from_model(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Модель вернула пустой ответ.")
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()

    # Принимаем JSON и когда модель добавила короткое вступление или пояснение.
    json_start = cleaned.find("{")
    if json_start < 0:
        raise ValueError("В ответе модели не найден JSON-объект. Проверьте промпт.")
    try:
        value, _ = json.JSONDecoder().raw_decode(cleaned[json_start:])
    except json.JSONDecodeError as exc:
        raise ValueError("Модель вернула невалидный JSON. Уточните формат в промпте.") from exc
    if not isinstance(value, dict):
        raise ValueError("Ожидался JSON-объект от модели.")
    return value


def _generate(prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=f"{prompt}\n\nВходные данные:\n{json.dumps(payload, ensure_ascii=False)}",
    )
    return _json_from_model(response.output_text)


def generate_questions(draft: dict[str, Any], round_number: int) -> AIQuestionsResult:
    result = _generate(QUESTION_PROMPT, {"round": round_number, "maximum_rounds": 3, **draft})
    raw_questions = result.get("questions")
    if isinstance(raw_questions, list):
        normalized_questions = []
        for index, question in enumerate(raw_questions, start=1):
            if isinstance(question, str):
                normalized_questions.append({"id": f"q{round_number}_{index}", "text": question})
            elif isinstance(question, dict):
                text = question.get("text") or question.get("prompt") or question.get("question")
                if text:
                    normalized_questions.append(
                        {
                            **question,
                            "id": question.get("id") or f"q{round_number}_{index}",
                            "text": text,
                        }
                    )
        result["questions"] = normalized_questions
    return AIQuestionsResult.model_validate(result)


def assess_answers(
    draft: dict[str, Any], round_number: int, answers: list[dict[str, str]]
) -> AIAssessmentResult:
    result = _generate(
        ASSESSMENT_PROMPT,
        {
            "round": round_number,
            "maximum_rounds": 3,
            "original_idea": draft,
            "previous_answers": draft["answers"],
            "latest_answers": answers,
        },
    )
    return AIAssessmentResult.model_validate(result)
