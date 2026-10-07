import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import User
from app.security import ALGORITHM, create_access_token, get_current_user


TEST_SIGNING_KEY = "test-only-signing-key-never-used-outside-this-test"


class JwtAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            name="JWT Student",
            email="jwt-student@example.com",
            password="test-hash",
        )
        self.db.add(self.user)
        self.db.commit()
        self.secret_patch = patch("app.security.SECRET_KEY", TEST_SIGNING_KEY)
        self.secret_patch.start()

    def tearDown(self) -> None:
        self.secret_patch.stop()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def credentials(self, token: str) -> HTTPAuthorizationCredentials:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def test_valid_token_resolves_current_database_user(self) -> None:
        token = create_access_token(self.user.id, "student")

        current_user = get_current_user(self.credentials(token), self.db)

        self.assertEqual(current_user.id, self.user.id)
        self.assertEqual(current_user.role, "student")

    def test_expired_token_is_rejected_with_bearer_challenge(self) -> None:
        expired_token = jwt.encode(
            {
                "user_id": self.user.id,
                "role": "student",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            TEST_SIGNING_KEY,
            algorithm=ALGORITHM,
        )

        with self.assertRaises(HTTPException) as raised:
            get_current_user(self.credentials(expired_token), self.db)

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.headers["WWW-Authenticate"], "Bearer")

    def test_valid_token_for_nonexistent_user_is_rejected(self) -> None:
        token = jwt.encode(
            {
                "user_id": self.user.id + 1000,
                "role": "student",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            TEST_SIGNING_KEY,
            algorithm=ALGORITHM,
        )

        with self.assertRaises(HTTPException) as raised:
            get_current_user(self.credentials(token), self.db)

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.headers["WWW-Authenticate"], "Bearer")

    def test_malformed_token_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_current_user(self.credentials("not.a.jwt"), self.db)

        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
