"""
Database configuration and session management.

This module is responsible for:
- creating the database engine
- providing a database session via FastAPI dependency injection

SQLite is used for simplicity and local development. The same pattern can be
easily adapted for PostgreSQL or another production-ready database.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, create_engine

# -------------------------------------------------------------------
# Database configuration
# -------------------------------------------------------------------

# SQLite database file (local development / portfolio setup)
sqlite_file_name = "fastapiblog.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# Required for SQLite when used with FastAPI (multi-threaded environment)
connect_args = {"check_same_thread": False}

# SQLModel engine (built on top of SQLAlchemy)
engine = create_engine(sqlite_url, connect_args=connect_args)


# -------------------------------------------------------------------
# Session dependency
# -------------------------------------------------------------------
def get_session():
    """
    Provide a database session for a single request.

    The session is automatically opened and closed using a context manager.
    FastAPI will inject this dependency into route handlers when requested.

    Yields:
        Session: SQLModel session bound to the configured engine.
    """
    with Session(engine) as session:
        yield session

# Type alias for cleaner dependency injection in route definitions
SessionDep = Annotated[Session, Depends(get_session)]



