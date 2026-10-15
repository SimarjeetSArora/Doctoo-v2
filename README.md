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

- Owners sign up at `/register` (title, first/middle/last name, mobile number, email verified with a
  6-digit code, password). Staff join through invitations sent by **email or SMS**.
- Log in with **email or mobile number**, using a **password or a one-time code** (emailed or texted).
  Mobile numbers are unique per account and stored in international format (`+919876543210`).
- One-time codes: 6 digits, valid 10 minutes, 5 wrong attempts, 60 s before resend, max 5 per hour,
  single use, stored only as a keyed hash.
- Access token (30 min, kept in memory) + refresh token (14 days, httpOnly cookie, stored hashed in `user_sessions`).
- Every clinic request sends `X-Clinic-Id`; the backend checks membership and role (`app/api/deps.py`).
- Emails (password reset, invitations) are sent over **SMTP** in the background, after the response.

## SMS

| Setting `SMS_BACKEND` | Where texts go |
|---|---|
| `mailpit` (development default) | The **Mailpit inbox at http://localhost:8025**, addressed to `sms+<number>@doctoo.local` |
| `console` | Printed in the backend terminal |
| `msg91` | Real SMS through **MSG91** (production) |

**Check SMS settings** (sends a sample login-code SMS right away and shows any error):
```powershell
cd back-end
.venv\Scripts\activate
python -m app.scripts.send_test_sms +919876543210
```

### SMS with MSG91 (India)
Indian law (TRAI DLT) only allows business SMS that match **pre-approved templates**, sent under an approved
**sender ID**. One-time setup:

1. **Register on a DLT portal** (Jio, Airtel, Vodafone-Idea…) as a business ("Principal Entity") — needs
   PAN + GST or company registration. You get a **PE ID**.
2. **Register a sender ID (header)**, e.g. `DOCTOO` (6 letters), category *Transactional/Service-Implicit*.
3. **Register these two content templates** on DLT. The wording must match exactly; `{#var#}` is a variable:

   | Use | Template text (DLT format) |
   |---|---|
   | Login code | `{#var#} is your Doctoo login code. Valid {#var#} min. Do not share it with anyone.` |
   | Invitation | `{#var#} invited you to join {#var#} on Doctoo as a {#var#}. Accept within {#var#} days: {#var#}` |

4. **In MSG91**: add your DLT PE ID and sender ID, then create the same two SMS templates, naming the
   variables exactly as Doctoo sends them:
   - Login code: `##code## is your Doctoo login code. Valid ##minutes## min. Do not share it with anyone.`
   - Invitation: `##inviter## invited you to join ##clinic## on Doctoo as a ##role##. Accept within ##days## days: ##link##`
5. In `back-end/.env`: `SMS_BACKEND=msg91`, `MSG91_AUTH_KEY=…`, `MSG91_LOGIN_TEMPLATE_ID=…`,
   `MSG91_INVITATION_TEMPLATE_ID=…` (MSG91's template IDs). Restart the backend and run the check command.

Notes: DLT allows at most **30 characters per variable**, so Doctoo trims long names and lets MSG91
**shorten the invitation link** (`MSG91_SHORT_URLS=true`). Newer DLT rules may also require the link's
domain to be **whitelisted** on the DLT portal — use your production domain there.

## WhatsApp with MSG91

Login codes and invitations to a mobile number go on **WhatsApp** (no DLT needed — WhatsApp has its own
template approval by Meta). In development they appear in Mailpit as `whatsapp+<number>@doctoo.local`.

**Check WhatsApp settings** (sends a sample login code right away):
```powershell
python -m app.scripts.send_test_whatsapp +919876543210
```

### Setup
1. **MSG91 → WhatsApp → Onboard**: connect a Meta Business account and a phone number that is **not**
   already used on the WhatsApp app. Set the display name to *Doctoo*.
2. **Create two templates** in MSG91 (language **English**) and wait for Meta to approve them:

   | Name | Category | Content |
   |---|---|---|
   | `doctoo_login_code` | **Authentication** | Meta's fixed text: *"{{1}} is your verification code. For your security, do not share this code."* — tick "Add security recommendation", set expiry **10 minutes**, button **Copy code** |
   | `doctoo_invitation` | **Utility** | `{{1}} invited you to join {{2}} on Doctoo as a {{3}}. Accept within {{4}} days: {{5}}` |

   Sample values for the invitation (Meta asks for them): `Dr. Anita Sharma`, `Sunrise Clinic`, `doctor`, `7`,
   `https://doctoo.in/invite?token=abc123`.
3. In `back-end/.env`: `WHATSAPP_BACKEND=msg91`, `MSG91_AUTH_KEY=…`, `MSG91_WHATSAPP_NUMBER=91…`
   (template names already match). Restart the backend and run the check command.
4. MSG91 shows a **sample API request** for each approved template — if a send fails, compare it with
   `Msg91WhatsAppSender.payload()` in `app/services/whatsapp.py`.

The login page offers **WhatsApp** and/or **SMS** codes depending on what is configured
(`GET /api/v1/auth/options`): until DLT is done, production shows WhatsApp only.

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
