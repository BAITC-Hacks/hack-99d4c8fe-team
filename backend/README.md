# FastAPI backend

## Локальный запуск (PowerShell)

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# .env не обязателен для работы без OpenAI
```

По умолчанию ключ не нужен: `AI_MODE=auto` запускает встроенные вопросы. Чтобы включить нейросеть, укажите **серверный** `OPENAI_API_KEY` в `.env` и вставьте промпты в `app/services/ai_service.py`. Затем:

```powershell
uvicorn app.main:app --reload --port 8000
```

Проверка: http://localhost:8000/api/health и http://localhost:8000/docs.

Frontend на `http://localhost:3000` уже использует эти маршруты:

- `POST /api/task-drafts` — первый блок вопросов (OpenAI или встроенный сценарий).
- `POST /api/task-drafts/{draft_id}/answers` — ответы и следующий блок либо `ready: true` с карточкой.
- `POST /api/task-drafts/{draft_id}/publish` — ручное подтверждение публикации после готовности.
- `GET /api/tasks` — общий список опубликованных задач.
- `PATCH /api/tasks/{task_id}` и `DELETE /api/tasks/{task_id}` — редактирование/удаление только в браузере автора.
- `POST /api/tasks/{task_id}/responses` — отправка предложения команды.
- `PATCH /api/tasks/{task_id}/responses/{response_id}` — решение автора вручную.

Промпты должны возвращать JSON-объекты, соответствующие моделям в `app/schemas.py`. Черновики, задачи и предложения сохраняются в SQLite по `DATABASE_PATH` (по умолчанию `backend/data/iskra.db`). В Docker Compose используется постоянный volume. Владелец определяется закрытым cookie браузера; для учётных записей и доступа с другого устройства потребуется полноценная регистрация.

## Проверки для разработки

Установите инструменты разработчика и запустите проверки:

```powershell
pip install -r requirements-dev.txt
ruff format --check app tests
ruff check app tests
pytest -q
```

## Если frontend показывает ошибку от backend/OpenAI

Frontend выводит FastAPI-поле `detail`, а backend печатает traceback в консоль:

- `503: На сервере не настроен OPENAI_API_KEY` — режим `openai` требует серверный ключ; режим `auto` работает без него.
- `502: Серверный ключ OpenAI отклонён` — ключ неверный или отозван.
- `503: OpenAI временно ограничил запрос...` — проверьте лимит запросов и доступность биллинга проекта.
- `502: Неверный ответ модели` — промпт должен возвращать JSON и имена полей из `app/schemas.py`.
- `500` — смотрите traceback в консоли FastAPI или `docker compose logs --tail=100 backend`, а также проверьте доступность директории `DATABASE_PATH` для записи.

Проверьте конфигурацию сервера отдельно: откройте http://localhost:8000/docs, выполните `GET /api/health`, затем проверьте `POST /api/task-drafts` с теми же начальными данными.
