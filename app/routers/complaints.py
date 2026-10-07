from datetime import datetime, timezone
import logging

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Complaint, ComplaintFeedback, User
from app.schemas import (
    ComplaintCreate,
    ComplaintAssignment,
    ComplaintFeedbackCreate,
    ComplaintFeedbackResponse,
    ComplaintResponse,
    ComplaintStatsResponse,
    ComplaintStatusUpdate,
    ComplaintUpdate,
)
from app.security import require_roles


router = APIRouter(tags=["Complaints"])
logger = logging.getLogger(__name__)
STATUS_TRANSITIONS = {
    "pending": "in_progress",
    "in_progress": "resolved",
    "resolved": "closed",
}


@router.get("/health")
def complaints_health() -> dict[str, str]:
    return {"message": "Complaints router is working."}


@router.get("/", response_model=list[ComplaintResponse])
def get_complaints(
    current_user: User = Depends(require_roles("student", "admin")),
    db: Session = Depends(get_db),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Complaint]:
    query = select(Complaint)
    if current_user.role == "student":
        query = query.where(Complaint.student_id == current_user.id)
    query = query.order_by(Complaint.id.asc()).offset(skip).limit(limit)
    return list(db.scalars(query).all())


@router.get("/assigned", response_model=list[ComplaintResponse])
def get_assigned_complaints(
    current_user: User = Depends(require_roles("maintenance")),
    db: Session = Depends(get_db),
) -> list[Complaint]:
    return list(
        db.scalars(
            select(Complaint).where(
                Complaint.assigned_maintenance_id == current_user.id
            )
        ).all()
    )


@router.get("/stats", response_model=ComplaintStatsResponse)
def get_complaint_stats(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ComplaintStatsResponse:
    complaint_counts = db.execute(
        select(
            func.count(Complaint.id),
            func.count(case((Complaint.status == "pending", 1))),
            func.count(case((Complaint.status == "in_progress", 1))),
            func.count(case((Complaint.status == "resolved", 1))),
            func.count(case((Complaint.status == "closed", 1))),
            func.count(case((Complaint.assigned_maintenance_id.is_not(None), 1))),
        )
    ).one()
    feedback_counts = db.execute(
        select(
            func.count(ComplaintFeedback.id),
            func.avg(ComplaintFeedback.rating),
        )
    ).one()
    total_complaints = complaint_counts[0]
    assigned_complaints = complaint_counts[5]
    return ComplaintStatsResponse(
        total_complaints=total_complaints,
        pending_complaints=complaint_counts[1],
        in_progress_complaints=complaint_counts[2],
        resolved_complaints=complaint_counts[3],
        closed_complaints=complaint_counts[4],
        assigned_complaints=assigned_complaints,
        unassigned_complaints=total_complaints - assigned_complaints,
        total_feedback=feedback_counts[0],
        average_rating=float(feedback_counts[1] or 0),
    )


@router.put("/{complaint_id}/assign", response_model=ComplaintResponse)
def assign_complaint(
    complaint_id: int,
    assignment: ComplaintAssignment,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Complaint:
    complaint = db.scalar(select(Complaint).where(Complaint.id == complaint_id))
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint with id {complaint_id} not found.",
        )

    maintenance_user = db.scalar(
        select(User).where(User.id == assignment.maintenance_user_id)
    )
    if maintenance_user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User with id {assignment.maintenance_user_id} not found.",
        )
    if maintenance_user.role != "maintenance":
        raise HTTPException(
            status_code=400,
            detail="The selected user is not a maintenance user.",
        )

    complaint.assigned_maintenance_id = maintenance_user.id
    db.commit()
    db.refresh(complaint)
    logger.info(
        "Complaint assigned (complaint_id=%s maintenance_user_id=%s)",
        complaint.id,
        maintenance_user.id,
    )
    return complaint


@router.get("/{complaint_id}", response_model=ComplaintResponse)
def get_complaint(
    complaint_id: int,
    current_user: User = Depends(require_roles("student", "admin")),
    db: Session = Depends(get_db),
) -> Complaint:
    query = select(Complaint).where(Complaint.id == complaint_id)
    if current_user.role == "student":
        query = query.where(Complaint.student_id == current_user.id)
    complaint = db.scalar(query)
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint with id {complaint_id} not found.",
        )
    return complaint


