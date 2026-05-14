# DEPLOY_TASKS_BACKEND.md — Backend deployment task plan

> Repo: `fastapi-blog-backend`. Read `DEPLOY_SPEC.md` first for shared context.
> Work milestone by milestone. After each milestone: verify the app still
> starts locally with `fastapi dev main.py` and behaves as before, then commit
> with a `[DEPLOY-Mx]` prefix.

**Golden rule:** local development must keep working with no new setup. Every
new environment variable gets a default equal to today's behaviour.

---

## M1 — Make configuration environment-driven

**Goal:** remove hardcoded localhost CORS, database path, and images directory;
read them from settings instead.

**Files:** `app/config.py`, `main.py`, `app/db.py`, `app/images.py`

**Changes:**
- `app/config.py` — add three settings to the `Settings` model:
  - `cors_origins: list[str]` — parsed from a comma-separated string, same
    pattern as the existing `admin_emails` validator (use `NoDecode` + a
    `mode="before"` validator). Default:
    `["http://localhost:5173", "http://127.0.0.1:5173"]`.
  - `database_path: str` — default `"fastapiblog.db"`.
  - `images_dir: str` — default `"images"`.
- `main.py` — read CORS origins from `get_settings().cors_origins` instead of
  the hardcoded list. Mount `StaticFiles` using the configured images dir.
- `app/db.py` — build the SQLite URL from `get_settings().database_path`
  (`sqlite:///{database_path}`) instead of the module-level constant. Keep
  `connect_args={"check_same_thread": False}`.
- `app/images.py` — `IMAGES_DIR` becomes `Path(get_settings().images_dir)`.
  Ensure the directory is created if it does not exist (`mkdir(parents=True,
  exist_ok=True)`) at startup or on first use — important because in
  production `/data/images` starts empty.

**Acceptance criteria:**
- With no `.env` changes, `fastapi dev main.py` starts and `GET /articles/`
  works exactly as before.
- CORS still allows `http://localhost:5173`.
- Setting `CORS_ORIGINS`, `DATABASE_PATH`, `IMAGES_DIR` env vars changes the
  respective behaviour.

**Test:** `fastapi dev main.py`; hit `/docs`, list articles; confirm the
frontend dev server can still call the API.

---

## M2 — Fix the Alembic initial migration

**Goal:** make `alembic upgrade head` work on a brand-new empty database.

**Problem:** the only migration `29dcdb5389bf` has `down_revision = None` but
does **not** create the `article` table — it only adds `cover_image_url` to it
and creates `galleryimage`. On a fresh DB, `alembic upgrade head` fails because
`article` does not exist. The table was originally created ad-hoc via
`SQLModel.metadata.create_all()` before Alembic was introduced.

**Changes:**
- Make Alembic use the same database path as the app. In `alembic/env.py`,
  set the SQLAlchemy URL from `app.config.get_settings().database_path`
  (`sqlite:///{database_path}`) rather than relying on a hardcoded
  `sqlalchemy.url` in `alembic.ini`. This guarantees migrations target
  `/data/fastapiblog.db` in production.
- Delete the existing migration file
  `alembic/versions/29dcdb5389bf_add_cover_image_url_and_galleryimage.py`.
- Regenerate a single complete initial migration against an **empty**
  database: `alembic revision --autogenerate -m "initial schema"`. It must
  create both tables with all current columns:
  - `article`: `id` (PK), `title` (indexed), `content`, `cover_image_url`
    (nullable), `created_at`.
  - `galleryimage`: `id` (PK), `article_id` (FK → `article.id`), `url`,
    `alt`, `order`.
- Review the generated migration — confirm it has `op.create_table` for both,
  the FK constraint, and the index on `article.title`.

**Acceptance criteria:**
- Delete any local `fastapiblog.db`, run `alembic upgrade head` → both tables
  are created correctly.
- `alembic downgrade base` cleanly drops them.
- The app runs against the migrated DB and all endpoints work.

**Test:** `rm -f fastapiblog.db && alembic upgrade head`, then
`fastapi dev main.py` and exercise create/read/update/delete.

---

## M3 — Add a health endpoint

**Goal:** give Fly.io a lightweight endpoint to check the app is alive.

**Files:** `app/api.py`

**Changes:**
- Add `GET /health` returning `{"status": "ok"}`. No authentication, no
  database dependency — it must succeed even if the DB is briefly unavailable.

**Acceptance criteria:** `curl http://127.0.0.1:8000/health` → `200` with
`{"status": "ok"}`.

---

## M4 — Remove Sentry

**Goal:** drop the unused `sentry-sdk` dependency.

**Files:** `requirements.txt`

**Changes:**
- Remove the `sentry-sdk==2.44.0` line. Confirm nothing in `app/` or `main.py`
  imports `sentry_sdk` (it does not).

**Acceptance criteria:** `pip install -r requirements.txt` in a clean venv
succeeds; the app starts with no import errors.

---

## M5 — Dockerfile + entrypoint + .dockerignore

**Goal:** a production container image that migrates the DB then serves the app.

**Files:** new `Dockerfile`, new `entrypoint.sh`, new `.dockerignore`

**Changes:**
- `Dockerfile`:
  - Base `python:3.12-slim`.
  - Install `requirements.txt` (use a pip cache-friendly layer order: copy
    `requirements.txt`, install, then copy the rest).
  - `pillow-heif` and `pillow` ship manylinux wheels, so no extra system
    packages should be needed — but if the build fails on `pillow-heif`,
    add `libheif1` via `apt-get`.
  - Create and switch to a non-root user.
  - Copy `entrypoint.sh`, make it executable, set as `ENTRYPOINT`.
  - Default `CMD` is not needed if the entrypoint launches uvicorn directly.
