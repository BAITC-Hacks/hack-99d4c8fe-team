"""Predictable clarification flow when AI is not configured or is unavailable."""

from typing import Any

from app.schemas import AIAssessmentResult, AIQuestionsResult, Question, TaskFields

BLOCKS: dict[int, list[tuple[str, str]]] = {
    1: [
        ("need", "Какую проблему нужно решить и почему это важно?"),
        ("users", "Кто будет пользоваться результатом решения?"),
    ],
    2: [
        ("data", "Какие данные, материалы или ресурсы доступны команде?"),
        ("constraints", "Какие есть ограничения по срокам, бюджету или технологии?"),
    ],
    3: [
        ("expectedResult", "Какой результат вы ожидаете получить от команды?"),
        ("successCriteria", "Как вы поймёте, что задача решена успешно?"),
        ("contact", "Как команда сможет с вами связаться?"),
        ("collaboration", "В каком формате вы готовы работать с командой?"),
    ],
}

POINTS = {
    "title": 10,
    "context": 12,
    "need": 12,
    "users": 10,
    "data": 8,
    "constraints": 8,
    "expectedResult": 12,
    "successCriteria": 10,
    "contact": 10,
    "collaboration": 8,
}


def generate_demo_questions(_draft: dict[str, Any], round_number: int) -> AIQuestionsResult:
    return AIQuestionsResult(
        questions=[
            Question(id=f"r{round_number}_{field}", text=question)
            for field, question in BLOCKS[round_number]
        ]
    )


def assess_demo_answers(
    draft: dict[str, Any], round_number: int, answers: list[dict[str, str]]
) -> AIAssessmentResult:
    if round_number < 3:
        return AIAssessmentResult(
            ready=False,
            questions=generate_demo_questions(draft, round_number + 1).questions,
            message="Следующий блок уточнений готов.",
        )

    all_answers = [*draft["answers"], {"round": round_number, "answers": answers}]
    values = {"title": draft["title"], "context": draft["description"]}
    for block in all_answers:
        expected_fields = [field for field, _ in BLOCKS[block["round"]]]
        for index, item in enumerate(block["answers"]):
            field = item["questionId"].split("_", 1)[-1]
            if field not in POINTS and index < len(expected_fields):
                field = expected_fields[index]
            if field in POINTS:
                values[field] = item["answer"].strip()

    final_text = (
        f"{draft['description'].strip()}\n\nЗадача: {values.get('need', '').strip()}".strip()
    )
    values["context"] = final_text
    fields = TaskFields.model_validate(values)
    rating = sum(points for field, points in POINTS.items() if getattr(fields, field).strip())
    return AIAssessmentResult(
        ready=True,
        finalText=final_text,
        taskFields=fields,
        rating=rating,
        message="Карточка подготовлена. Проверьте и подтвердите публикацию.",
    )
