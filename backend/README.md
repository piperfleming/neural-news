# Neural News (N²) — Team 15 Backend

FastAPI + Postgres (async). The team shares a single cloud-hosted PostgreSQL
database on [Neon](https://neon.tech) so everyone works against the same data.

## Prerequisites

- **Python 3.11+**

> **Note:** You do **not** need PostgreSQL installed locally — the database is
> hosted in the cloud. A local Postgres is only needed if you want to work
> offline (see [Local Postgres (optional)](#local-postgres-optional) below).

## Quick start (cloud database)

### 1. Create a virtualenv and install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the two required values:

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Ask a teammate for the shared Neon connection string (see format below) |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `ADMIN_EMAILS` (optional) | Comma-separated emails that can access `/api/metrics/admin/summary` and the admin dashboard in `/account` |

The `DATABASE_URL` should look like:

```
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>.neon.tech/<db>?sslmode=require
```

> **Important:** The scheme must be `postgresql+asyncpg://` (not plain
> `postgresql://`). Keep `?sslmode=require` at the end — it is required for
> cloud connections.

> **OpenAI API key:** Required for the article ingestion feature (AI-powered
> summarisation, tagging, sentiment analysis). Get a key at
> https://platform.openai.com/api-keys and paste it in place of
> `sk-your-api-key-here`. The app will still start without a key, but the
> "Add Article" feature on the front page will fail.

### 3. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

That's it — the cloud database is already seeded with sample articles.

- **Frontend:** http://localhost:8000
- **API (articles):** http://localhost:8000/api/articles
- **API Docs (Swagger):** http://localhost:8000/docs

---

## Seeding / resetting the database

The seed script drops **all** tables and recreates them with sample data.
Because we share a cloud database, it asks for confirmation before proceeding:

```bash
python seed_db.py
```

You will see a warning and a `yes/no` prompt. To skip the prompt (e.g. in CI),
pass `--force`:

```bash
python seed_db.py --force
```

> **Caution:** This destroys all existing data (articles, users) for the whole
> team. Only run it when the team agrees to reset.

---

## Local Postgres (optional)

If you want to develop offline against a local database:

1. Install and start PostgreSQL locally.
2. Create the database and user:

   ```sql
   CREATE USER jack_admin WITH PASSWORD 'parsley194';
   CREATE DATABASE parsley_db OWNER jack_admin;
   GRANT ALL PRIVILEGES ON DATABASE parsley_db TO jack_admin;
   ```

3. In `.env`, switch the `DATABASE_URL` to the local connection:

   ```
   DATABASE_URL=postgresql+asyncpg://jack_admin:parsley194@localhost:5432/parsley_db
   ```

4. Seed:

   ```bash
   python seed_db.py
   ```

5. Grant table permissions (only needed if the database was created by a
   different Postgres role):

   ```bash
   psql -d parsley_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jack_admin; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jack_admin;"
   ```

---

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
    ├── dependencies.py — shared FastAPI dependencies (auth)
    ├── constants.py    — valid tags list
    ├── models/
    │   ├── base.py     — SQLAlchemy declarative base
    │   ├── article.py  — Article model
    │   └── user.py     — User model
    ├── schemas/
    │   ├── article.py  — Pydantic schemas (create, update, response)
    │   └── user.py     — User schemas
    ├── routers/
    │   ├── articles.py — CRUD + ingest endpoints for /api/articles
    │   ├── auth.py     — Register / login / me
    │   └── users.py    — User profile & preferences
    └── services/
        ├── article_extractor.py — fetches & extracts article text from URLs
        ├── auth_service.py      — password hashing & JWT tokens
        └── llm_service.py       — OpenAI integration (summary, tags, sentiment)
```

Add new routers in `app/routers/` and include them in `app/main.py`.

## Troubleshooting

- **`connection refused` / timeout** — Make sure your `DATABASE_URL` in `.env`
  is correct and includes `?sslmode=require` for the cloud database.
- **`got an unexpected keyword argument 'sslmode'`** — The `database.py` module
  strips this param automatically. Make sure you're on the latest
  `cloud-database` branch.
- **`permission denied for table articles`** — If using local Postgres, run the
  GRANT command from the local-setup section above.
- **`column X does not exist`** — The table schema is outdated. Re-run
  `python seed_db.py` to drop and recreate tables.
- **500 on `/api/articles`** — Check the uvicorn terminal for the full
  traceback.
