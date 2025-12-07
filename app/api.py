from fastapi import APIRouter

from app.models import Article
from app.db import SessionDep

from typing import Annotated
from fastapi import Query
from sqlmodel import select


router = APIRouter()


@router.post("/articles/")
def create_article(article: Article, session: SessionDep) -> Article:
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
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
