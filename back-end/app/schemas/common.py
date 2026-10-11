from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints

# Emails are compared case-insensitively, so always store them lowercase.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
