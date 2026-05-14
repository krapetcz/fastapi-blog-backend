from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import select

from app.auth import get_current_user, require_admin
from app.images import delete_image_file, save_image
from app.models import Article, GalleryImage
from app.schemas import ArticleCreate, ArticleRead, ArticleReadDetail, ArticleUpdate, GalleryImageRead, ImageUploadResponse
from app.db import SessionDep


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/images", status_code=201, response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
) -> ImageUploadResponse:
    """Accept and store an uploaded image file; return its URL."""
    url = await save_image(file)
    return ImageUploadResponse(url=url)


@router.post("/articles/", status_code=201, dependencies=[Depends(require_admin)])
def create_article(payload: ArticleCreate, session: SessionDep) -> ArticleRead:
    """Create a new article with optional cover image and gallery."""
    article = Article(
        title=payload.title,
        content=payload.content,
        cover_image_url=payload.cover_image_url,
    )
    session.add(article)
    session.commit()
    session.refresh(article)

    for item in payload.gallery_images:
        session.add(GalleryImage(article_id=article.id, url=item.url, alt=item.alt, order=item.order))
    session.commit()

    return ArticleRead(
        id=article.id,
        title=article.title,
        content=article.content,
        cover_image_url=article.cover_image_url,
        created_at=article.created_at,
    )


@router.get("/articles/")
def get_articles(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[ArticleRead]:
    """Return a paginated list of all articles without gallery images."""
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
    """Return a single article including gallery images sorted by order."""
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
    payload: ArticleUpdate,
    session: SessionDep,
) -> ArticleRead:
    """Update article fields, cover image, and gallery with file cleanup on removal."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if article.cover_image_url != payload.cover_image_url:
        if article.cover_image_url is not None:
            delete_image_file(article.cover_image_url)

    old_images = {img.url: img for img in article.gallery_images}
    new_images = {img.url: img for img in payload.gallery_images}

    for url in old_images.keys() - new_images.keys():
        delete_image_file(url)
        session.delete(old_images[url])

    for url in new_images.keys() - old_images.keys():
        session.add(GalleryImage(article_id=article.id, url=url, alt=new_images[url].alt, order=new_images[url].order))

    for url in old_images.keys() & new_images.keys():
        old_images[url].alt = new_images[url].alt
        old_images[url].order = new_images[url].order

    article.title = payload.title
    article.content = payload.content
    article.cover_image_url = payload.cover_image_url
    session.add(article)
    session.commit()
    session.refresh(article)
    return ArticleRead(
        id=article.id,
        title=article.title,
        content=article.content,
        cover_image_url=article.cover_image_url,
        created_at=article.created_at,
    )


@router.delete(
    "/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_article(article_id: int, session: SessionDep) -> None:
    """Delete an article and remove all associated image files from disk."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if article.cover_image_url is not None:
        delete_image_file(article.cover_image_url)

    for img in article.gallery_images:
        delete_image_file(img.url)

    session.delete(article)
    session.commit()


@router.get("/me")
def whoami(claims: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    """Return the decoded JWT claims of the authenticated user."""
    return claims
