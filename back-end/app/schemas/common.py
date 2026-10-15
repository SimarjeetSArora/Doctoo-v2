from typing import Annotated

import phonenumbers
from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, StringConstraints

from app.models import Salutation

# Emails are compared case-insensitively, so always store them lowercase.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]

# A single name part (first / middle / last): any script, but no digits.
PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=r"^[^0-9]+$"),
]
OptionalPersonName = Annotated[PersonName | None, BeforeValidator(lambda v: v or None)]

_MOBILE_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,  # e.g. US/Canada numbers
}


def normalize_phone(value: str) -> str:
    """Validates a number that includes its country code; returns E.164, e.g. +919876543210."""
    try:
        number = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Enter the number with its country code, e.g. +91 98765 43210") from exc
    if not phonenumbers.is_valid_number(number):
        raise ValueError("This doesn't look like a valid phone number")
    # Must be able to receive an SMS/WhatsApp OTP later, so landlines are rejected.
    if phonenumbers.number_type(number) not in _MOBILE_TYPES:
        raise ValueError("Please enter a mobile number")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=25), AfterValidator(normalize_phone)
]


class PersonDetails(BaseModel):
    """Name and contact number for a staff account (used at sign-up and when accepting invites)."""

    salutation: Salutation
    first_name: PersonName
    middle_name: OptionalPersonName = None
    last_name: PersonName
    phone: Phone
