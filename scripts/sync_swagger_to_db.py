"""
Writer job: fetch Swagger from URL, parse operations, write to Postgres.
Run manually or on a schedule. Requires write access to the database.

Config: set env vars directly or use a .env file in the project root.
  DATABASE_URL    - Postgres connection string (read+write).
  SWAGGER_URL     - URL of the Swagger/OpenAPI JSON.
  SOURCE_NAME     - Name for this API source (e.g. "Flytel"). Used for upsert.
  BASE_URL        - Optional. If not set, taken from Swagger servers[0].url.
"""

# Load .env first (finds project root from this script's location)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import env_loader
env_loader.load_project_env(__file__)

import json
import os
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def fetch_swagger(url):
    """Fetch Swagger/OpenAPI JSON from URL."""
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_base_url(doc, fallback_url, swagger_url=None):
    """Get base URL from OpenAPI doc, fallback env, or derive from swagger_url."""
    servers = doc.get("servers")
    if servers and len(servers) > 0:
        s = servers[0]
        url = s.get("url", "").rstrip("/")
        if url:
            return url
    if fallback_url:
        return fallback_url.rstrip("/")
    # Derive from Swagger URL: e.g. https://host/path/swagger.json -> https://host
    if swagger_url:
        parsed = urlparse(swagger_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def parse_operations(doc):
    """Yield (method, path_template, operation_id, summary, tag, parameters_schema, request_body_ref)."""
    paths = doc.get("paths") or {}
    for path_template, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            operation_id = op.get("operationId") or f"{method.upper()}_{path_template}"
            summary = (op.get("summary") or op.get("description") or "")[:2048]
            tags = op.get("tags")
            tag = tags[0] if tags else None
            parameters = op.get("parameters")
            parameters_schema = None
            if parameters:
                parameters_schema = [
                    {
                        "name": p.get("name"),
                        "in": p.get("in"),
                        "required": p.get("required", False),
                        "schema": p.get("schema"),
                    }
                    for p in parameters
                    if isinstance(p, dict)
                ]
            request_body = op.get("requestBody")
            request_body_schema_ref = None
            if request_body and isinstance(request_body, dict):
                content = request_body.get("content") or {}
                for ct, media in content.items():
                    if "json" in ct and isinstance(media, dict):
                        schema = media.get("schema")
                        if isinstance(schema, dict) and "$ref" in schema:
                            request_body_schema_ref = schema["$ref"].split("/")[-1]
                        else:
                            request_body_schema_ref = "(has body)"
                        break
            yield (
                method.upper(),
                path_template,
                operation_id,
                summary,
                tag,
                parameters_schema,
                request_body_schema_ref,
            )


def run():
    database_url = os.environ.get("DATABASE_URL")
    swagger_url = os.environ.get("SWAGGER_URL")
    source_name = os.environ.get("SOURCE_NAME")
    base_url_override = os.environ.get("BASE_URL")

    if not database_url or not swagger_url or not source_name:
        print(
            "Set DATABASE_URL, SWAGGER_URL, and SOURCE_NAME.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Fetching Swagger from {swagger_url} ...")
    try:
        doc = fetch_swagger(swagger_url)
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"Failed to fetch or parse Swagger: {e}", file=sys.stderr)
        sys.exit(1)

    base_url = get_base_url(doc, base_url_override, swagger_url)
    if not base_url:
        print("Could not determine base_url. Set BASE_URL in .env or ensure SWAGGER_URL is a full URL.", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to Postgres ...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_sources (name, base_url, swagger_url, raw_swagger, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (name) DO UPDATE SET
                    base_url = EXCLUDED.base_url,
                    swagger_url = EXCLUDED.swagger_url,
                    raw_swagger = EXCLUDED.raw_swagger,
                    updated_at = NOW()
                RETURNING id
                """,
                (source_name, base_url, swagger_url, Json(doc)),
            )
            row = cur.fetchone()
            api_source_id = row[0]

            cur.execute("DELETE FROM api_operations WHERE api_source_id = %s", (api_source_id,))

            count = 0
            for (
                method,
                path_template,
                operation_id,
                summary,
                tag,
                parameters_schema,
                request_body_schema_ref,
            ) in parse_operations(doc):
                cur.execute(
                    """
                    INSERT INTO api_operations
                    (api_source_id, operation_id, method, path_template, summary, tag,
                     parameters_schema, request_body_schema_ref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        api_source_id,
                        operation_id,
                        method,
                        path_template,
                        summary or None,
                        tag,
                        Json(parameters_schema) if parameters_schema else None,
                        request_body_schema_ref,
                    ),
                )
                count += 1

        conn.commit()
        print(f"Done. Source '{source_name}' id={api_source_id}, operations={count}")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
