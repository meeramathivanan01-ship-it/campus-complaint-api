import unittest
from datetime import datetime
from unittest.mock import Mock

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import Complaint, ComplaintFeedback, User
from app.routers.complaints import router, update_complaint_status
from app.schemas import ComplaintStatusUpdate, ComplaintUpdate


def user_with_role(role: str) -> User:
    return User(
        id=1,
        name="Test User",
        email="test@example.com",
        password="hash",
        role=role,
    )


class ComplaintStatusWorkflowTests(unittest.TestCase):
    def test_valid_status_values_are_accepted(self) -> None:
        self.assertEqual(
            ComplaintStatusUpdate(status="in_progress").status,
            "in_progress",
        )

    def test_invalid_status_values_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ComplaintStatusUpdate(status="invented")

    def test_status_cannot_be_changed_through_student_complaint_update(self) -> None:
        with self.assertRaises(ValidationError):
            ComplaintUpdate(title="Updated", status="resolved")

    def test_admin_can_advance_status_and_resolution_sets_timestamp(self) -> None:
        complaint = Complaint(
            id=12,
            title="Broken light",
            description="Light is out",
            category="Electrical",
            priority="medium",
            status="in_progress",
            location="Library",
            student_id=1,
        )
        db = Mock()
        db.scalar.return_value = complaint

        result = update_complaint_status(
            12,
            ComplaintStatusUpdate(status="resolved"),
            user_with_role("admin"),
            db,
        )

        self.assertIs(result, complaint)
        self.assertEqual(complaint.status, "resolved")
        self.assertIsInstance(complaint.resolved_at, datetime)
        db.commit.assert_called_once()

    def test_complete_status_sequence_preserves_resolution_timestamp(self) -> None:
        complaint = Complaint(
            id=12,
            title="Broken light",
            description="Light is out",
            category="Electrical",
            priority="medium",
            status="pending",
            location="Library",
            student_id=1,
        )
        db = Mock()
        db.scalar.side_effect = [
            complaint,
            complaint,
            complaint,
            complaint,
            ComplaintFeedback(id=1, complaint_id=12, student_id=1, rating=5),
        ]
        admin = user_with_role("admin")

        update_complaint_status(12, ComplaintStatusUpdate(status="in_progress"), admin, db)
        self.assertEqual(complaint.status, "in_progress")
        self.assertIsNone(complaint.resolved_at)

        update_complaint_status(12, ComplaintStatusUpdate(status="resolved"), admin, db)
        resolved_at = complaint.resolved_at
        self.assertIsInstance(resolved_at, datetime)

        update_complaint_status(12, ComplaintStatusUpdate(status="closed"), admin, db)
        self.assertEqual(complaint.status, "closed")
        self.assertEqual(complaint.resolved_at, resolved_at)
        self.assertEqual(db.commit.call_count, 3)

    def test_admin_cannot_close_resolved_complaint_without_feedback(self) -> None:
        complaint = Complaint(
            id=12,
            title="Broken light",
            description="Light is out",
            category="Electrical",
            priority="medium",
            status="resolved",
            location="Library",
            student_id=1,
        )
        db = Mock()
        db.scalar.side_effect = [complaint, None]

        with self.assertRaises(HTTPException) as raised:
            update_complaint_status(
                12,
                ComplaintStatusUpdate(status="closed"),
                user_with_role("admin"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(complaint.status, "resolved")
        db.commit.assert_not_called()

    def test_maintenance_can_advance_only_to_resolved(self) -> None:
        complaint = Complaint(
            id=12,
            title="Broken light",
            description="Light is out",
            category="Electrical",
            priority="medium",
            status="pending",
            location="Library",
            student_id=1,
            assigned_maintenance_id=1,
        )
        db = Mock()
        db.scalar.side_effect = [complaint, complaint, complaint, None]
        maintenance = user_with_role("maintenance")

        update_complaint_status(
            12, ComplaintStatusUpdate(status="in_progress"), maintenance, db
        )
        self.assertEqual(complaint.status, "in_progress")
        self.assertIsNone(complaint.resolved_at)

        update_complaint_status(
            12, ComplaintStatusUpdate(status="resolved"), maintenance, db
        )
        self.assertEqual(complaint.status, "resolved")
        self.assertIsInstance(complaint.resolved_at, datetime)

        with self.assertRaises(HTTPException) as raised:
            update_complaint_status(
                12, ComplaintStatusUpdate(status="closed"), maintenance, db
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(complaint.status, "resolved")
        self.assertEqual(db.commit.call_count, 2)

    def test_invalid_transition_is_rejected(self) -> None:
        complaint = Complaint(
            id=12,
            title="Broken light",
            description="Light is out",
            category="Electrical",
            priority="medium",
            status="pending",
            location="Library",
            student_id=1,
        )
        db = Mock()
        db.scalar.return_value = complaint

        with self.assertRaises(HTTPException) as raised:
            update_complaint_status(
                12,
                ComplaintStatusUpdate(status="closed"),
                user_with_role("admin"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 400)
        db.commit.assert_not_called()

    def test_admin_and_assigned_maintenance_roles_are_allowed_on_status_route(self) -> None:
        route = next(
            route for route in router.routes
            if route.path == "/{complaint_id}/status"
        )
        role_dependency = route.dependant.dependencies[0].call

        admin = user_with_role("admin")
        self.assertIs(role_dependency(admin), admin)
        maintenance = user_with_role("maintenance")
        self.assertIs(role_dependency(maintenance), maintenance)
        for role in ("student",):
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as raised:
                    role_dependency(user_with_role(role))
                self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
