# HealTrip

HealTrip AI Patient Decision Assistant

## Tech Stack

- **Backend**: Django + Django REST Framework + django-allauth (Google OAuth)
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Cache/Queue**: Redis (prod), Django-Q2 task queue
- **Deployment**: Docker + Nginx, Railway-ready

## Development Setup

### Backend

```bash
cd backend
uv venv && source .venv/bin/activate
uv sync
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required for OAuth:
- `GOOGLE_CLIENT_ID` - From Google Cloud Console
- `GOOGLE_CLIENT_SECRET` - From Google Cloud Console

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create an OAuth 2.0 Client ID (Web application)
3. Add authorized redirect URI: `http://localhost:8000/accounts/google/login/callback/`
4. Copy Client ID and Secret to your `.env`
5. Run `python manage.py migrate`
6. Create a `SocialApp` in Django admin at `/admin/socialaccount/socialapp/`

### Docker

```bash
# Development
docker compose up

# Production
docker compose -f docker-compose.prod.yml up
```

## Testing

```bash
# Backend
cd backend && uv run pytest

# Frontend
cd frontend && npx vitest run
```

## Linting

```bash
# Backend
cd backend && uv run ruff check . && uv run ruff format .

# Frontend
cd frontend && npm run lint
```

## Railway Deployment

Railway env templates are provided:
- `backend/.env.backend.railway`
- `frontend/.env.frontend.railway`

Set these variables in your Railway dashboard for each service.
