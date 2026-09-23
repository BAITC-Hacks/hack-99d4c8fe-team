import json
import os
import re
import uuid
from typing import Any

from google import genai
from google.genai import types

from app.schemas import AIAssessmentResult, AIQuestionsResult, Question, TaskFields

QUESTION_PROMPT = """
You are an expert Business Analyst. Analyze the task description and ask 3 clear, targeted follow-up questions to clarify missing business/technical details.
Respond ONLY with a single valid JSON object in this format:
{
  "clarifying_questions": ["Question 1 text?", "Question 2 text?", "Question 3 text?"]
}
"""

ASSESSMENT_PROMPT = """
You are an expert Business Analyst preparing a task card. Analyze the draft and answers.
If details are sufficient, set "ready": true, provide "finalText" and "taskFields", and calculate a "rating" (0-100).
If details are missing, set "ready": false and ask follow-up "questions".

Respond ONLY with a valid JSON object matching this schema:
{
  "ready": boolean,
  "rating": integer,
  "message": "string",
  "questions": [{"id": "string", "text": "string", "label": "string"}],
  "finalText": "string",
  "taskFields": {
    "title": "string",
    "context": "string",
    "need": "string",
    "users": "string",
    "data": "string",
    "constraints": "string",
    "expectedResult": "string",
    "successCriteria": "string",
    "contact": "string",
    "collaboration": "string"
  }
}
"""


def _json_from_model(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx : end_idx + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Не удалось распарсить JSON: {exc}") from exc


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    return genai.Client(api_key=api_key)


def generate_questions(draft: dict[str, Any], round_num: int) -> AIQuestionsResult:
    client = get_client()

    user_content = json.dumps(
        {
            "round": round_num,
            "title": draft.get("title", ""),
            "description": draft.get("description", ""),
            "category": draft.get("category", ""),
            "previous_answers": draft.get("answers", []),
        },
        ensure_ascii=False,
    )

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[QUESTION_PROMPT, user_content],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    content = response.text or "{}"
    parsed_data = _json_from_model(content)

    raw_questions = parsed_data.get("clarifying_questions", [])
    questions_list: list[Question] = []

    for idx, q_text in enumerate(raw_questions, start=1):
        if isinstance(q_text, str):
            questions_list.append(
                Question(
                    id=f"q_{round_num}_{idx}_{uuid.uuid4().hex[:6]}",
                    text=q_text,
                    label=f"Вопрос {idx}",
                    placeholder="Напишите ответ...",
                )
            )

    if not questions_list:
        questions_list = [
            Question(
                id=f"q_{round_num}_1",
                text="Каковы основные критерии успеха данного проекта?",
                label="Критерии успеха",
            )
        ]

    return AIQuestionsResult(questions=questions_list)


def assess_answers(
    draft: dict[str, Any],
    round_num: int,
    latest_answers: list[dict[str, Any]],
) -> AIAssessmentResult:
    client = get_client()

    context_payload = {
        "round": round_num,
        "draft": draft,
        "latest_answers": latest_answers,
    }

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[ASSESSMENT_PROMPT, json.dumps(context_payload, ensure_ascii=False)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    content = response.text or "{}"
    parsed_data = _json_from_model(content)

    questions_data = parsed_data.get("questions", [])
    normalized_questions: list[Question] = []

    for idx, item in enumerate(questions_data, start=1):
        if isinstance(item, str):
            normalized_questions.append(
                Question(
                    id=f"q_{round_num + 1}_{idx}_{uuid.uuid4().hex[:6]}",
                    text=item,
                    label=f"Уточнение {idx}",
                )
            )
        elif isinstance(item, dict):
            normalized_questions.append(
                Question(
                    id=item.get("id") or f"q_{round_num + 1}_{idx}",
                    text=item.get("text", ""),
                    label=item.get("label"),
                    placeholder=item.get("placeholder"),
                )
            )

    task_fields_data = parsed_data.get("taskFields")
    task_fields = TaskFields(**task_fields_data) if task_fields_data else None

    return AIAssessmentResult(
        ready=bool(parsed_data.get("ready", False)),
        rating=parsed_data.get("rating"),
        message=parsed_data.get("message"),
        questions=normalized_questions,
        finalText=parsed_data.get("finalText"),
        taskFields=task_fields,
    )