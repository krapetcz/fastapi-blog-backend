# FastAPI Blog Backend

A simple blog backend built with FastAPI and SQLModel.

This project serves as a portfolio example demonstrating clean API design,
basic database interaction, and a clear application structure.
The focus is on readability, maintainability, and understanding core concepts
rather than feature completeness.

---

## Purpose

The goal of this project is to showcase:

- REST API design using FastAPI
- ORM usage with SQLModel (SQLAlchemy + Pydantic)
- Dependency injection for database sessions
- Clean and minimal project structure
- Basic pagination and sorting logic

The project is intentionally kept small to make the architecture
and design decisions easy to understand.

---

## Tech Stack

- Python
- FastAPI
- SQLModel
- SQLite (local development)

---

## Project Structure

```text
fastapiblog/
├─ app/
│  ├─ api.py        # API route definitions
│  ├─ db.py         # database engine and session dependency
│  └─ models.py    # SQLModel ORM models
├─ main.py          # application entry point
├─ fastapiblog.db   # SQLite database
└─ README.md
```

---

## API Overview

The API provides basic CRUD functionality for blog articles.

- POST /articles/ – create a new article
- GET /articles/ – list articles (paginated, newest first)
- GET /articles/{id} – retrieve a single article by ID

Interactive API documentation is available via Swagger UI.

---

## Design Notes

- SQLModel is used to combine ORM models and request/response schemas
- SQLite is used for simplicity and easy local setup
- Database tables are created automatically on application startup
- Pagination is implemented using offset and limit
- CORS is enabled to allow access from a local frontend (e.g. React / Vite)

---

## Running the Project Locally

1. Create and activate a virtual environment
2. Install project dependencies
3. Start the development server

```bash
fastapi dev main.py
```

The API will be available at:
- http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs

---

## Future Improvements

Possible next steps for extending the project:

- Authentication and authorization for write endpoints
- Separation of read/write schemas (DTOs)
- Production-ready database (PostgreSQL)
- Deployment configuration (Docker, cloud hosting)

---

## Author

This project was created as a personal learning and portfolio project.
