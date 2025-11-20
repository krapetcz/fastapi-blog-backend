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
    articles = session.exec(select(Article).offset(offset).limit(limit)).all()
    return articles
