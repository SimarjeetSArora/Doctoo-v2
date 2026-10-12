# Doctoo — Clinic Management System

| Part | Tech |
|---|---|
| Frontend | React + TypeScript + Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Router |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic |
| Database | PostgreSQL 17 (+ Redis 7 for background jobs) — run via Docker |
| Email | SMTP (any provider); Mailpit catches all emails in development |

## First-time setup

**Prerequisites:** Python 3.13+, Node 22+, Docker Desktop.

```bash
# 1. Start the database, Redis and Mailpit (from the project root)
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

## Authentication (clinic staff)

- Email + password. Owners sign up at `/register`; staff join through email invitations.
- Access token (30 min, kept in memory) + refresh token (14 days, httpOnly cookie, stored hashed in `user_sessions`).
- Every clinic request sends `X-Clinic-Id`; the backend checks membership and role (`app/api/deps.py`).
- Emails (password reset, invitations) are sent over **SMTP** in the background, after the response.

## Email

| | Where emails go |
|---|---|
| Development (default) | **Mailpit** — open **http://localhost:8025** to read every email the app sends. Nothing reaches real inboxes. |
| Production | Your provider's SMTP server — set `SMTP_*` and `EMAIL_FROM_*` in `back-end/.env` (examples for Gmail, Zoho, Brevo and Amazon SES are in `.env.example`). |
| No Docker / quick debugging | `EMAIL_BACKEND=console` prints emails in the backend terminal instead. |

If sending fails (wrong password, server down), the request still succeeds and the error is logged in the backend terminal as `Failed to send email ...`.

**Check your email settings** (sends one email immediately and shows any error):
```powershell
cd back-end
.venv\Scripts\activate
python -m app.scripts.send_test_email you@example.com
```

### Using Gmail
1. Turn on **2-Step Verification**: https://myaccount.google.com/security
2. Create an **App Password**: https://myaccount.google.com/apppasswords (name it "Doctoo").
3. In `back-end/.env`: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_SECURITY=starttls`,
   `SMTP_USERNAME=<your Gmail>`, `SMTP_PASSWORD=<16 characters, no spaces>`, `EMAIL_FROM_ADDRESS=` (empty).
4. Restart the backend and run the check command above.

Gmail allows roughly 500 emails/day and always sends as your Gmail address, so it's fine for development and
pilots; move to your own domain (Brevo, Amazon SES, Zoho) before scaling.
