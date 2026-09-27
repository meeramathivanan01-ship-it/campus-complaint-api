from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _require_non_whitespace(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        raise ValueError("must not be empty or whitespace-only")
    return value


NonBlankString = Annotated[
    str,
    BeforeValidator(_require_non_whitespace),
    Field(min_length=1),
]
EmailString = Annotated[
    NonBlankString,
    Field(
        pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
    ),
]


class UserBase(BaseModel):
    name: NonBlankString
    email: EmailString


class UserCreate(UserBase):
    password: NonBlankString


class ComplaintBase(BaseModel):
    title: NonBlankString
    description: NonBlankString
    category: NonBlankString
    priority: NonBlankString
    location: NonBlankString


class ComplaintCreate(ComplaintBase):
    pass


class ComplaintResponse(ComplaintBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    student_id: int
    created_at: datetime
    resolved_at: datetime | None
