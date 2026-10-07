from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


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


class UserLogin(BaseModel):
    email: EmailString
    password: NonBlankString


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class ComplaintBase(BaseModel):
    title: NonBlankString
    description: NonBlankString
    category: NonBlankString
    priority: NonBlankString
    location: NonBlankString


class ComplaintCreate(ComplaintBase):
    pass


class ComplaintUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: NonBlankString = None
    description: NonBlankString = None
    category: NonBlankString = None
    priority: NonBlankString = None
    location: NonBlankString = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ComplaintUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for an update.")
        return self


ComplaintStatus = Literal["pending", "in_progress", "resolved", "closed"]


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus


class ComplaintAssignment(BaseModel):
    maintenance_user_id: int = Field(gt=0)


class ComplaintFeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ComplaintFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    rating: int
    comment: str | None
    created_at: datetime


class ComplaintStatsResponse(BaseModel):
    total_complaints: int
    pending_complaints: int
    in_progress_complaints: int
    resolved_complaints: int
    closed_complaints: int
    assigned_complaints: int
    unassigned_complaints: int
    total_feedback: int
    average_rating: float


class ComplaintResponse(ComplaintBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ComplaintStatus
    student_id: int
    assigned_maintenance_id: int | None
    created_at: datetime
    resolved_at: datetime | None
