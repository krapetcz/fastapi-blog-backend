# DEPLOY_SPEC.md — Shared deployment specification

> Shared context for the deployment phase of KrapetBlog. A copy of this file
> lives in **both** repos (`fastapi-blog-backend` and `fastapi-blog-frontend`).
> Give this file to Claude Code as context, alongside the repo-specific task
> file (`DEPLOY_TASKS_BACKEND.md` or `DEPLOY_TASKS_FRONTEND.md`).

---

## 1. Goal

The blog is feature-complete and works locally. This phase makes it
**deployable and live on the internet** — without changing any product
behaviour. No new features. The only goal is: a fresh machine can build,
start, and serve the app, and data survives redeploys.

## 2. Current state (as of this phase)

- Both repos are published on GitHub, `main` holds the finished app.
- The original minimal portfolio version is preserved under the git tag
  `v1.0-portfolio-minimal` in each repo — **do not touch or move that tag.**
- Backend: FastAPI + SQLModel + SQLite, Auth0 JWT validation, image uploads
  to a local `images/` directory, Alembic present but incomplete (see below).
- Frontend: React 19 + Vite + Tailwind 4, Auth0 SPA login.

## 3. Target architecture

```
   Browser
      │
      ├──────────────►  Vercel  (static frontend build, HTTPS)
      │                    │
      │                    │  VITE_API_BASE_URL
      ▼                    ▼
   Auth0  ◄──────────  Fly.io  (FastAPI in Docker, HTTPS)
   (existing tenant)       │
                           ▼
                   Fly persistent volume  ──►  /data
                     • fastapiblog.db (SQLite)
                     • uploaded images
```

- **Backend → Fly.io.** Runs as a Docker container. A Fly **persistent
  volume** is mounted at `/data` and holds both the SQLite database file and
  the uploaded images. Without the volume, every redeploy would wipe all data.
- **Frontend → Vercel.** Static build (`vite build`), connected to the GitHub
  repo for automatic deploys. Environment variables set in the Vercel
  dashboard, not committed.
- **Auth** stays on the existing Auth0 tenant. Only the dashboard
  configuration changes (production URLs added).
- **No custom domain** for now — the free `*.fly.dev` and `*.vercel.app`
  subdomains are used. A domain can be added later without code changes.

## 4. Decisions already made

- **SQLite stays** (on the Fly volume). No migration to Postgres in this phase.
- **Sentry is removed** from the backend (`sentry-sdk` is in `requirements.txt`
  but never initialised). Error tracking can be added later.
- **Hosting: Fly.io** for the backend (free tier, native volumes), **Vercel**
  for the frontend (free tier).
- The original version is kept as the `v1.0-portfolio-minimal` tag — no second
  repository.

## 5. Hard constraints / guiding principles

1. **Local development must keep working unchanged.** Every new environment
   variable must have a default that reproduces today's local behaviour. After
   the changes, `fastapi dev main.py` and `npm run dev` must work with no new
   setup.
2. **Nothing host-specific is hardcoded.** API URLs, CORS origins, database
   path, and the images directory all come from environment variables.
3. **SQLite DB and uploaded images must live on the persistent volume in
   production** (`/data`). If they land on the container filesystem, they are
   lost on every redeploy.
4. **HTTPS everywhere.** Auth0 will not accept non-HTTPS callback URLs (except
   `localhost`). Both Fly and Vercel give HTTPS for free.
5. **No secrets in git.** `.env` stays git-ignored. Production secrets are set
   via `fly secrets` (backend) and the Vercel dashboard (frontend).

## 6. Environment variables — full catalogue

### Backend (Fly.io — set via `fly secrets set`)

| Variable          | Local default                         | Production value                                  |
|-------------------|---------------------------------------|---------------------------------------------------|
| `AUTH0_DOMAIN`    | (from `.env`)                         | same as local                                     |
| `AUTH0_AUDIENCE`  | (from `.env`)                         | same as local                                     |
| `AUTH0_ISSUER`    | (from `.env`)                         | same as local                                     |
| `ADMIN_EMAILS`    | (from `.env`)                         | same as local                                     |
| `CORS_ORIGINS`    | `http://localhost:5173,http://127.0.0.1:5173` | the Vercel frontend URL                   |
| `DATABASE_PATH`   | `fastapiblog.db`                      | `/data/fastapiblog.db`                            |
| `IMAGES_DIR`      | `images`                              | `/data/images`                                    |
| `PORT`            | `8000`                                | provided by Fly                                   |

### Frontend (Vercel — set in the dashboard)

| Variable                 | Local (`.env`)              | Production value                |
|--------------------------|-----------------------------|---------------------------------|
| `VITE_API_BASE_URL`      | `http://127.0.0.1:8000`     | the Fly backend URL             |
| `VITE_AUTH0_DOMAIN`      | (from `.env`)               | same as local                   |
| `VITE_AUTH0_CLIENT_ID`   | (from `.env`)               | same as local                   |
| `VITE_AUTH0_AUDIENCE`    | (from `.env`)               | same as local                   |
| `VITE_ADMIN_EMAILS`      | (from `.env`)               | same as local                   |

## 7. Deployment sequencing

The two sides have a chicken-and-egg dependency (backend needs the frontend
URL for CORS, frontend needs the backend URL for the API). Resolve it in this
order:

1. **Backend code changes** (`DEPLOY_TASKS_BACKEND.md`) — make everything
   env-driven, fix the Alembic migration, add Docker + `fly.toml`.
2. **Deploy backend to Fly.io** → obtain the `*.fly.dev` URL.
3. **Frontend code changes** (`DEPLOY_TASKS_FRONTEND.md`) — add production
   config, `vercel.json`.
4. **Deploy frontend to Vercel** with `VITE_API_BASE_URL` = the Fly URL →
   obtain the `*.vercel.app` URL.
5. **Update backend** `CORS_ORIGINS` secret with the Vercel URL, redeploy.
6. **Auth0 dashboard** — add the Vercel URL to Allowed Callback URLs, Allowed
   Logout URLs, and Allowed Web Origins.
7. **Verify end-to-end** — load the site, log in, create/edit/delete an
   article with an image, confirm data survives a backend redeploy.

Steps 1 and 3 are the Claude Code work. Steps 2, 4, 5, 6, 7 are manual and are
documented step-by-step in the `DEPLOY.md` file each task plan produces.

## 8. Out of scope (deferred)

- PostgreSQL migration
- Sentry / error tracking
- CI/CD pipelines (GitHub Actions)
- Custom domain
- Rate limiting, caching, CDN for images

## 9. How the task files relate

- `DEPLOY_TASKS_BACKEND.md` — lives in `fastapi-blog-backend`. Milestones M1–M9.
- `DEPLOY_TASKS_FRONTEND.md` — lives in `fastapi-blog-frontend`. Milestones M1–M4.

Work milestone by milestone. After each milestone, verify locally that the app
still starts and behaves as before, then commit. The frontend work depends on
the backend being deployed first (it needs the real Fly URL).