@router.post(
    "/{complaint_id}/feedback",
    response_model=ComplaintFeedbackResponse,
    status_code=201,
)
def submit_complaint_feedback(
    complaint_id: int,
    feedback_data: ComplaintFeedbackCreate,
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db),
) -> ComplaintFeedback:
    complaint = db.scalar(
        select(Complaint).where(
            Complaint.id == complaint_id,
            Complaint.student_id == current_user.id,
        )
    )
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint with id {complaint_id} not found.",
        )
    if complaint.status not in ("resolved", "closed"):
        raise HTTPException(
            status_code=409,
            detail="Feedback can only be submitted for resolved or closed complaints.",
        )

    existing_feedback = db.scalar(
        select(ComplaintFeedback).where(
            ComplaintFeedback.complaint_id == complaint_id
        )
    )
    if existing_feedback is not None:
        raise HTTPException(
            status_code=409,
            detail="Feedback has already been submitted for this complaint.",
        )

    feedback = ComplaintFeedback(
        complaint_id=complaint.id,
        student_id=current_user.id,
        rating=feedback_data.rating,
        comment=feedback_data.comment,
    )
    db.add(feedback)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Feedback has already been submitted for this complaint.",
        ) from None
    db.refresh(feedback)
    logger.info(
        "Complaint feedback submitted (complaint_id=%s user_id=%s)",
        complaint.id,
        current_user.id,
    )
    return feedback


@router.put("/{complaint_id}", response_model=ComplaintResponse)
def update_complaint(
    complaint_id: int,
    update_data: ComplaintUpdate,
    current_user: User = Depends(require_roles("student", "admin")),
    db: Session = Depends(get_db),
) -> Complaint:
    query = select(Complaint).where(Complaint.id == complaint_id)
    if current_user.role == "student":
        query = query.where(Complaint.student_id == current_user.id)
    complaint = db.scalar(query)
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint with id {complaint_id} not found.",
        )

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(complaint, field, value)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.put("/{complaint_id}/status", response_model=ComplaintResponse)
def update_complaint_status(
    complaint_id: int,
    status_data: ComplaintStatusUpdate,
    current_user: User = Depends(require_roles("admin", "maintenance")),
    db: Session = Depends(get_db),
) -> Complaint:
    query = select(Complaint).where(Complaint.id == complaint_id)
    if current_user.role == "maintenance":
        query = query.where(
            Complaint.assigned_maintenance_id == current_user.id
        )
    complaint = db.scalar(query)
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint with id {complaint_id} not found.",
        )

    expected_status = STATUS_TRANSITIONS.get(complaint.status)
    if status_data.status != expected_status:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition from '{complaint.status}' "
                f"to '{status_data.status}'."
            ),
        )

    complaint.status = status_data.status
    if complaint.status == "resolved":
        complaint.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(complaint)
    logger.info(
        "Complaint status updated (complaint_id=%s status=%s user_id=%s)",
        complaint.id,
        complaint.status,
        current_user.id,
    )
    return complaint


@router.delete("/{complaint_id}")
def delete_complaint(
    complaint_id: int,
    current_user: User = Depends(require_roles("student", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    query = select(Complaint).where(Complaint.id == complaint_id)
    if current_user.role == "student":
        query = query.where(Complaint.student_id == current_user.id)
    complaint = db.scalar(query)
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint with id {complaint_id} not found.",
        )

    db.delete(complaint)
    db.commit()
    return {"message": f"Complaint with id {complaint_id} deleted successfully."}


@router.post("/", response_model=ComplaintResponse)
def create_complaint(
    complaint_data: ComplaintCreate,
    current_user: User = Depends(require_roles("student", "admin")),
    db: Session = Depends(get_db),
) -> Complaint:
    complaint = Complaint(
        **complaint_data.model_dump(), student_id=current_user.id
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    logger.info(
        "Complaint created (complaint_id=%s user_id=%s)",
        complaint.id,
        current_user.id,
    )
    return complaint
