"""
API routes for the blog project.

This module defines REST endpoints for working with Article entities.
The routes are registered via FastAPI's APIRouter and then included in the main app.

Design notes:
- We use dependency injection for database sessions (SessionDep) to keep handlers clean.
- Listing endpoint supports basic pagination (offset/limit) and sorts by newest first.
- For a portfolio-grade project, this file should clearly communicate intent and trade-offs.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.auth import get_current_user
from app.models import Article
from app.db import SessionDep


router = APIRouter()


@router.post("/articles/")
def create_article(article: Article, session: SessionDep) -> Article:
    """
    Create a new article.

    The incoming payload is mapped directly to the Article ORM model.
    After committing, we refresh the instance to return server-generated values
    (e.g., primary key, timestamps if the model defines defaults).

    Returns:
    The newly created Article.
    """
    session.add(article)
    session.commit()
    session.refresh(article)
    return article

@router.get("/articles/")
def get_articles(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[Article]:
    """
    Get a list of articles (newest first).

    Pagination:
        - offset: number of records to skip
        - limit: max number of records returned (capped to 100)

    Notes:
        Sorting by created_at DESC matches typical blog UX where latest posts appear first.
    """
    statement = (
        select(Article)
        .order_by(Article.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    articles = session.exec(statement).all()
    return articles

@router.get("/articles/{article_id}")
def get_article(article_id: int, session: SessionDep) -> Article:
    """
    Get a single article by its ID.

    Raises:
    HTTPException(404): if the article does not exist.
    """
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


# ---------------------------------------------------------------------------
# Diagnostic endpoint for verifying the Auth0 integration.
# TODO: remove before production — leaks the full JWT payload to any caller
# holding a valid token.
# ---------------------------------------------------------------------------
@router.get("/me")
def whoami(claims: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    """
    Return the decoded JWT claims for the caller.

    Requires a valid Auth0 Bearer token. Handy during setup to confirm that
    signature/audience/issuer all line up and to see which claims Auth0 is
    actually issuing (sub, email, email_verified, scope, etc.).
    """
    return claims
