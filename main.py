"""
Application entry point for the FastAPI blog project.

This module:
- creates the FastAPI application instance
- configures middleware (CORS)
- registers API routers
- initializes database tables
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.db import engine
from app.models import Article
from app.api import router

# -------------------------------------------------------------------
# FastAPI application
# -------------------------------------------------------------------

app = FastAPI()

# -------------------------------------------------------------------
# CORS configuration
# -------------------------------------------------------------------
# Enabled to allow requests from a local frontend (e.g. React / Vite).
# In production, allowed origins should be restricted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# API routes
# -------------------------------------------------------------------

app.include_router(router)

# -------------------------------------------------------------------
# Database initialization
# -------------------------------------------------------------------
# Creates all database tables based on SQLModel metadata.
# This is suitable for small projects and local development.
SQLModel.metadata.create_all(engine)

# Development run command:
# fastapi dev main.py
