"""
Database models for the FastAPI blog project.

This module defines ORM models using SQLModel, which combines
SQLAlchemy's ORM with Pydantic-style data validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Article(SQLModel, table=True):
    """
    Represents a blog article stored in the database.

    This model is used both:
    - as a database table definition (ORM)
    - as a response/request schema in the API

    Fields are intentionally minimal to keep the project focused
    on API and architecture fundamentals.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