- `entrypoint.sh`:
  - Run `alembic upgrade head` (creates/migrates the SQLite DB on the mounted
    volume — this is why migrations are NOT a Fly `release_command`: the
    volume is reliably mounted in the app machine, not necessarily in a
    release machine).
  - Then `exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"`.
- `.dockerignore`: `.venv`, `.git`, `__pycache__`, `*.pyc`, `*.db`, `*.sqlite`,
  `images/`, `.idea`, `.DS_Store`, `.env`, `*.md` is optional — keep `DEPLOY*`
  and `README` out of the image if you like.

**Acceptance criteria:**
- `docker build -t krapetblog-api .` succeeds.
- `docker run -e DATABASE_PATH=/tmp/test.db -e IMAGES_DIR=/tmp/images -e AUTH0_DOMAIN=... -e AUTH0_AUDIENCE=... -e AUTH0_ISSUER=... -e ADMIN_EMAILS=... -p 8000:8000 krapetblog-api`
  starts, runs migrations, and `GET /health` returns 200.

---

## M6 — fly.toml

**Goal:** declare the Fly app, the persistent volume mount, and the health check.

**Files:** new `fly.toml`

**Changes:**
- App name: placeholder `krapetblog-api` (the person picks the final unique
  name when running `fly launch`).
- `primary_region = "fra"`.
- `[mounts]` — a volume (e.g. `krapetblog_data`) mounted at `/data`.
- `[env]` — non-secret values:
  - `DATABASE_PATH = "/data/fastapiblog.db"`
  - `IMAGES_DIR = "/data/images"`
- `[http_service]` — internal port `8000`, `force_https = true`,
  `auto_stop_machines` / `auto_start_machines` as preferred, with a health
  check hitting `/health`.
- Add a comment block at the top of `fly.toml` reminding that secrets
  (`AUTH0_*`, `ADMIN_EMAILS`, `CORS_ORIGINS`) are set via `fly secrets set`,
  NOT in this file.

**Acceptance criteria:** `fly config validate` passes. (Full verification
happens during the manual deploy.)

---

## M7 — Repo cleanup

**Goal:** stop tracking editor/OS junk that is currently committed.

**Files:** `.gitignore`, plus `git rm --cached`

**Changes:**
- `git rm --cached -r .idea` and `git rm --cached .DS_Store` (and any other
  `.DS_Store` under the tree).
- Add `.idea/` and `.DS_Store` to `.gitignore`.

**Acceptance criteria:** `git status` shows `.idea/` and `.DS_Store` as
deleted-from-tracking and ignored; they remain on disk locally.

---

## M8 — Rewrite README.md

**Goal:** the README must accurately describe the current app, not the
original minimal version.

**Files:** `README.md`

**Changes — fix all of the following, which are now outdated or wrong:**
- Intro / Purpose — drop "intentionally kept small" / "rather than feature
  completeness"; the app now has auth, image uploads, galleries, migrations.
- Tech Stack — add Auth0 (JWT), Alembic, Pillow / pillow-heif, pydantic-settings.
- Project Structure — reflect the real tree: `app/{api,auth,config,db,images,
  models,schemas}.py`, `alembic/`, `main.py`, `requirements.txt`, `.env.example`.
- API Overview — list all endpoints: `GET/POST/PUT/DELETE /articles`,
  `POST /images`, `GET /me`, `GET /health`.
- Design Notes — **remove the false line** "Database tables are created
  automatically on application startup". Replace with: schema is managed by
  Alembic migrations (`alembic upgrade head`).
- Running Locally — now requires a `.env` file (copy from `.env.example`) and
  `alembic upgrade head` before first run.
- Add a **Deployment** section pointing to `DEPLOY.md`.
- Future Improvements — remove the items now done (auth, DTOs, deployment
  config); keep PostgreSQL and add e.g. tests, CI/CD.

**Acceptance criteria:** every statement in the README is true of the current
code.

---

## M9 — DEPLOY.md (deployment runbook)

**Goal:** a step-by-step guide for the manual Fly.io deployment.

**Files:** new `DEPLOY.md`

**Contents:**
- Prerequisites: install `flyctl`, `fly auth login`.
- `fly launch` (or `fly apps create`) — pick the final app name; do NOT deploy
  yet when prompted.
- `fly volumes create krapetblog_data --region fra --size 1` (1 GB is plenty).
- Set secrets:
  `fly secrets set AUTH0_DOMAIN=... AUTH0_AUDIENCE=... AUTH0_ISSUER=... ADMIN_EMAILS=... CORS_ORIGINS=...`
  (CORS_ORIGINS can be a placeholder at first — it is updated after the
  frontend is deployed).
- `fly deploy`.
- Verify: `curl https://<app>.fly.dev/health`.
- Note that the entrypoint runs `alembic upgrade head` automatically on every
  deploy, so the DB schema is created on first boot.
- After the frontend is live: `fly secrets set CORS_ORIGINS=https://<app>.vercel.app`
  then `fly deploy` again.
- Auth0 dashboard reminder — see the frontend `DEPLOY.md` for the exact values.

**Acceptance criteria:** a person following `DEPLOY.md` top to bottom can take
the repo to a live `*.fly.dev` URL.

---

## Commit & wrap-up

- One commit per milestone, prefix `[DEPLOY-M1]` … `[DEPLOY-M9]`.
- After M9, push `main`.
- Do **not** create or move any git tags.
- The actual `fly deploy` is performed manually afterwards, following `DEPLOY.md`.
