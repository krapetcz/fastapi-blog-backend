# FastAPI Blog Backend

A blog backend built with FastAPI and SQLModel, featuring JWT-based authentication via Auth0, image uploads with automatic HEIC conversion, and schema management with Alembic.

---

## Tech Stack

- **Python 3.12**
- **FastAPI** — REST API framework
- **SQLModel** — ORM (SQLAlchemy + Pydantic)
- **SQLite** — database (on a persistent Fly.io volume in production)
- **Alembic** — database migrations
- **Auth0** — JWT authentication and authorisation
- **Pillow / pillow-heif** — image re-encoding and HEIC support
- **pydantic-settings** — typed environment-variable configuration

---

## Project Structure

```text
fastapiblog/
├─ app/
│  ├─ api.py        # route definitions
│  ├─ auth.py       # Auth0 JWT validation
│  ├─ config.py     # pydantic-settings configuration
│  ├─ db.py         # database engine and session dependency
│  ├─ images.py     # image upload and storage logic
│  ├─ models.py     # SQLModel ORM models
│  └─ schemas.py    # request / response schemas
├─ alembic/         # Alembic migration environment
│  └─ versions/     # migration scripts
├─ main.py          # application entry point
├─ requirements.txt
├─ Dockerfile
├─ entrypoint.sh
├─ fly.toml
└─ .env.example
```

---

## API Overview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check (used by Fly.io) |
| GET | `/me` | JWT | Return decoded JWT claims |
| GET | `/articles/` | — | List articles (paginated, newest first) |
| POST | `/articles/` | admin | Create an article |
| GET | `/articles/{id}` | — | Retrieve one article with gallery |
| PUT | `/articles/{id}` | admin | Update article, cover image, and gallery |
| DELETE | `/articles/{id}` | admin | Delete article and its images |
| POST | `/images` | admin | Upload an image; returns its URL |

Write endpoints require a valid Auth0 JWT from an email listed in `ADMIN_EMAILS`.

---

## Design Notes

- Schema is managed by Alembic migrations — run `alembic upgrade head` before the first start and after any schema change.
- Uploaded images are stored in the configured `IMAGES_DIR` directory. In production this is `/data/images` on the Fly persistent volume.
- HEIC images are automatically converted to JPEG on upload.
- CORS origins, database path, and images directory are all driven by environment variables so the same image runs locally and on Fly.io without code changes.

---

## Running Locally

```bash
# 1. Copy and fill in the environment file
cp .env.example .env
# edit .env — set AUTH0_DOMAIN, AUTH0_AUDIENCE, AUTH0_ISSUER, ADMIN_EMAILS

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations (creates the database on first run)
alembic upgrade head

# 5. Start the development server
fastapi dev main.py
```

- API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for the step-by-step Fly.io deployment runbook.

---

## Future Improvements

- PostgreSQL for higher-traffic workloads
- Test suite (pytest + httpx)
- CI/CD pipeline (GitHub Actions)

---

## Author

Personal learning and portfolio project.
