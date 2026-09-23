import hashlib
import logging
import os
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, AuthenticationError, OpenAIError, RateLimitError

from app import storage
from app.schemas import (
    AnswerRoundRequest,
    PublishDraftRequest,
    ResponseStatusRequest,
    StartDraftRequest,
    TeamResponseRequest,
    UpdateTaskRequest,
)
from app.services.clarification import assess_answers, generate_questions
from app.services.demo_service import POINTS

load_dotenv()
logger = logging.getLogger(__name__)
COOKIE_NAME = "iskra_owner"

app = FastAPI(title="Iskra API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _owner(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    return hashlib.sha256(token.encode()).hexdigest() if token and len(token) >= 32 else None


def _new_owner(request: Request, response: Response) -> str:
    existing = _owner(request)
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
        path="/",
    )
    return hashlib.sha256(token.encode()).hexdigest()


def _owned_draft(draft_id: str, request: Request) -> dict[str, Any]:
    record = storage.get_draft(draft_id)
    if not record:
        raise HTTPException(status_code=404, detail="Черновик не найден.")
    if record[0] != _owner(request):
        raise HTTPException(status_code=403, detail="Черновик принадлежит другому посетителю.")
    return record[1]


def _owned_task(task_id: str, request: Request) -> dict[str, Any]:
    record = storage.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    if record[0] != _owner(request):
        raise HTTPException(status_code=403, detail="Изменять задачу может только её автор.")
    return record[1]


def _score(fields: dict[str, str]) -> int:
    return sum(points for field, points in POINTS.items() if fields.get(field, "").strip())


def _model_error(exc: Exception) -> HTTPException:
    logger.exception("Clarification request failed", exc_info=exc)
    if isinstance(exc, RuntimeError) and "OPENAI_API_KEY" in str(exc):
        return HTTPException(status_code=503, detail="На сервере не настроен OPENAI_API_KEY.")
    if isinstance(exc, AuthenticationError):
        return HTTPException(status_code=502, detail="Серверный ключ OpenAI отклонён.")
    if isinstance(exc, RateLimitError):
        return HTTPException(status_code=503, detail="Временный лимит запросов OpenAI.")
    if isinstance(exc, APIConnectionError):
        return HTTPException(status_code=502, detail="Нет соединения сервера с OpenAI.")
    if isinstance(exc, OpenAIError):
        return HTTPException(status_code=502, detail="Ошибка сервиса генерации.")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=502, detail=f"Неверный ответ модели: {exc}")
    return HTTPException(
        status_code=500, detail="Внутренняя ошибка backend. Смотрите traceback в консоли FastAPI."
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        with storage.connection() as db:
            db.execute("SELECT 1")
    except (OSError, sqlite3.Error) as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="База данных недоступна для записи.") from exc
    return {"status": "ok"}


@app.post("/api/task-drafts")
def create_draft(
    payload: StartDraftRequest, request: Request, response: Response
) -> dict[str, Any]:
    draft_id = str(uuid.uuid4())
    draft = {
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "answers": [],
        "nextRound": 1,
        "ready": False,
    }
    try:
        generated = generate_questions(draft, 1)
    except Exception as exc:
        raise _model_error(exc) from exc
    if not generated.questions:
        raise HTTPException(status_code=502, detail="Не получены вопросы для первого блока.")
    storage.save_draft(draft_id, _new_owner(request, response), draft)
    return {"draftId": draft_id, "questions": [q.model_dump() for q in generated.questions]}


@app.post("/api/task-drafts/{draft_id}/answers")
def answer_round(draft_id: str, payload: AnswerRoundRequest, request: Request) -> dict[str, Any]:
    draft = _owned_draft(draft_id, request)
    if draft["ready"] or payload.round != draft["nextRound"]:
        raise HTTPException(status_code=409, detail="Неверный или уже пройденный блок вопросов.")
    latest = [answer.model_dump() for answer in payload.answers]
    answer_record = {"round": payload.round, "answers": latest}
    try:
        result = assess_answers(draft, payload.round, latest)
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
            raise ValueError("При ready=true требуется rating от 0 до 100.")
    except Exception as exc:
        raise _model_error(exc) from exc
    draft["answers"].append(answer_record)
    draft["ready"] = result.ready
    if result.ready:
        draft["finalText"] = result.finalText or ""
        draft["taskFields"] = result.taskFields.model_dump() if result.taskFields else {}
        draft["rating"] = result.rating
    else:
        draft["nextRound"] = min(payload.round + 1, 3)
    storage.save_draft(draft_id, _owner(request), draft)
    return result.model_dump(exclude_none=True)


@app.post("/api/task-drafts/{draft_id}/publish")
def publish_draft(draft_id: str, payload: PublishDraftRequest, request: Request) -> dict[str, Any]:
    draft = _owned_draft(draft_id, request)
    if not draft.get("ready"):
        raise HTTPException(status_code=409, detail="Задача ещё не прошла уточнение.")
    fields = payload.fields.model_dump()
    fields["context"] = payload.finalText
    if len(fields["title"].strip()) < 3 or len(fields["context"].strip()) < 10:
        raise HTTPException(status_code=422, detail="Укажите название и подробный контекст задачи.")
    task_id = str(uuid.uuid4())
    task = {
        **fields,
        "id": task_id,
        "category": payload.category,
        "rating": _score(fields),
        "published": True,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    storage.save_task(task_id, _owner(request), task)
    storage.delete_draft(draft_id)
    return {"task": {**task, "author": "Вы", "responses": [], "backendManaged": True}}


@app.get("/api/tasks")
def list_tasks(request: Request) -> dict[str, list[dict[str, Any]]]:
    owner = _owner(request)
    items = []
    for task_owner, task in storage.list_tasks():
        own = owner is not None and owner == task_owner
        responses = storage.list_responses(task["id"])
        items.append(
            {
                **task,
                "author": "Вы" if own else "Автор задачи",
                "responses": responses if own else [],
                "responseCount": len(responses),
                "backendManaged": True,
            }
        )
    return {"items": items}


@app.patch("/api/tasks/{task_id}")
def edit_task(task_id: str, payload: UpdateTaskRequest, request: Request) -> dict[str, Any]:
    task = _owned_task(task_id, request)
    fields = payload.fields.model_dump()
    if len(fields["title"].strip()) < 3 or len(fields["context"].strip()) < 10:
        raise HTTPException(status_code=422, detail="Укажите название и подробный контекст задачи.")
    task.update(fields)
    task["rating"] = _score(fields)
    storage.save_task(task_id, _owner(request), task)
    return {"task": task}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, request: Request) -> dict[str, bool]:
    _owned_task(task_id, request)
    storage.delete_task(task_id)
    return {"deleted": True}


@app.post("/api/tasks/{task_id}/responses")
def respond_to_task(task_id: str, payload: TeamResponseRequest) -> dict[str, Any]:
    if not storage.get_task(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    response = {
        **payload.model_dump(),
        "id": str(uuid.uuid4()),
        "status": "pending",
        "createdAt": datetime.now(UTC).isoformat(),
    }
    storage.add_response(response, task_id)
    return {"response": response}


@app.patch("/api/tasks/{task_id}/responses/{response_id}")
def decide_response(
    task_id: str, response_id: str, payload: ResponseStatusRequest, request: Request
) -> dict[str, Any]:
    _owned_task(task_id, request)
    response = storage.update_response(task_id, response_id, payload.status)
    if not response:
        raise HTTPException(status_code=404, detail="Отклик не найден.")
    return {"response": response}
