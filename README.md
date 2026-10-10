# Doctoo — Clinic Management System

| Part | Tech |
|---|---|
| Frontend | React + TypeScript + Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Router |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic |
| Database | PostgreSQL 17 (+ Redis 7 for background jobs) — run via Docker |

## First-time setup

**Prerequisites:** Python 3.13+, Node 22+, Docker Desktop.

```bash
# 1. Start the database and Redis (from the project root)
docker compose up -d

# 2. Backend
cd back-end
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env            # then set SECRET_KEY (see comment inside)
alembic upgrade head              # create/update database tables

# 3. Frontend
cd ../front-end
npm install
```

## Running daily

```bash
docker compose up -d                                   # project root
cd back-end && .venv\Scripts\activate && uvicorn app.main:app --reload   # http://localhost:8000/docs
cd front-end && npm run dev                            # http://localhost:5173
```

## Common commands

| Task | Command (run inside the folder shown) |
|---|---|
| Create a migration after changing models | `back-end`: `alembic revision --autogenerate -m "describe change"` |
| Apply migrations | `back-end`: `alembic upgrade head` |
| Run backend tests | `back-end`: `pytest` |
| Lint / format backend | `back-end`: `ruff check . --fix` and `ruff format .` |
| Add a UI component | `front-end`: `npx shadcn@latest add <name>` |
| Stop database containers | root: `docker compose down` (data is kept) |
