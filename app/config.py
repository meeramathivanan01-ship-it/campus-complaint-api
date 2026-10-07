import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_environment_file(
    env_file: Path = ENV_FILE,
    environ: dict[str, str] | None = None,
) -> None:
    """Load simple KEY=VALUE entries without overriding process environment."""

    target = os.environ if environ is None else environ
    if not env_file.is_file():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        name = name.strip()
        if separator and name:
            target.setdefault(name, value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    secret_key: str | None = field(repr=False)
    database_path: Path
    environment: str
    log_level: str


def load_settings(
    env_file: Path = ENV_FILE,
    environ: dict[str, str] | None = None,
) -> Settings:
    target = os.environ if environ is None else environ
    load_environment_file(env_file, target)

    database_path_value = target.get("DATABASE_PATH")
    if database_path_value:
        database_path = Path(database_path_value).expanduser()
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
    else:
        database_path = PROJECT_ROOT / "campus_complaints.db"

    return Settings(
        secret_key=target.get("SECRET_KEY"),
        database_path=database_path,
        environment=target.get("ENVIRONMENT", "development"),
        log_level=target.get("LOG_LEVEL", "INFO").strip().upper(),
    )


settings = load_settings()
