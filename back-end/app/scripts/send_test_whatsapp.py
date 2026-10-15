"""Send one test WhatsApp message right now (the login-code template, code 123456).

Usage (from back-end/, with the venv active):
    python -m app.scripts.send_test_whatsapp +919876543210
"""

import asyncio
import sys

from app.core.config import get_settings
from app.schemas.common import normalize_phone
from app.services.whatsapp import WhatsAppMessage, WhatsAppTemplate, get_whatsapp_sender


async def main(number: str) -> int:
    settings = get_settings()
    print(f"WhatsApp backend: {settings.whatsapp_backend}")
    try:
        to = normalize_phone(number)
    except ValueError as exc:
        print(f"Invalid number: {exc}")
        return 1
    message = WhatsAppMessage(
        to=to, template=WhatsAppTemplate.LOGIN_CODE, params={"code": "123456"}
    )
    print(f"Sending to {to}: {message.render()}")
    try:
        await get_whatsapp_sender().send(message)
    except Exception as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        if settings.whatsapp_backend == "msg91":
            print(
                "\nMSG91 WhatsApp checklist:\n"
                "  - MSG91_AUTH_KEY is set, and MSG91_WHATSAPP_NUMBER is your connected number\n"
                f"  - a template named '{settings.msg91_whatsapp_login_template}' is APPROVED\n"
                "  - compare with the sample request MSG91 shows for that template"
            )
        return 1
    where = (
        "the Mailpit inbox (http://localhost:8025)"
        if settings.whatsapp_backend == "mailpit"
        else f"WhatsApp on {to}"
    )
    print(f"\nSent. Check {where}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(asyncio.run(main(sys.argv[1])))
