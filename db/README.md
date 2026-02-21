# Database (Postgres) for External API tool

Used by the **external API tool** (see `doc/requirements/external-api-tool-requirements.md`).

- **Writer** (e.g. `scripts/sync_swagger_to_db.py`) needs **read+write** access.
- **App** (`app.py` via `external_api.py`) uses **read-only** access.

## Setup

1. Create a database and a user (e.g. one with read+write for the writer, one read-only for the app).
2. Run the DDL. Either use **psql** (if in PATH) or the **Python script** (uses `DATABASE_URL` from `.env`):
   ```bash
   # Option A: psql (Windows: add PostgreSQL bin to PATH, or use full path to psql.exe)
   psql -U postgres -d Experiments -f db/001_api_sources_and_operations.sql

   # Option B: Python (no psql needed)
   python scripts/run_ddl.py
   ```
3. Run the writer to backfill from Swagger:
   ```bash
   set DATABASE_URL=postgresql://user:pass@host:5432/dbname
   set SWAGGER_URL=https://.../swagger/v1/swagger.json
   set SOURCE_NAME=Flytel
   python scripts/sync_swagger_to_db.py
   ```
4. Run the app with `DATABASE_URL`, `API_SOURCE_NAME`, and `EXTERNAL_API_BEARER_TOKEN` set.
