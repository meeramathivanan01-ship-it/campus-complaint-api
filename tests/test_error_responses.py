import asyncio
import unittest
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.main import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.schemas import ComplaintFeedbackCreate
from app.security import get_current_user


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/test",
            "raw_path": b"/test",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


class ErrorResponseTests(unittest.TestCase):
    def test_missing_and_invalid_credentials_remain_401_with_bearer_header(self) -> None:
        db = Mock()
        invalid_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-token"
        )
        for credentials in (None, invalid_credentials):
            with self.subTest(credentials=credentials is not None):
                with self.assertRaises(HTTPException) as raised:
                    if credentials is None:
                        get_current_user(credentials=credentials, db=db)
                    else:
                        with self.assertLogs("app.security", level="WARNING") as logged:
                            get_current_user(credentials=credentials, db=db)
                        self.assertNotIn(
                            credentials.credentials, "\n".join(logged.output)
                        )
                self.assertEqual(raised.exception.status_code, 401)
                response = asyncio.run(
                    http_exception_handler(make_request(), raised.exception)
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertEqual(
                    response.body,
                    b'{"error":"Could not validate credentials.","status_code":401}',
                )

    def test_http_errors_keep_status_and_use_consistent_body(self) -> None:
        for status_code, detail in (
            (400, "Invalid status transition."),
            (403, "You do not have permission."),
            (404, "Complaint not found."),
            (409, "Feedback already exists."),
        ):
            with self.subTest(status_code=status_code):
                response = asyncio.run(
                    http_exception_handler(
                        make_request(),
                        StarletteHTTPException(
                            status_code=status_code, detail=detail
                        ),
                    )
                )
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(
                    response.body,
                    (
                        f'{{"error":"{detail}","status_code":{status_code}}}'
                    ).encode(),
                )

    def test_validation_response_identifies_invalid_field_without_input(self) -> None:
        try:
            ComplaintFeedbackCreate(rating=6)
        except ValidationError as validation_error:
            error = RequestValidationError(validation_error.errors())
        else:
            self.fail("Expected rating validation to fail")

        response = asyncio.run(
            validation_exception_handler(make_request(), error)
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.body,
            b'{"error":"Request validation failed","status_code":422,'
            b'"detail":[{"loc":["rating"],"msg":"Input should be less than or '
            b'equal to 5","type":"less_than_equal"}]}',
        )
        self.assertNotIn(b'"input"', response.body)

    def test_unhandled_error_does_not_expose_exception_text(self) -> None:
        with self.assertLogs("app.main", level="ERROR") as captured:
            response = asyncio.run(
                unhandled_exception_handler(
                    make_request(), RuntimeError("diagnostic failure")
                )
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.body,
            b'{"error":"Internal server error","status_code":500}',
        )
        self.assertNotIn(b"diagnostic failure", response.body)
        self.assertIn("Unhandled application exception", captured.output[0])
        self.assertIn("RuntimeError: diagnostic failure", captured.output[0])


if __name__ == "__main__":
    unittest.main()
