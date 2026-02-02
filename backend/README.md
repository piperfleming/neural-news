# Neural News Team 15 Backend

FastAPI + Postgres (async) (+ Redis will be implemented later
).

## Setup

1. **Python 3.11+** and a virtualenv:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Postgres** – already set up locally (`parsley_db`, user `jack_admin`).

3. skipped Redis install

4. **Environment** – copy `.env.example` to `.env` and set `DATABASE_URL` and `REDIS_URL` if needed (defaults point to local Postgres and Redis).

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  
- Ready (DB + Redis): http://localhost:8000/health/ready  

## Project layout

- `app/main.py` – FastAPI app, lifespan, CORS
- `app/config.py` – settings from env (pydantic-settings)
- `app/database.py` – async SQLAlchemy engine and `get_db` dependency
- `app/redis_client.py` – async Redis client and `get_redis` dependency
- `app/models/` – SQLAlchemy models (start from `base.py`)
- `app/routers/` – API route modules

Add new routers in `app/routers/` and include them in `app/main.py`.
