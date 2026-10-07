import unittest

from fastapi import HTTPException

from app.models import User
from app.security import require_roles


class RequireRolesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = User(id=1, name="Test User", email="test@example.com", password="hash")

    def test_allowed_role_returns_current_user(self) -> None:
        self.user.role = "admin"
        dependency = require_roles("admin", "staff")

        self.assertIs(dependency(self.user), self.user)

    def test_disallowed_role_raises_forbidden(self) -> None:
        self.user.role = "student"
        dependency = require_roles("admin", "staff")

        with self.assertRaises(HTTPException) as raised:
            dependency(self.user)

        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
