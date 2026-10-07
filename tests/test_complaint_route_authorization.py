import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from app.models import User
from app.routers.complaints import get_complaint, get_complaints, router


def user_with_role(role: str, user_id: int = 1) -> User:
    return User(
        id=user_id,
        name="Test User",
        email="test@example.com",
        password="hash",
        role=role,
    )


class ComplaintRouteAuthorizationTests(unittest.TestCase):
    def test_student_can_list_own_complaints(self) -> None:
        db = Mock()
        db.scalars.return_value.all.return_value = []

        self.assertEqual(get_complaints(user_with_role("student"), db), [])
        query = db.scalars.call_args.args[0]
        self.assertIn("complaints.student_id", str(query))

    def test_student_detail_lookup_keeps_ownership_filter(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as raised:
            get_complaint(99, user_with_role("student"), db)

        self.assertEqual(raised.exception.status_code, 404)
        query = db.scalar.call_args.args[0]
        self.assertIn("complaints.student_id", str(query))

    def test_student_and_admin_are_allowed_on_complaint_routes(self) -> None:
        for route in router.routes:
            if route.path not in ("/{complaint_id}", "/"):
                continue
            role_dependency = route.dependant.dependencies[0].call
            for role in ("student", "admin"):
                with self.subTest(path=route.path, role=role):
                    user = user_with_role(role)
                    self.assertIs(role_dependency(user), user)

    def test_maintenance_is_forbidden_on_complaint_routes(self) -> None:
        for route in router.routes:
            if route.path not in ("/{complaint_id}", "/"):
                continue
            role_dependency = route.dependant.dependencies[0].call
            with self.subTest(path=route.path):
                with self.assertRaises(HTTPException) as raised:
                    role_dependency(user_with_role("maintenance"))
                self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
