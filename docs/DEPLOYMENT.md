# Deployment (Railway)

Target topology: **3 Railway services** in one project.

```
Browser ──https──> frontend (nginx, public domain)
                     ├── /            SPA (static build)
                     └── /api /admin /accounts ──private network──> backend (gunicorn :8000)
                                                                     └──> Postgres (Railway plugin)
```

The browser only ever talks to the **frontend domain**. The API is same-origin through nginx, so session and CSRF cookies are first-party and CORS isn't exercised. The backend needs no public domain.

## Before you start (things only you can do)

1. A GitHub account with this repository pushed (see "Push to GitHub" at the end).
2. A Railway account (railway.app), logged in with GitHub.
3. An Anthropic API key from console.anthropic.com. Set a **monthly spend limit** in the Anthropic console for the demo.

## Step by step

### 1. Create the project and database
1. Railway dashboard → **New Project** → **Deploy from GitHub repo** → pick this repository. Railway creates one service from it; you'll turn it into the backend in step 2.
2. In the project canvas: **+ Create** → **Database** → **PostgreSQL**. Keep the default service name **`Postgres`**, since the env templates reference `${{Postgres.DATABASE_URL}}`.
3. *(Recommended)* **+ Create** → **Database** → **Redis** (service name `Redis`). This shares rate-limit counters across gunicorn workers.

### 2. Backend service
1. Open the service created from the repo → **Settings**:
   - **Service name:** `backend`. The name matters because the frontend's env references `${{backend.RAILWAY_PRIVATE_DOMAIN}}`.
   - **Root directory:** leave empty (repo root). The Dockerfile copies `backend/...`.
   - **Healthcheck path:** `/api/health/`
2. **Variables** → **Raw Editor** → paste the contents of [`backend/.env.backend.railway`](../backend/.env.backend.railway), then replace:
   - `SECRET_KEY`: a long random string, e.g. `python -c "import secrets; print(secrets.token_urlsafe(50))"`
   - `ANTHROPIC_API_KEY`: your key
   - `DJANGO_SUPERUSER_PASSWORD`: a strong password, or delete the three superuser lines
   - uncomment `REDIS_URL` if you added Redis
3. Deploy. On start the container runs `migrate`, then `seed_providers` (idempotent), then gunicorn. Check the logs for `Seeded 7 specialties, 8 hospitals, 28 doctors`.

### 3. Frontend service
1. **+ Create** → **GitHub Repo** → the same repository again → **Settings**:
   - **Service name:** `frontend`
   - **Networking** → **Generate Domain**. This is your demo link.
2. **Variables** → **Raw Editor** → paste [`frontend/.env.frontend.railway`](../frontend/.env.frontend.railway):
   ```
   RAILWAY_DOCKERFILE_PATH="frontend/Dockerfile"
   BACKEND_URL="${{backend.RAILWAY_PRIVATE_DOMAIN}}"
   ```
3. Deploy, then **redeploy the backend once** so `${{frontend.RAILWAY_PUBLIC_DOMAIN}}` resolves in `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS`.

### 4. Verify
```bash
curl https://<frontend-domain>/api/health/
# {"status":"ok","database":"ok","llm":{"provider":"anthropic","model":"claude-sonnet-5-5","api_key_configured":true},...}
```
Open `https://<frontend-domain>/`, click the English chest-pain example, then the Arabic emergency example. Open **Agent trace**. OpenAPI docs are at `https://<frontend-domain>/api/docs/`.

### 5. Optional hardening
- **Least-privilege tool role.** Railway → Postgres → **Connect** → copy the `psql` command, then:
  ```bash
  psql "<connection-url>" -v tools_password="'<strong-password>'" -f docs/sql/readonly_role.sql
  ```
  Then set `DATABASE_URL_READONLY` on the backend (template line provided) and redeploy.
- **Retention job.** + Create → **Cron** (or a scheduled service) using the backend image, running `uv run python manage.py purge_old_sessions` daily.
- **Google login (optional).** Create an OAuth client with redirect URI `https://<frontend-domain>/accounts/google/login/callback/`, set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, then add a *Social application* in `/admin/`.

## Demo safety settings (already in the production defaults)

| Setting | Production default | Effect |
|---|---|---|
| `CHAT_RATE_PER_MINUTE` / `CHAT_RATE_PER_DAY` | 10 / 60 | per client IP (`NUM_PROXIES=2` reads the real IP behind Railway edge + nginx) |
| `CHAT_SESSION_RATE` | 10/min | per conversation |
| `CHAT_MAX_MESSAGES_PER_SESSION` | 50 | per conversation |
| `DEMO_DAILY_MESSAGE_CAP` | 500 | **global**, per rolling 24 h, DB-backed. Worst case ≈ 500 × 5 model calls/day |
| `SESSION_CREATE_RATE` | 10/hour | per IP |

## Local alternative: `docker compose`

```bash
cp .env.example .env      # set ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic for the real model
docker compose up --build # postgres + backend (migrate + seed) + frontend
# http://localhost:3000   · API docs http://localhost:8000/api/docs/
```

## Push to GitHub

```bash
# create an EMPTY repo on github.com first (no README), then:
git remote add origin https://github.com/<you>/healtrip-assistant.git
git push -u origin main
```
CI (`.github/workflows/ci.yml`) runs automatically on push: lint, backend tests on Postgres with the mock LLM, frontend type-check, lint, tests and build, then Docker image builds.
