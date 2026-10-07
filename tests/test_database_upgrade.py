import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import Complaint


class DatabaseUpgradeTests(unittest.TestCase):
    def test_init_db_adds_assignment_column_and_preserves_existing_rows(self) -> None:
        test_engine = create_engine("sqlite:///:memory:")
        try:
            with test_engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE users ("
                        "id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, "
                        "email VARCHAR(255) NOT NULL, password VARCHAR(255) NOT NULL, "
                        "role VARCHAR(50) NOT NULL, created_at DATETIME NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TABLE complaints ("
                        "id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, "
                        "description TEXT NOT NULL, category VARCHAR(100) NOT NULL, "
                        "priority VARCHAR(50) NOT NULL, status VARCHAR(50) NOT NULL, "
                        "location VARCHAR(255) NOT NULL, student_id INTEGER NOT NULL, "
                        "created_at DATETIME NOT NULL, resolved_at DATETIME)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO complaints "
                        "(id, title, description, category, priority, status, "
                        "location, student_id, created_at) VALUES "
                        "(5, 'Old complaint', 'Existing data', 'General', 'medium', "
                        "'pending', 'Campus', 3, CURRENT_TIMESTAMP)"
                    )
                )

            with patch("app.database.engine", test_engine):
                init_db()

            table_names = set(inspect(test_engine).get_table_names())
            self.assertTrue(
                {"users", "complaints", "complaint_feedback"} <= table_names
            )

            columns = {
                column["name"]: column
                for column in inspect(test_engine).get_columns("complaints")
            }
            self.assertIn("assigned_maintenance_id", columns)
            self.assertTrue(columns["assigned_maintenance_id"]["nullable"])
            complaint_indexes = inspect(test_engine).get_indexes("complaints")
            index_names = {index["name"] for index in complaint_indexes}
            self.assertIn("ix_complaints_student_id_id", index_names)
            self.assertIn("ix_complaints_assigned_maintenance_id", index_names)

            with patch("app.database.engine", test_engine):
                init_db()
            repeated_index_names = {
                index["name"]
                for index in inspect(test_engine).get_indexes("complaints")
            }
            self.assertEqual(repeated_index_names, index_names)

            with test_engine.connect() as connection:
                row = connection.execute(
                    text("SELECT id, title FROM complaints WHERE id = 5")
                ).one()
            self.assertEqual(tuple(row), (5, "Old complaint"))
            with Session(test_engine) as session:
                existing_complaint = session.get(Complaint, 5)
                self.assertIsNotNone(existing_complaint)
                self.assertEqual(existing_complaint.title, "Old complaint")
        finally:
            test_engine.dispose()


if __name__ == "__main__":
    unittest.main()
