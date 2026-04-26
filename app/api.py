from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import select

from app.auth import get_current_user, require_admin
from app.images import save_image
from app.models import Article
from app.schemas import ArticleRead, ArticleReadDetail, GalleryImageRead
from app.db import SessionDep


router = APIRouter()


@router.post("/images", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
) -> dict[str, str]:
    url = await save_image(file)
    return {"url": url}


@router.post("/articles/", dependencies=[Depends(require_admin)])
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
) -> list[ArticleRead]:
    statement = (
        select(Article)
        .order_by(Article.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    articles = session.exec(statement).all()
    return [
        ArticleRead(
            id=a.id,
            title=a.title,
            content=a.content,
            cover_image_url=a.cover_image_url,
            created_at=a.created_at,
        )
        for a in articles
    ]


@router.get("/articles/{article_id}")
def get_article(article_id: int, session: SessionDep) -> ArticleReadDetail:
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    gallery = sorted(article.gallery_images, key=lambda img: img.order)
    return ArticleReadDetail(
        id=article.id,
        title=article.title,
        content=article.content,
        cover_image_url=article.cover_image_url,
        created_at=article.created_at,
        gallery_images=[
            GalleryImageRead(id=img.id, url=img.url, alt=img.alt, order=img.order)
            for img in gallery
        ],
    )


@router.put("/articles/{article_id}", dependencies=[Depends(require_admin)])
def update_article(
    article_id: int,
    payload: Article,
    session: SessionDep,
) -> Article:
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.title = payload.title
    article.content = payload.content
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


@router.delete(
    "/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_article(article_id: int, session: SessionDep) -> None:
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    session.delete(article)
    session.commit()


@router.get("/me")
def whoami(claims: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    return claims
