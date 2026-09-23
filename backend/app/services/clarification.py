"""Keep provider selection on the server, never in the browser."""

import logging
import os
from collections.abc import Callable
from typing import Any

from app.schemas import AIAssessmentResult, AIQuestionsResult
from app.services.ai_service import assess_answers as assess_with_openai
from app.services.ai_service import generate_questions as generate_with_openai
from app.services.demo_service import assess_demo_answers, generate_demo_questions

logger = logging.getLogger(__name__)


def _run[Result](openai_call: Callable[[], Result], demo_call: Callable[[], Result]) -> Result:
    mode = os.getenv("AI_MODE", "auto").strip().lower()
    if mode == "demo" or (mode == "auto" and not os.getenv("OPENAI_API_KEY")):
        return demo_call()
    if mode not in {"auto", "openai"}:
        raise ValueError("AI_MODE должен быть auto, demo или openai.")
    if mode == "openai":
        return openai_call()
    try:
        return openai_call()
    except Exception:
        logger.exception("OpenAI unavailable; using built-in clarification flow")
        return demo_call()


def generate_questions(draft: dict[str, Any], round_number: int) -> AIQuestionsResult:
    def from_openai() -> AIQuestionsResult:
        result = generate_with_openai(draft, round_number)
        if not result.questions:
            raise ValueError("Модель не вернула вопросов.")
        return result

    return _run(
        from_openai,
        lambda: generate_demo_questions(draft, round_number),
    )


def assess_answers(
    draft: dict[str, Any], round_number: int, answers: list[dict[str, str]]
) -> AIAssessmentResult:
    def from_openai() -> AIAssessmentResult:
        result = assess_with_openai(draft, round_number, answers)
        if result.ready and result.rating is None:
            raise ValueError("Модель не вернула рейтинг.")
        if not result.ready and not result.questions:
            raise ValueError("Модель не вернула следующий блок вопросов.")
        return result

    return _run(
        from_openai,
        lambda: assess_demo_answers(draft, round_number, answers),
    )
