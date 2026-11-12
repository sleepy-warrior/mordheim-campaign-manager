import os


def get_database_url() -> str:
    """Return the PostgreSQL URL configured for the current environment."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return database_url
