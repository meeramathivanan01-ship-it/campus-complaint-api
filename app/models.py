from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="student")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    complaints: Mapped[list[Complaint]] = relationship(
        back_populates="student",
        foreign_keys="Complaint.student_id",
    )
    assigned_complaints: Mapped[list[Complaint]] = relationship(
        back_populates="assigned_maintenance",
        foreign_keys="Complaint.assigned_maintenance_id",
    )
    submitted_feedback: Mapped[list[ComplaintFeedback]] = relationship(
        back_populates="student",
    )


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        Index("ix_complaints_student_id_id", "student_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_maintenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    student: Mapped[User] = relationship(
        back_populates="complaints",
        foreign_keys=[student_id],
    )
    assigned_maintenance: Mapped[User | None] = relationship(
        back_populates="assigned_complaints",
        foreign_keys=[assigned_maintenance_id],
    )
    feedback: Mapped[ComplaintFeedback | None] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ComplaintFeedback(Base):
    __tablename__ = "complaint_feedback"
    __table_args__ = (
        UniqueConstraint("complaint_id", name="uq_feedback_complaint_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    complaint: Mapped[Complaint] = relationship(back_populates="feedback")
    student: Mapped[User] = relationship(back_populates="submitted_feedback")
