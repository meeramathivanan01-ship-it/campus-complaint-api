import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import User
from app.routers.auth import login_user, password_context, register_user
from app.schemas import UserCreate, UserLogin, UserResponse


class AuthFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.existing_user = User(
            name="Existing Student",
            email="existing@example.com",
            password=password_context.hash("correct horse battery"),
        )
        self.db.add(self.existing_user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_registration_creates_student_and_returns_safe_user_data(self) -> None:
        user_data = UserCreate(
            name="New Student",
            email="new@example.com",
            password="not-a-real-password",
            role="admin",
        )

        user = register_user(user_data, self.db)

        self.assertEqual(user.role, "student")
        self.assertNotEqual(user.password, "not-a-real-password")
        self.assertTrue(password_context.verify("not-a-real-password", user.password))
        response = UserResponse.model_validate(user)
        self.assertNotIn("password", response.model_dump())

    def test_duplicate_email_registration_returns_400(self) -> None:
        user_data = UserCreate(
            name="Duplicate",
            email="existing@example.com",
            password="another-password",
        )

        with self.assertRaises(HTTPException) as raised:
            register_user(user_data, self.db)

        self.assertEqual(raised.exception.status_code, 400)

    def test_invalid_registration_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreate(name=" ", email="not-an-email", password="")

    def test_login_returns_access_token_for_valid_credentials(self) -> None:
        login_data = UserLogin(
            email="existing@example.com",
            password="correct horse battery",
        )

        with patch("app.routers.auth.create_access_token", return_value="test-token"):
            response = login_user(login_data, self.db)

        self.assertEqual(response, {"access_token": "test-token", "token_type": "bearer"})

    def test_login_rejects_invalid_password_and_nonexistent_email(self) -> None:
        credentials = (
            UserLogin(email="existing@example.com", password="wrong-password"),
            UserLogin(email="missing@example.com", password="correct horse battery"),
        )
        for login_data in credentials:
            with self.subTest(email=login_data.email):
                with self.assertRaises(HTTPException) as raised:
                    with self.assertLogs("app.routers.auth", level="WARNING") as captured:
                        login_user(login_data, self.db)
                self.assertEqual(raised.exception.status_code, 401)
                self.assertTrue(all("wrong-password" not in line for line in captured.output))
                self.assertTrue(all(login_data.email not in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
