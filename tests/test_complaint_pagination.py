import asyncio
import unittest

from fastapi.dependencies.utils import request_params_to_args
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from starlette.datastructures import QueryParams
from starlette.requests import Request

from app.database import Base
from app.main import validation_exception_handler
from app.models import Complaint, User
from app.routers.complaints import get_complaints, router
from app.security import get_current_user


class ComplaintPaginationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.student = User(
            name="Student",
            email="student@example.com",
            password="hash",
            role="student",
        )
        self.other_student = User(
            name="Other Student",
            email="other@example.com",
            password="hash",
            role="student",
        )
        self.admin = User(
            name="Admin",
            email="admin@example.com",
            password="hash",
            role="admin",
        )
        self.maintenance = User(
            name="Maintenance",
            email="maintenance@example.com",
            password="hash",
            role="maintenance",
        )
        self.db.add_all(
            [self.student, self.other_student, self.admin, self.maintenance]
        )
        self.db.commit()

        complaints = [
            Complaint(
                title=f"Student complaint {index}",
                description="Test issue",
                category="General",
                priority="medium",
                location="Campus",
                student_id=self.student.id,
            )
            for index in range(105)
        ]
        complaints.extend(
            Complaint(
                title=f"Other complaint {index}",
                description="Test issue",
                category="General",
                priority="medium",
                location="Campus",
                student_id=self.other_student.id,
            )
            for index in range(2)
        )
        self.db.add_all(complaints)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_default_pagination_returns_first_twenty_student_complaints(self) -> None:
        page = get_complaints(self.student, self.db)

        self.assertEqual(len(page), 20)
        self.assertEqual([complaint.id for complaint in page], list(range(1, 21)))
        self.assertTrue(all(c.student_id == self.student.id for c in page))

    def test_custom_skip_and_limit_are_applied(self) -> None:
        page = get_complaints(self.student, self.db, skip=23, limit=5)

        self.assertEqual(len(page), 5)
        self.assertEqual([complaint.id for complaint in page], list(range(24, 29)))

    def test_custom_limit_is_applied(self) -> None:
        page = get_complaints(self.student, self.db, limit=7)

        self.assertEqual(len(page), 7)

    def test_limit_cannot_exceed_one_hundred(self) -> None:
        page = get_complaints(self.admin, self.db, limit=100)

        self.assertEqual(len(page), 100)
        self.assertEqual(page[0].id, 1)
        self.assertEqual(page[-1].id, 100)

    def test_limit_and_offset_are_applied_in_sql(self) -> None:
        statements: list[str] = []

        def capture_statement(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ) -> None:
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture_statement)
        try:
            get_complaints(self.admin, self.db, skip=4, limit=6)
        finally:
            event.remove(self.engine, "before_cursor_execute", capture_statement)

        complaint_select = next(
            statement
            for statement in statements
            if "FROM complaints" in statement and statement.lstrip().upper().startswith("SELECT")
        )
        self.assertIn("LIMIT", complaint_select.upper())
        self.assertIn("OFFSET", complaint_select.upper())

    def test_student_page_query_uses_composite_ownership_index(self) -> None:
        statements: list[tuple[str, object]] = []

        def capture_statement(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ) -> None:
            statements.append((statement, parameters))

        event.listen(self.engine, "before_cursor_execute", capture_statement)
        try:
            get_complaints(self.student, self.db, skip=2, limit=5)
        finally:
            event.remove(self.engine, "before_cursor_execute", capture_statement)

        statement, parameters = next(
            (statement, parameters)
            for statement, parameters in statements
            if "FROM complaints" in statement
            and statement.lstrip().upper().startswith("SELECT")
        )
        with self.engine.connect() as connection:
            query_plan = connection.exec_driver_sql(
                "EXPLAIN QUERY PLAN " + statement,
                parameters,
            ).all()
        plan_text = " ".join(str(row) for row in query_plan)
        self.assertIn("ix_complaints_student_id_id", plan_text)

    def test_student_ownership_filter_is_applied_before_pagination(self) -> None:
        page = get_complaints(self.student, self.db, skip=104, limit=20)

        self.assertEqual(len(page), 1)
        self.assertEqual(page[0].student_id, self.student.id)

    def test_admin_pagination_still_includes_complaints_from_all_students(self) -> None:
        page = get_complaints(self.admin, self.db, skip=105, limit=20)

        self.assertEqual(len(page), 2)
        self.assertTrue(all(c.student_id == self.other_student.id for c in page))

    def test_maintenance_is_still_denied_from_normal_complaint_list(self) -> None:
        route = next(
            route for route in router.routes
            if route.path == "/" and "GET" in route.methods
        )
        role_dependency = route.dependant.dependencies[0].call
        with self.assertRaises(HTTPException) as raised:
            role_dependency(self.maintenance)
        self.assertEqual(raised.exception.status_code, 403)

    def test_invalid_skip_and_limit_return_standardized_422_details(self) -> None:
        route = next(
            route for route in router.routes
            if route.path == "/" and "GET" in route.methods
        )
        invalid_queries = (
            ("skip=-1", "skip"),
            ("limit=0", "limit"),
            ("limit=-2", "limit"),
            ("limit=101", "limit"),
        )
        for query_string, field_name in invalid_queries:
            with self.subTest(query=query_string):
                _, errors = request_params_to_args(
                    route.dependant.query_params,
                    QueryParams(query_string),
                )
                self.assertTrue(errors)
                request = Request(
                    {
                        "type": "http",
                        "http_version": "1.1",
                        "method": "GET",
                        "scheme": "http",
                        "path": "/complaints/",
                        "raw_path": b"/complaints/",
                        "query_string": query_string.encode(),
                        "headers": [],
                        "client": ("testclient", 50000),
                        "server": ("testserver", 80),
                    }
                )
                response = asyncio.run(
                    validation_exception_handler(
                        request,
                        RequestValidationError(errors),
                    )
                )
                self.assertEqual(response.status_code, 422)
                self.assertIn(field_name.encode(), response.body)
                self.assertIn(b"Request validation failed", response.body)

    def test_complaint_list_requires_existing_authentication_dependency(self) -> None:
        route = next(
            route for route in router.routes
            if route.path == "/" and "GET" in route.methods
        )
        self.assertIs(
            route.dependant.dependencies[0].dependencies[0].call,
            get_current_user,
        )


if __name__ == "__main__":
    unittest.main()
