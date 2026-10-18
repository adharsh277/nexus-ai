# Nexus AI: Phase 1 (Foundation & Google Gemini AI Assistant)

A personal automation assistant with an intelligent chat interface powered by Google Gemini, persistent conversation history backed by PostgreSQL, task management, and a modern responsive React frontend.

**Stack:**
- **Frontend:** React + Vite + Tailwind CSS v4 + React Router
- **Backend:** FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + official Google Gen AI SDK (`google-genai`)
- **Database:** PostgreSQL (with psycopg 3 driver)
- **Containerization:** Docker & Docker Compose (optional / production-ready)

---

## 1. Prerequisites
- **Python:** 3.12+ (tested with Python 3.13)
- **Node.js:** 20+ (tested with Node 24 and npm 11)
- **Database:** PostgreSQL 16+ running locally or in Docker
- **AI Provider Key:** Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

---

## 2. Environment Configuration

Copy the template to `.env`:
```bash
cp .env.example .env
```

Ensure the following variables are set in `.env`:
```env
# PostgreSQL
DATABASE_URL=postgresql+psycopg://postgres:<YOUR_PASSWORD>@localhost:5432/nexus
TEST_DATABASE_URL=postgresql+psycopg://postgres:<YOUR_PASSWORD>@localhost:5432/nexus_test

# AI & LLM Settings
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=30.0
LLM_MAX_HISTORY_MESSAGES=20

# Frontend & CORS
FRONTEND_ORIGIN=http://localhost:5173
VITE_API_URL=http://localhost:8000
```

---

## 3. Running Locally (Without Docker)

### Step 3.1: Prepare PostgreSQL Database
If using local PostgreSQL on Windows:
```bash
# Connect with psql and create the app database:
psql -U postgres
CREATE DATABASE nexus;
CREATE DATABASE nexus_test;
\q
```

### Step 3.2: Start Backend
```bash
cd backend

# Activate existing virtualenv:
.\.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

# Apply Alembic database migrations:
alembic upgrade head

# Seed default local user:
python -m app.seed

# Launch FastAPI development server:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API is available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### Step 3.3: Start Frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 4. Running with Docker Compose
```bash
docker compose up --build
```
On startup the backend automatically waits for Postgres to be healthy, applies Alembic migrations, seeds the default user, and starts Uvicorn with reload.

---

## 5. Running Tests

### Backend Tests (Automated with MockProvider)
The test suite utilizes a deterministic `MockProvider` so tests run offline without consuming live Gemini API quota or requiring network access:
```bash
# Set test database (Postgres or fast local SQLite):
cmd /c "set TEST_DATABASE_URL=sqlite+pysqlite:///test_nexus.db && backend\.venv\Scripts\pytest.exe backend/tests"
```

### Frontend Tests (Vitest + React Testing Library)
```bash
cd frontend
npm test
```

---

## 6. Architecture & Endpoints

### LLM Provider Abstraction (`backend/app/services/llm/`)
- `base.py`: Defines `BaseLLMProvider`, message structures, and standard exceptions (`LLMAuthError`, `LLMRateLimitError`, `LLMTimeoutError`, `LLMUnavailableError`).
- `gemini.py`: Integrates `google-genai` SDK using `gemini-2.5-flash`, managing turn-based conversational context and system instructions.
- `mock.py`: Zero-dependency provider for deterministic unit testing.
- `registry.py`: Lightweight custom tool registry interface ready for Phase 2 tool bindings.
- `factory.py`: Resolves provider based on `LLM_PROVIDER`.

### Core API Endpoints (`/api` and `/api/v1`)
- `GET /health`: Health status of database and configured LLM provider.
- `GET /tasks`, `POST /tasks`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `POST /tasks/{id}/complete`: Task management.
- `GET /conversations`, `POST /conversations`: Conversations management.
- `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages`: Message exchange.
- `POST /reminders`, `GET /reminders`: Reminder creation and list with status/search filtering.
- `GET /reminders/{id}`, `PATCH /reminders/{id}`, `DELETE /reminders/{id}`: Reminder CRUD.
- `POST /reminders/{id}/complete`, `POST /reminders/{id}/cancel`: Reminder completion and cancellation.
- `GET /notifications`, `GET /notifications/unread-count`: In-app notification delivery.
- `PATCH /notifications/{id}/read`, `POST /notifications/mark-all-read`: Notification reading.

### Reminder Background Scheduler & Concurrency
- Integrated into FastAPI lifespan (`REMINDER_POLL_INTERVAL_SECONDS=10.0`).
- **Restart-Safe**: Overdue pending reminders are notified on reboot.
- **Concurrency**: PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` guarantees zero duplicate notifications across multiple workers or replicas.