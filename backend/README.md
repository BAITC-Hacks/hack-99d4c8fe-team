# FastAPI backend

## Локальный запуск (PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Добавьте свой `OPENAI_API_KEY` в `.env`, вставьте промпты в `app/services/ai_service.py`, затем:

```powershell
uvicorn app.main:app --reload --port 8000
```

Проверка: http://localhost:8000/api/health и http://localhost:8000/docs.

Frontend на `http://localhost:3000` уже использует эти маршруты:

- `POST /api/task-drafts` — первый запрос; OpenAI возвращает первый блок вопросов.
- `POST /api/task-drafts/{draft_id}/answers` — ответы; OpenAI оценивает полноту, присылает следующий блок либо `ready: true` и подготовленную карточку.
- `POST /api/task-drafts/{draft_id}/publish` — ручное подтверждение публикации после готовности.
- `GET /api/tasks` — общий список опубликованных задач.
- `DELETE /api/tasks/{task_id}` — удаление карточки (добавьте проверку владельца через авторизацию до production).

Промпты должны возвращать JSON-объекты, соответствующие моделям в `app/schemas.py`. Черновики и задачи сейчас хранятся в памяти процесса: добавьте базу данных и авторизацию для постоянного хранения и проверки прав владельца перед реальным запуском.

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

- `503: Не задан OPENAI_API_KEY` — проверьте, что `backend/.env` создан и содержит ключ; после редактирования перезапустите Uvicorn.
- `502: OpenAI отклонил API-ключ` — ключ неверный, отозван или содержит лишние кавычки/пробелы.
- `503: OpenAI временно ограничил запрос...` — проверьте лимит запросов и доступность биллинга проекта.
- `502: Некорректный ответ модели` — промпт должен возвращать JSON и имена полей из `app/schemas.py`; markdown fences и короткое вступление обрабатываются.
- `502: Ошибка OpenAI API` — подробный ответ SDK находится в окне PowerShell, где запущен Uvicorn.

Проверьте конфигурацию сервера отдельно: откройте http://localhost:8000/docs, выполните `GET /api/health`, затем проверьте `POST /api/task-drafts` с теми же начальными данными.
