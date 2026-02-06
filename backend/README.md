# Neural News (N²) — Team 15 Backend

FastAPI + Postgres (async).

## Prerequisites

- **Python 3.11+**
- **PostgreSQL** running locally

## Setup

### 1. Create a virtualenv and install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create the Postgres database and user

If you haven't already, create the database and user in `psql`:

```sql
CREATE USER jack_admin WITH PASSWORD 'parsley194';
CREATE DATABASE parsley_db OWNER jack_admin;
GRANT ALL PRIVILEGES ON DATABASE parsley_db TO jack_admin;
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your database credentials and API keys:

```
DATABASE_URL=postgresql+asyncpg://jack_admin:parsley194@localhost:5432/parsley_db
APP_ENV=development
DEBUG=true
OPENAI_API_KEY=sk-your-api-key-here
```

> **OpenAI API key:** Required for the article ingestion feature (AI-powered
> summarisation, tagging, sentiment analysis). Get a key at
> https://platform.openai.com/api-keys and paste it in place of
> `sk-your-api-key-here`. The app will still start without a key, but the
> "Add Article" feature on the front page will fail.

### 4. Seed the database

This creates the tables and populates them with sample articles:

```bash
python seed_db.py
```

If you need to re-seed (drops and recreates all tables), just run the same command again.

### 5. Grant table permissions

After seeding, make sure the user has access to the newly created tables:

```bash
psql -d parsley_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jack_admin; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jack_admin;"
```

> **Note:** This step is only needed if the database was originally created by a
> different Postgres role. If `jack_admin` owns the database, you can skip this.

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Frontend:** http://localhost:8000
- **API (articles):** http://localhost:8000/api/articles
- **API Docs (Swagger):** http://localhost:8000/docs

## Project layout

```
backend/
├── seed_db.py          — seeds the DB with sample articles
├── requirements.txt    — Python dependencies
├── .env.example        — template for environment variables
└── app/
    ├── main.py         — FastAPI app, lifespan, CORS, static files
    ├── config.py       — settings from env (pydantic-settings)
    ├── database.py     — async SQLAlchemy engine and get_db dependency
    ├── models/
    │   ├── base.py     — SQLAlchemy declarative base
    │   └── article.py  — Article model
    ├── schemas/
    │   └── article.py  — Pydantic schemas (create, update, response)
    ├── routers/
    │   └── articles.py — CRUD + ingest endpoints for /api/articles
    └── services/
        ├── article_extractor.py — fetches & extracts article text from URLs
        └── llm_service.py       — OpenAI integration (summary, tags, sentiment)
```

Add new routers in `app/routers/` and include them in `app/main.py`.

## Troubleshooting

- **`permission denied for table articles`** — Run the GRANT command from step 5.
- **`column X does not exist`** — The table schema is outdated. Re-run `python seed_db.py` to drop and recreate tables, then re-run the GRANT command.
- **500 on `/api/articles`** — Check the uvicorn terminal for the full traceback.
