# Neural News (N²) — Backend

FastAPI + Postgres (async). See the [root README](../README.md) for Docker
setup (recommended). This file covers running the backend standalone and
explains the code layout.

## Running standalone (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
# Edit .env — set DATABASE_URL and OPENAI_API_KEY

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment variables

| Variable | Required | Where to get it |
|---|---|---|
| `DATABASE_URL` | Yes | Neon connection string or local Postgres URL |
| `OPENAI_API_KEY` | Yes | https://platform.openai.com/api-keys |
| `JWT_SECRET_KEY` | No | Has a safe default for development |

The `DATABASE_URL` should use the `postgresql+asyncpg://` scheme. For Neon,
keep `?sslmode=require` at the end.

## Seeding / resetting the database

```bash
# With Docker:
docker compose exec backend python seed_db.py --force

# Without Docker (from backend/):
python seed_db.py
```

> **Caution:** This drops all tables and recreates them. On the shared cloud
> database, coordinate with the team before running.

## Project layout

```
backend/
├── Dockerfile          — container image definition
├── requirements.txt    — Python dependencies
├── seed_db.py          — seeds DB with sample articles
├── app/
│   ├── main.py         — FastAPI app, lifespan, CORS, static files
│   ├── config.py       — settings from env (pydantic-settings)
│   ├── database.py     — async SQLAlchemy engine and session
│   ├── dependencies.py — shared FastAPI dependencies (auth)
│   ├── constants.py    — valid tags list
│   ├── models/
│   │   ├── base.py     — SQLAlchemy declarative base
│   │   ├── article.py  — Article model
│   │   ├── user.py     — User model
│   │   └── daily_briefing.py — DailyBriefing model
│   ├── schemas/
│   │   ├── article.py  — Pydantic schemas (create, update, response)
│   │   └── user.py     — User schemas
│   ├── routers/
│   │   ├── articles.py — CRUD + ingest endpoints for /api/articles
│   │   ├── auth.py     — Register / login / me
│   │   ├── users.py    — User profile & preferences
│   │   ├── briefing.py — Daily briefing generation
│   │   └── buzz.py     — Social buzz analysis
│   └── services/
│       ├── article_extractor.py — fetches & extracts article text from URLs
│       ├── auth_service.py      — password hashing & JWT tokens
│       ├── llm_service.py       — OpenAI integration (summary, tags, sentiment)
│       ├── feed_service.py      — periodic article feed refresh
│       ├── briefing_service.py  — daily briefing generation
│       └── social_buzz_service.py — social buzz analysis
├── scraper/
│   ├── scraper.py      — DuckDuckGo news search + backend ingestion
│   └── __main__.py     — python -m scraper entrypoint
├── scripts/            — utility scripts
└── static/             — backend-specific static assets
```

Add new routers in `app/routers/` and include them in `app/main.py`.

## Troubleshooting

- **`connection refused` / timeout** — Check `DATABASE_URL` in `.env` and ensure
  `?sslmode=require` is present for cloud databases.
- **`got an unexpected keyword argument 'sslmode'`** — The `database.py` module
  strips this param automatically. Pull the latest code.
- **`permission denied for table`** — If using local Postgres, grant privileges
  to your database user.
- **`column X does not exist`** — Re-run `python seed_db.py` to recreate tables.
- **500 errors** — Check the uvicorn terminal for the full traceback.
