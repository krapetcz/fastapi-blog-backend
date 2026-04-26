from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel


class GalleryImageWrite(SQLModel):
    url: str
    alt: str = ""
    order: int = 0


class GalleryImageRead(SQLModel):
    id: int
    url: str
    alt: str
    order: int


class ArticleCreate(SQLModel):
    title: str
    content: str
    cover_image_url: Optional[str] = None
    gallery_images: List[GalleryImageWrite] = []


class ArticleUpdate(SQLModel):
    title: str
    content: str
    cover_image_url: Optional[str] = None
    gallery_images: List[GalleryImageWrite] = []


class ArticleRead(SQLModel):
    id: int
    title: str
    content: str
    cover_image_url: Optional[str]
    created_at: datetime


class ArticleReadDetail(ArticleRead):
    gallery_images: List[GalleryImageRead]
