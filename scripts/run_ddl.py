"""
Run the DB DDL (create api_sources and api_operations) using DATABASE_URL.
Use this if psql is not in your PATH. Loads .env from project root when present.

  python scripts/run_ddl.py
"""

import os
import sys
from pathlib import Path

# Load .env first (finds project root from this script's location)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import env_loader
env_loader.load_project_env(__file__)

try:
    import psycopg2
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Set DATABASE_URL in .env or environment.", file=sys.stderr)
        sys.exit(1)

    ddl_path = Path(__file__).resolve().parent.parent / "db" / "001_api_sources_and_operations.sql"
    if not ddl_path.exists():
        print(f"DDL file not found: {ddl_path}", file=sys.stderr)
        sys.exit(1)

    sql = ddl_path.read_text(encoding="utf-8")

    print("Connecting and running DDL ...")
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.close()
        print("Done. Tables api_sources and api_operations are ready.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
