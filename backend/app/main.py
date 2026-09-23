import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, AuthenticationError, OpenAIError, RateLimitError

from app.schemas import AnswerRoundRequest, PublishDraftRequest, StartDraftRequest
from app.services.ai_service import assess_answers, generate_questions

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="Iskra API", version="0.1.0")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Демонстрационное хранилище. Для постоянных данных замените на БД.
drafts: dict[str, dict[str, Any]] = {}
tasks: dict[str, dict[str, Any]] = {}


def _model_error(exc: Exception) -> HTTPException:
    logger.exception("AI request failed", exc_info=exc)

    if isinstance(exc, RuntimeError) and "OPENAI_API_KEY" in str(exc):
        return HTTPException(
            status_code=503,
            detail=(
                "Не задан OPENAI_API_KEY. Создайте backend/.env на основе .env.example "
                "и перезапустите FastAPI."
            ),
        )
    if isinstance(exc, AuthenticationError):
        return HTTPException(
            status_code=502,
            detail="OpenAI отклонил API-ключ. Проверьте OPENAI_API_KEY в backend/.env.",
        )
    if isinstance(exc, RateLimitError):
        return HTTPException(
            status_code=503,
            detail=(
                "OpenAI временно ограничил запрос или исчерпана квота проекта. "
                "Проверьте лимиты и биллинг OpenAI."
            ),
        )
    if isinstance(exc, APIConnectionError):
        return HTTPException(
            status_code=502,
            detail="Backend не смог подключиться к OpenAI. Проверьте интернет-соединение сервера.",
        )
    if isinstance(exc, OpenAIError):
        return HTTPException(status_code=502, detail=f"Ошибка OpenAI API: {exc}")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=502, detail=f"Некорректный ответ модели: {exc}")
    return HTTPException(
        status_code=500,
        detail="Внутренняя ошибка backend. Подробности записаны в консоль FastAPI.",
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/task-drafts")
def create_draft(payload: StartDraftRequest) -> dict[str, Any]:
    draft_id = str(uuid.uuid4())
    draft = {
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "answers": [],
        "ready": False,
    }
    try:
        generated = generate_questions(draft, 1)
    except Exception as exc:
        raise _model_error(exc) from exc
    if not generated.questions:
        raise HTTPException(status_code=502, detail="OpenAI не вернул вопросы для первого блока.")
    drafts[draft_id] = draft
    return {"draftId": draft_id, "questions": [q.model_dump() for q in generated.questions]}


@app.post("/api/task-drafts/{draft_id}/answers")
def answer_round(draft_id: str, payload: AnswerRoundRequest) -> dict[str, Any]:
    draft = drafts.get(draft_id)
    if not draft:
        raise HTTPException(
            status_code=404, detail="Черновик не найден или сервер был перезапущен."
        )
    latest = [answer.model_dump() for answer in payload.answers]
    answer_record = {"round": payload.round, "answers": latest}
    try:
        result = assess_answers(draft, payload.round, latest)
        # Каждый черновик проходит три блока минимум. Если AI признал идею
        # готовой раньше, всё равно запрашиваем следующий блок уточнений.
        if result.ready and payload.round < 3:
            next_questions = generate_questions(
                {**draft, "answers": [*draft["answers"], answer_record]}, payload.round + 1
            )
            result = result.model_copy(
                update={
                    "ready": False,
                    "questions": next_questions.questions,
                    "message": "Ответьте на следующий обязательный блок уточнений.",
                }
            )
        if result.ready and result.rating is None:
            raise ValueError("При ready=true модель должна вернуть rating от 0 до 100.")
    except Exception as exc:
        raise _model_error(exc) from exc
    draft["answers"].append(answer_record)
    draft["ready"] = result.ready
    if result.ready:
        draft["finalText"] = result.finalText or ""
        draft["taskFields"] = (result.taskFields or {}).model_dump() if result.taskFields else {}
        draft["rating"] = result.rating
    return result.model_dump(exclude_none=True)


@app.post("/api/task-drafts/{draft_id}/publish")
def publish_draft(draft_id: str, payload: PublishDraftRequest) -> dict[str, Any]:
    draft = drafts.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Черновик не найден.")
    if not draft.get("ready"):
        raise HTTPException(status_code=409, detail="Задача ещё не получила ready=true от модели.")
    task_id = str(uuid.uuid4())
    fields = payload.fields.model_dump()
    fields["context"] = payload.finalText
    rating = draft.get("rating")
    if rating is None:
        rating = 0
    task = {
        **fields,
        "id": task_id,
        "author": "Создатель",
        "category": payload.category,
        "rating": rating,
        "published": True,
        "responses": [],
    }
    tasks[task_id] = task
    return {"task": task, "useGeneratedText": payload.useGeneratedText}


@app.get("/api/tasks")
def list_tasks() -> dict[str, list[dict[str, Any]]]:
    # Опубликованный каталог доступен всем посетителям.
    public_items = []
    for task in tasks.values():
        item = {**task, "author": "Автор задачи"}
        public_items.append(item)
    return {"items": public_items}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str) -> dict[str, bool]:
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    del tasks[task_id]
    return {"deleted": True}
