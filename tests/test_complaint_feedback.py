import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models import Complaint, ComplaintFeedback, User
from app.routers.complaints import router, submit_complaint_feedback
from app.schemas import ComplaintFeedbackCreate, ComplaintFeedbackResponse


def make_user(role: str = "student", user_id: int = 4) -> User:
    return User(
        id=user_id,
        name="Feedback Student",
        email="student@example.com",
        password="hash",
        role=role,
    )


def make_complaint(status: str = "resolved", owner_id: int = 4) -> Complaint:
    return Complaint(
        id=24,
        title="Fixed sink",
        description="Sink was repaired",
        category="Plumbing",
        priority="medium",
        status=status,
        location="Hall",
        student_id=owner_id,
    )


class ComplaintFeedbackTests(unittest.TestCase):
    def test_ratings_one_through_five_are_valid(self) -> None:
        for rating in range(1, 6):
            with self.subTest(rating=rating):
                self.assertEqual(ComplaintFeedbackCreate(rating=rating).rating, rating)

    def test_ratings_outside_one_through_five_are_rejected(self) -> None:
        for rating in (0, 6):
            with self.subTest(rating=rating):
                with self.assertRaises(ValidationError):
                    ComplaintFeedbackCreate(rating=rating)

    def test_owner_can_submit_feedback_for_resolved_complaint(self) -> None:
        db = Mock()
        db.scalar.side_effect = [make_complaint(), None]
        db.refresh.side_effect = lambda feedback: (
            setattr(feedback, "id", 11),
            setattr(feedback, "created_at", datetime.now(timezone.utc)),
        )
        data = ComplaintFeedbackCreate(rating=5, comment="Thank you")

        result = submit_complaint_feedback(24, data, make_user(), db)

        self.assertIsInstance(result, ComplaintFeedback)
        self.assertEqual(result.complaint_id, 24)
        self.assertEqual(result.student_id, 4)
        self.assertEqual(result.rating, 5)
        self.assertEqual(result.comment, "Thank you")
        db.commit.assert_called_once()
        response = ComplaintFeedbackResponse.model_validate(result)
        self.assertNotIn("password", response.model_dump())

    def test_feedback_comment_is_optional(self) -> None:
        self.assertIsNone(ComplaintFeedbackCreate(rating=3).comment)

    def test_non_owner_cannot_submit_feedback(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as raised:
            submit_complaint_feedback(
                24,
                ComplaintFeedbackCreate(rating=4),
                make_user(user_id=9),
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        query = db.scalar.call_args.args[0]
        self.assertIn("complaints.student_id", str(query))
        self.assertEqual(query.compile().params["student_id_1"], 9)
        db.add.assert_not_called()

    def test_feedback_requires_resolved_or_closed_complaint(self) -> None:
        db = Mock()
        db.scalar.return_value = make_complaint(status="in_progress")

        with self.assertRaises(HTTPException) as raised:
            submit_complaint_feedback(
                24, ComplaintFeedbackCreate(rating=4), make_user(), db
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(db.scalar.call_count, 1)
        db.add.assert_not_called()

    def test_duplicate_feedback_is_rejected(self) -> None:
        db = Mock()
        db.scalar.side_effect = [make_complaint(), ComplaintFeedback(id=2)]

        with self.assertRaises(HTTPException) as raised:
            submit_complaint_feedback(
                24, ComplaintFeedbackCreate(rating=4), make_user(), db
            )

        self.assertEqual(raised.exception.status_code, 409)
        db.add.assert_not_called()

    def test_database_duplicate_race_rolls_back_and_returns_conflict(self) -> None:
        db = Mock()
        db.scalar.side_effect = [make_complaint(), None]
        db.commit.side_effect = IntegrityError("insert feedback", {}, Exception())

        with self.assertRaises(HTTPException) as raised:
            submit_complaint_feedback(
                24, ComplaintFeedbackCreate(rating=4), make_user(), db
            )

        self.assertEqual(raised.exception.status_code, 409)
        db.rollback.assert_called_once()

    def test_only_students_can_submit_feedback(self) -> None:
        route = next(
            route for route in router.routes
            if route.path == "/{complaint_id}/feedback"
        )
        role_dependency = route.dependant.dependencies[0].call
        self.assertEqual(role_dependency(make_user()).role, "student")
        for role in ("admin", "maintenance"):
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as raised:
                    role_dependency(make_user(role=role))
                self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
