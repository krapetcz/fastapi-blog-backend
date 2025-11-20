from fastapi import FastAPI
from sqlmodel import SQLModel

from app.db import engine
from app.models import Article
from app.api import router


app = FastAPI()
app.include_router(router)

SQLModel.metadata.create_all(engine)

# fastapi dev main.py
