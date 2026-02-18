# Neural News (N²) — Team 15

<img width="500" height="105.84" alt="neural-news-logo" src="https://github.com/user-attachments/assets/45838ba3-50b2-4463-9005-4fc540545e42" />

**Exponential news. Constant-time understanding.**

Piper Fleming · Eva Geierstanger · Kenny Lam · Jack Zhang

---

## Project structure

```
├── docker-compose.yml        — orchestrates backend + database
├── .env.example              — environment variable template
│
├── frontend/                 — HTML / CSS / JS (served by the backend)
│   ├── index.html
│   ├── auth.html
│   └── static/               — images, logos
│
├── backend/                  — FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── seed_db.py
│   ├── app/                  — main application package
│   └── scraper/              — article scraper
│
├── database/                 — Postgres initialisation
│   └── init.sql
│
└── docs/                     — project documentation
    └── Team 15 PRD.pdf
```

---

## Getting started (Docker — recommended)

Docker gives every team member an identical environment with one command.

### Prerequisites

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (includes Docker Compose)

### First-time setup

```bash
# 1. Clone the repo
git clone <repo-url> && cd win26-Team15

# 2. Create your environment file
cp .env.example .env

# 3. Edit .env — at minimum set your OpenAI key:
#    OPENAI_API_KEY=sk-...

# 4. Build and start everything
docker compose up --build
```

The first run will:
- Pull the Postgres 16 image
- Build the backend Python image
- Create the database and tables automatically
- Start the FastAPI server with live-reload

### Day-to-day development

```bash
# Start the app (Ctrl+C to stop)
docker compose up

# Rebuild after changing requirements.txt or Dockerfile
docker compose up --build

# Stop and remove containers (keeps database data)
docker compose down

# Stop and wipe database data
docker compose down -v
```

### Access points

| What | URL |
|---|---|
| Frontend | http://localhost:8000 |
| API (articles) | http://localhost:8000/api/articles |
| API Docs (Swagger) | http://localhost:8000/docs |
| Account page | http://localhost:8000/account |

### Common tasks

```bash
# Seed the database with sample articles
docker compose exec backend python seed_db.py --force

# Run the article scraper
docker compose exec backend python scraper/scraper.py

# Open a Python shell inside the backend container
docker compose exec backend python

# Connect to the database with psql
docker compose exec db psql -U neuralnews -d neuralnews
```

---

## Getting started (without Docker)

If you prefer to run Python directly on your machine.

### Prerequisites

- **Python 3.11+**
- **PostgreSQL** running locally, or a [Neon](https://neon.tech) cloud database

### Setup

```bash
# 1. Create a virtualenv
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp ../.env.example .env
# Edit .env — set DATABASE_URL and OPENAI_API_KEY

# 3. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For a local Postgres database, set in `.env`:

```
DATABASE_URL=postgresql+asyncpg://neuralnews:neuralnews@localhost:5432/neuralnews
```

For the shared Neon cloud database, ask a teammate for the connection string.

---

## Using the cloud database (Neon)

To connect to the shared Neon database instead of the local Docker Postgres:

1. Get the connection string from a teammate.
2. Set `DATABASE_URL` in your `.env` file:
   ```
   DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>.neon.tech/<db>?sslmode=require
   ```
3. In Docker, the `DATABASE_URL` in `.env` is overridden by `docker-compose.yml`.
   To use Neon with Docker, comment out the `DATABASE_URL` line in the
   `environment:` block of `docker-compose.yml` and set it in `.env` instead.

---

## Troubleshooting

- **`docker compose up` fails with port conflict** — Another process is using
  port 8000 or 5432. Stop it or change the port mapping in `docker-compose.yml`.
- **`connection refused` / timeout** — Check `DATABASE_URL` in `.env`. For cloud
  databases, include `?sslmode=require`.
- **Changes not appearing** — The backend live-reloads automatically. For
  frontend changes, hard-refresh your browser (Cmd+Shift+R).
- **`column X does not exist`** — Schema is outdated. Run
  `docker compose exec backend python seed_db.py --force` to recreate tables.
- **500 on `/api/articles`** — Check logs with `docker compose logs backend`.
