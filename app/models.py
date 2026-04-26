from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class Article(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    content: str
    cover_image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    gallery_images: List["GalleryImage"] = Relationship(
        back_populates="article",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class GalleryImage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    url: str
    alt: str = ""
    order: int = 0

    article: Optional["Article"] = Relationship(back_populates="gallery_images")
