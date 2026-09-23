# Искра — frontend + FastAPI backend

В проекте frontend и backend находятся рядом:

```text
HackAlem/
├── frontend/   # Next.js + TypeScript + Tailwind
└── backend/    # Python + FastAPI + OpenAI SDK
```

## Запуск backend (PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# вставьте свой OPENAI_API_KEY и промпты в backend/app/services/ai_service.py
uvicorn app.main:app --reload --port 8000
```

## Запуск frontend (во втором окне PowerShell)

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Frontend отправляет первый запрос, получает вопросный блок, отправляет ответы следующими запросами и ждёт `ready: true` перед экраном редактирования и публикации. Подробности контрактов запросов есть в `frontend/README.md`, backend-маршрутов — в `backend/README.md`.

Черновики и опубликованные задачи в текущем FastAPI прототипе хранятся в памяти и очистятся при перезапуске backend. До реального запуска добавьте базу данных и авторизацию владельцев.

## Проверки перед коммитом

```powershell
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run build
cd ..\backend
pip install -r requirements-dev.txt
ruff format --check app tests
ruff check app tests
pytest -q
```

`.gitignore` исключает ключи, виртуальные окружения, зависимости, сборки и локальные архивы. Настройки форматирования находятся в `.editorconfig`, `frontend/.prettierrc.json` и `backend/pyproject.toml`.
