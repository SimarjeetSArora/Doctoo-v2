"""Send one test SMS right now (a login-code template with code 123456) and report any error.

Usage (from back-end/, with the venv active):
    python -m app.scripts.send_test_sms +919876543210
"""

import asyncio
import sys

from app.core.config import get_settings
from app.schemas.common import normalize_phone
from app.services.sms import SmsMessage, SmsTemplate, get_sms_sender


async def main(number: str) -> int:
    settings = get_settings()
    print(f"SMS backend: {settings.sms_backend}")
    try:
        to = normalize_phone(number)
    except ValueError as exc:
        print(f"Invalid number: {exc}")
        return 1
    message = SmsMessage(
        to=to, template=SmsTemplate.LOGIN_CODE, params={"code": "123456", "minutes": "10"}
    )
    print(f"Sending to {to}: {message.render()}")
    try:
        await get_sms_sender().send(message)
    except Exception as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        if settings.sms_backend == "msg91":
            print(
                "\nMSG91 checklist:\n"
                "  - MSG91_AUTH_KEY is the key from MSG91 > Authkey\n"
                "  - MSG91_LOGIN_TEMPLATE_ID is the MSG91 template ID (not the DLT ID)\n"
                "  - the template is DLT-approved and its text matches exactly\n"
                "  - your MSG91 account has SMS credits"
            )
        return 1
    where = "the Mailpit inbox (http://localhost:8025)" if settings.sms_backend == "mailpit" else to
    print(f"\nSent. Check {where}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(asyncio.run(main(sys.argv[1])))
