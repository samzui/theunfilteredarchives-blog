# Whisper Blog — Full FastAPI Backend

Portfolio-ready REST API for a personal writing/community platform.

## Stack
FastAPI, Python, PostgreSQL, SQLAlchemy 2, Alembic, Pydantic, JWT, Swagger/OpenAPI.

## Included
Authentication and roles, admin dashboard, writings/drafts/publishing, categories/tags, search/pagination,
anonymous + authenticated likes, comments/replies, comment likes, reports/moderation, bookmarks,
notifications, view analytics, rate limiting, validation, CORS, migrations and tests.

## Run on Windows
1. Create PostgreSQL database `whisper_blog`.
2. Copy `.env.example` to `.env` and fill in values.
3. `py -m venv .venv`
4. `.venv\Scripts\Activate.ps1`
5. `pip install -r requirements.txt`
6. `alembic upgrade head`
7. `python -m app.seed`
8. `uvicorn app.main:app --reload --port 8082`

Swagger: http://localhost:8082/docs
OpenAPI: http://localhost:8082/openapi.json
