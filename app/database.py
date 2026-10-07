from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings


DATABASE_PATH = settings.database_path
DATABASE_URL = URL.create("sqlite", database=str(DATABASE_PATH))

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    inspector = inspect(engine)
    if inspector.has_table("complaints"):
        complaint_columns = {
            column["name"] for column in inspector.get_columns("complaints")
        }
        if "assigned_maintenance_id" not in complaint_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE complaints ADD COLUMN "
                        "assigned_maintenance_id INTEGER "
                        "REFERENCES users(id)"
                    )
                )
    Base.metadata.create_all(engine)
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            index.create(engine, checkfirst=True)
