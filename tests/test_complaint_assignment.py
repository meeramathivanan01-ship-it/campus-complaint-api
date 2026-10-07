import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from app.models import Complaint, User
from app.routers.complaints import (
    assign_complaint,
    get_assigned_complaints,
    router,
    update_complaint_status,
)
from app.schemas import ComplaintAssignment, ComplaintStatusUpdate


def make_user(user_id: int, role: str) -> User:
    return User(
        id=user_id,
        name=f"User {user_id}",
        email=f"user{user_id}@example.com",
        password="hash",
        role=role,
    )


def make_complaint(assigned_maintenance_id: int | None = None) -> Complaint:
    return Complaint(
        id=17,
        title="Broken light",
        description="Light is out",
        category="Electrical",
        priority="medium",
        status="pending",
        location="Library",
        student_id=3,
        assigned_maintenance_id=assigned_maintenance_id,
    )


def role_dependency_for(path: str):
    route = next(route for route in router.routes if route.path == path)
    return route.dependant.dependencies[0].call


class ComplaintAssignmentTests(unittest.TestCase):
    def test_admin_can_assign_complaint_to_maintenance_user(self) -> None:
        complaint = make_complaint()
        maintenance_user = make_user(8, "maintenance")
        db = Mock()
        db.scalar.side_effect = [complaint, maintenance_user]

        result = assign_complaint(
            17,
            ComplaintAssignment(maintenance_user_id=8),
            make_user(1, "admin"),
            db,
        )

        self.assertIs(result, complaint)
        self.assertEqual(complaint.assigned_maintenance_id, 8)
        self.assertEqual(complaint.status, "pending")
        db.commit.assert_called_once()

    def test_only_admin_can_assign(self) -> None:
        dependency = role_dependency_for("/{complaint_id}/assign")
        self.assertIs(dependency(make_user(1, "admin")).role, "admin")
        for role in ("student", "maintenance"):
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as raised:
                    dependency(make_user(2, role))
                self.assertEqual(raised.exception.status_code, 403)

    def test_assigning_nonexistent_complaint_fails(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as raised:
            assign_complaint(
                99,
                ComplaintAssignment(maintenance_user_id=8),
                make_user(1, "admin"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(db.scalar.call_count, 1)

    def test_assigning_nonexistent_user_fails(self) -> None:
        db = Mock()
        db.scalar.side_effect = [make_complaint(), None]

        with self.assertRaises(HTTPException) as raised:
            assign_complaint(
                17,
                ComplaintAssignment(maintenance_user_id=99),
                make_user(1, "admin"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        db.commit.assert_not_called()

    def test_assigning_non_maintenance_user_fails(self) -> None:
        db = Mock()
        db.scalar.side_effect = [make_complaint(), make_user(4, "student")]

        with self.assertRaises(HTTPException) as raised:
            assign_complaint(
                17,
                ComplaintAssignment(maintenance_user_id=4),
                make_user(1, "admin"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 400)
        db.commit.assert_not_called()

    def test_maintenance_sees_only_complaints_assigned_to_self(self) -> None:
        db = Mock()
        db.scalars.return_value.all.return_value = []

        self.assertEqual(get_assigned_complaints(make_user(8, "maintenance"), db), [])
        query = db.scalars.call_args.args[0]
        self.assertIn("assigned_maintenance_id", str(query))
        self.assertEqual(query.compile().params["assigned_maintenance_id_1"], 8)

    def test_assigned_complaints_route_rejects_student_and_admin(self) -> None:
        dependency = role_dependency_for("/assigned")
        for role in ("student", "admin"):
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as raised:
                    dependency(make_user(1, role))
                self.assertEqual(raised.exception.status_code, 403)

    def test_assigned_maintenance_can_advance_status(self) -> None:
        complaint = make_complaint(assigned_maintenance_id=8)
        complaint.status = "in_progress"
        db = Mock()
        db.scalar.return_value = complaint

        result = update_complaint_status(
            17,
            ComplaintStatusUpdate(status="resolved"),
            make_user(8, "maintenance"),
            db,
        )

        self.assertIs(result, complaint)
        self.assertEqual(complaint.status, "resolved")
        query = db.scalar.call_args.args[0]
        self.assertIn("assigned_maintenance_id", str(query))
        self.assertEqual(query.compile().params["assigned_maintenance_id_1"], 8)

    def test_unassigned_complaint_cannot_be_updated_by_maintenance(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as raised:
            update_complaint_status(
                17,
                ComplaintStatusUpdate(status="in_progress"),
                make_user(8, "maintenance"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        query = str(db.scalar.call_args.args[0])
        self.assertIn("assigned_maintenance_id", query)
        self.assertEqual(
            db.scalar.call_args.args[0].compile().params[
                "assigned_maintenance_id_1"
            ],
            8,
        )
        db.commit.assert_not_called()

    def test_maintenance_cannot_update_another_users_complaint_status(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as raised:
            update_complaint_status(
                17,
                ComplaintStatusUpdate(status="in_progress"),
                make_user(8, "maintenance"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        query = str(db.scalar.call_args.args[0])
        self.assertIn("assigned_maintenance_id", query)
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
