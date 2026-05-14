# DEPLOY.md — Backend deployment runbook (Fly.io)

Step-by-step guide to take this repo from a local git clone to a live
`*.fly.dev` URL. Run these steps in order; each step depends on the previous.

---

## Prerequisites

1. Install `flyctl`:
   ```bash
   brew install flyctl
   # or: curl -L https://fly.io/install.sh | sh
   ```

2. Log in:
   ```bash
   fly auth login
   ```

3. Have your Auth0 tenant values ready (from your Auth0 dashboard):
   - `AUTH0_DOMAIN` (e.g. `dev-xxx.us.auth0.com`)
   - `AUTH0_AUDIENCE` (the API Identifier)
   - `AUTH0_ISSUER` (e.g. `https://dev-xxx.us.auth0.com/`)
   - `ADMIN_EMAILS` (comma-separated list of admin email addresses)

---

## Step 1 — Create the Fly app

```bash
fly apps create krapetblog-api
```

> Pick a unique app name. Whatever you choose becomes your base URL:
> `https://<app-name>.fly.dev`. Update `app` in `fly.toml` if you use
> a different name.

When prompted **do not deploy yet** — the volume and secrets must be set first.

---

## Step 2 — Create the persistent volume

```bash
fly volumes create krapetblog_data --region fra --size 1
```

This 1 GB volume is mounted at `/data` and holds both the SQLite
database (`/data/fastapiblog.db`) and uploaded images (`/data/images`).
Data on this volume survives redeploys.

---

## Step 3 — Set secrets

```bash
fly secrets set \
  AUTH0_DOMAIN="<your-auth0-domain>" \
  AUTH0_AUDIENCE="<your-auth0-audience>" \
  AUTH0_ISSUER="<your-auth0-issuer-with-trailing-slash>" \
  ADMIN_EMAILS="<comma-separated-admin-emails>" \
  CORS_ORIGINS="https://<your-vercel-frontend>.vercel.app"
```

> At this point the frontend URL is not yet known. Set `CORS_ORIGINS` to
> a placeholder (e.g. `https://placeholder.vercel.app`) and update it
> after the frontend is deployed (Step 6 below).

Secrets are stored encrypted in Fly and injected as environment variables
at runtime. They are **not** stored in `fly.toml` or any committed file.

---

## Step 4 — Deploy

```bash
fly deploy
```

The entrypoint runs `alembic upgrade head` automatically before starting
uvicorn, so the database schema is created on first boot. No manual
migration step is needed.

---

## Step 5 — Verify

```bash
curl https://<app-name>.fly.dev/health
# Expected: {"status":"ok"}
```

Open `https://<app-name>.fly.dev/docs` to browse the live API.

---

## Step 6 — Update CORS after frontend is live

After the frontend is deployed to Vercel and you have the `*.vercel.app` URL:

```bash
fly secrets set CORS_ORIGINS="https://<your-app>.vercel.app"
fly deploy
```

---

## Step 7 — Auth0 dashboard

Add the following URLs in your Auth0 tenant under
**Applications → \<your SPA\> → Settings**:

- **Allowed Callback URLs**: `https://<your-app>.vercel.app/callback`
- **Allowed Logout URLs**: `https://<your-app>.vercel.app`
- **Allowed Web Origins**: `https://<your-app>.vercel.app`

See the frontend `DEPLOY.md` for the exact values.

---

## Step 8 — End-to-end verification

1. Open the frontend URL in a browser.
2. Log in with Auth0.
3. Create an article with a cover image and a gallery image.
4. Confirm the article is visible without logging in.
5. Run `fly deploy` again (a new deploy) and confirm the article and images
   are still there after the container restarts — this proves the persistent
   volume is working.

---

## Useful commands

```bash
fly logs                        # tail live logs
fly status                      # machine and deployment status
fly ssh console                 # shell into the running container
fly volumes list                # confirm the volume exists and is attached
fly secrets list                # list secret names (values are hidden)
```
