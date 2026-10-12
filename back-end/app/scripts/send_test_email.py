"""Send one test email right now, using the settings in .env, and report any error.

Usage (from back-end/, with the venv active):
    python -m app.scripts.send_test_email you@example.com
"""

import asyncio
import sys

from app.core.config import get_settings
from app.services.email import EmailMessage, get_email_sender


async def main(to: str) -> int:
    settings = get_settings()
    print(f"Backend: {settings.email_backend}")
    if settings.email_backend == "smtp":
        print(
            f"Server:  {settings.smtp_host}:{settings.smtp_port} ({settings.smtp_security}), "
            f"user: {settings.smtp_username or '(none)'}"
        )
    try:
        await get_email_sender().send(
            EmailMessage(
                to=to,
                subject="Doctoo test email",
                body="If you can read this, Doctoo's email settings work.",
            )
        )
    except Exception as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        if "gmail" in settings.smtp_host:
            print(
                "\nGmail checklist:\n"
                "  - SMTP_USERNAME is your full Gmail address\n"
                "  - SMTP_PASSWORD is a 16-character App Password (not your normal password),\n"
                "    typed without spaces; create one at https://myaccount.google.com/apppasswords\n"
                "  - 2-Step Verification is ON for that Google account\n"
                "  - Gmail sometimes just disconnects on a bad login instead of saying why"
            )
        return 1
    print(f"\nSent to {to}. Check the inbox (and the spam folder).")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(asyncio.run(main(sys.argv[1])))
