import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Complaint, ComplaintFeedback, User
from app.routers.complaints import get_complaint_stats, router
from app.security import get_current_user


class ComplaintStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.admin = User(
            name="Admin", email="admin@example.com", password="hash", role="admin"
        )
        self.student = User(
            name="Student", email="student@example.com", password="hash", role="student"
        )
        self.maintenance = User(
            name="Maintenance",
            email="maintenance@example.com",
            password="hash",
            role="maintenance",
        )
        self.session.add_all([self.admin, self.student, self.maintenance])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def stats_route(self):
        return next(
            route
            for route in router.routes
            if route.path == "/stats" and "GET" in route.methods
        )

    def test_only_admin_can_access_stats(self) -> None:
        route = self.stats_route()
        role_dependency = route.dependant.dependencies[0].call

        self.assertIs(role_dependency(self.admin), self.admin)
        for user in (self.student, self.maintenance):
            with self.subTest(role=user.role):
                with self.assertRaises(HTTPException) as raised:
                    role_dependency(user)
                self.assertEqual(raised.exception.status_code, 403)

        current_user_dependency = route.dependant.dependencies[0].dependencies[0].call
        self.assertIs(current_user_dependency, get_current_user)
        with self.assertRaises(HTTPException) as raised:
            get_current_user(credentials=None, db=self.session)
        self.assertEqual(raised.exception.status_code, 401)

    def test_stats_count_complaint_status_assignment_and_feedback(self) -> None:
        statuses = ["pending", "pending", "in_progress", "resolved", "resolved", "closed"]
        complaints = [
            Complaint(
                title=f"Complaint {index}",
                description="Test issue",
                category="General",
                priority="medium",
                status=status,
                location="Campus",
                student_id=self.student.id,
                assigned_maintenance_id=(
                    self.maintenance.id if index in (0, 2, 3, 5) else None
                ),
            )
            for index, status in enumerate(statuses)
        ]
        self.session.add_all(complaints)
        self.session.commit()
        self.session.add_all(
            [
                ComplaintFeedback(
                    complaint_id=complaints[3].id,
                    student_id=self.student.id,
                    rating=5,
                    comment="Great",
                ),
                ComplaintFeedback(
                    complaint_id=complaints[4].id,
                    student_id=self.student.id,
                    rating=4,
                ),
                ComplaintFeedback(
                    complaint_id=complaints[5].id,
                    student_id=self.student.id,
                    rating=3,
                ),
            ]
        )
        self.session.commit()

        result = get_complaint_stats(self.admin, self.session)

        self.assertEqual(result.total_complaints, 6)
        self.assertEqual(result.pending_complaints, 2)
        self.assertEqual(result.in_progress_complaints, 1)
        self.assertEqual(result.resolved_complaints, 2)
        self.assertEqual(result.closed_complaints, 1)
        self.assertEqual(result.assigned_complaints, 4)
        self.assertEqual(result.unassigned_complaints, 2)
        self.assertEqual(result.total_feedback, 3)
        self.assertEqual(result.average_rating, 4.0)

    def test_empty_database_and_no_feedback_return_zero_values(self) -> None:
        empty_result = get_complaint_stats(self.admin, self.session)
        self.assertEqual(empty_result.total_complaints, 0)
        self.assertEqual(empty_result.unassigned_complaints, 0)
        self.assertEqual(empty_result.total_feedback, 0)
        self.assertEqual(empty_result.average_rating, 0)

        complaint = Complaint(
            title="No feedback yet",
            description="Test issue",
            category="General",
            priority="medium",
            status="pending",
            location="Campus",
            student_id=self.student.id,
        )
        self.session.add(complaint)
        self.session.commit()

        result = get_complaint_stats(self.admin, self.session)
        self.assertEqual(result.total_complaints, 1)
        self.assertEqual(result.total_feedback, 0)
        self.assertEqual(result.average_rating, 0)


if __name__ == "__main__":
    unittest.main()
