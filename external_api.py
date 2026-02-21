"""
External API tool: load operations from Postgres (precomputed by scripts/sync_swagger_to_db.py)
and execute requests. App reads only; no Swagger parsing here.
"""

import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

try:
    import psycopg2
except ImportError:
    psycopg2 = None


def load_api_source_and_operations(database_url, source_name=None, source_id=None):
    """
    Read from Postgres: one api_source and its operations.
    Returns (base_url, operations_list) or (None, None) on missing config/DB/rows.
    operations_list: list of dicts with operation_id, method, path_template, summary, tag, parameters_schema.
    """
    if not database_url or not (source_name or source_id):
        return None, None
    if not psycopg2:
        return None, None

    try:
        conn = psycopg2.connect(database_url)
    except Exception:
        return None, None

    try:
        with conn.cursor() as cur:
            if source_id is not None:
                cur.execute(
                    "SELECT id, base_url FROM api_sources WHERE id = %s",
                    (source_id,),
                )
            else:
                cur.execute(
                    "SELECT id, base_url FROM api_sources WHERE name = %s",
                    (source_name,),
                )
            row = cur.fetchone()
            if not row:
                return None, None
            api_source_id, base_url = row

            cur.execute(
                """
                SELECT operation_id, method, path_template, summary, tag, parameters_schema
                FROM api_operations
                WHERE api_source_id = %s
                ORDER BY tag, operation_id
                """,
                (api_source_id,),
            )
            rows = cur.fetchall()
            operations = [
                {
                    "operation_id": r[0],
                    "method": r[1],
                    "path_template": r[2],
                    "summary": r[3] or "",
                    "tag": r[4],
                    "parameters_schema": r[5],
                }
                for r in rows
            ]
        return base_url.rstrip("/"), operations
    finally:
        conn.close()


def resolve_operation_with_openai(user_message, operations_list, api_key):
    """
    Ask OpenAI which API operation to call and with what parameters.
    Returns dict with operation_id, path_params, query_params, request_body, or None on failure.
    Works with any third-party API; no hardcoded operation names.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None
    if not api_key or not operations_list:
        return None

    # Compact list for the prompt (operation_id, method, path, summary)
    ops_text = "\n".join(
        f"- {op['operation_id']}: {op['method']} {op['path_template']} — {op['summary'][:100]}"
        for op in operations_list[:150]
    )
    if len(operations_list) > 150:
        ops_text += f"\n... and {len(operations_list) - 150} more operations."

    system = (
        "You choose which API operation to call based on the user's request. "
        "Reply with a single JSON object only, no other text. Use this exact shape:\n"
        '{"operation_id": "<operationId from the list>", "path_params": {} or {"paramName": "value"}, '
        '"query_params": {} or {"key": "value"}, "request_body": null or {...}}\n'
        "path_params: fill path placeholders (e.g. airportId, id). query_params: for GET query string. "
        "request_body: only for POST/PUT/PATCH; null for GET/DELETE. Use empty objects {} where nothing is needed."
    )
    user = f"Available operations:\n{ops_text}\n\nUser request: {user_message}\n\nRespond with JSON only:"

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        # Extract JSON (in case of markdown code block)
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
        data = json.loads(text)
        operation_id = data.get("operation_id")
        if not operation_id:
            return None
        return {
            "operation_id": operation_id,
            "path_params": data.get("path_params") or {},
            "query_params": data.get("query_params") or {},
            "request_body": data.get("request_body"),
        }
    except Exception:
        return None


def resolve_operation_with_ollama(user_message, operations_list, model="functiongemma"):
    """
    Ask Ollama (e.g. functiongemma) which API operation to call and with what parameters.
    No API key needed. Returns dict with operation_id, path_params, query_params, request_body, or None on failure.
    """
    try:
        import ollama
    except ImportError:
        return None
    if not operations_list:
        return None

    ops_text = "\n".join(
        f"- {op['operation_id']}: {op['method']} {op['path_template']} — {op['summary'][:100]}"
        for op in operations_list[:150]
    )
    if len(operations_list) > 150:
        ops_text += f"\n... and {len(operations_list) - 150} more operations."

    system = (
        "You choose which API operation to call based on the user's request. "
        "Reply with a single JSON object only, no other text. Use this exact shape:\n"
        '{"operation_id": "<operationId from the list>", "path_params": {} or {"paramName": "value"}, '
        '"query_params": {} or {"key": "value"}, "request_body": null or {...}}\n'
        "path_params: fill path placeholders (e.g. airportId, id). query_params: for GET query string. "
        "request_body: only for POST/PUT/PATCH; null for GET/DELETE. Use empty objects {} where nothing is needed."
    )
    user = f"Available operations:\n{ops_text}\n\nUser request: {user_message}\n\nRespond with JSON only:"

    try:
        resp = ollama.chat(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        text = (resp.message.content or "").strip()
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
        data = json.loads(text)
        operation_id = data.get("operation_id")
        if not operation_id:
            return None
        return {
            "operation_id": operation_id,
            "path_params": data.get("path_params") or {},
            "query_params": data.get("query_params") or {},
            "request_body": data.get("request_body"),
        }
    except Exception:
        return None


def build_external_api_tool(operations_list):
    """
    Build the single generic tool definition for Ollama, with operation list in the description.
    """
    lines = [
        "Call the external API. Choose operation_id from the list below and provide path_params, query_params, and request_body as needed.",
        "",
        "Available operations (operation_id: METHOD path — summary):",
    ]
    for op in operations_list[:200]:  # cap so description is not huge
        lines.append(
            f"  - {op['operation_id']}: {op['method']} {op['path_template']} — {op['summary'][:80]}"
        )
    if len(operations_list) > 200:
        lines.append(f"  ... and {len(operations_list) - 200} more.")

    description = "\n".join(lines)

    return {
        "type": "function",
        "function": {
            "name": "call_external_api",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "Operation ID from the list above (e.g. Auth_Login, Airports_GetPassengers)",
                    },
                    "path_params": {
                        "type": "object",
                        "description": "Path parameters: keys match placeholders in path (e.g. airportId, id)",
                    },
                    "query_params": {
                        "type": "object",
                        "description": "Query string parameters",
                    },
                    "request_body": {
                        "type": "object",
                        "description": "JSON body for POST/PUT/PATCH; omit for GET/DELETE",
                    },
                },
                "required": ["operation_id"],
            },
        },
    }


def _fill_path_template(template, path_params):
    """Replace {name} in template with path_params.get('name')."""
    if not path_params:
        return template
    result = template
    for key, value in path_params.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def _build_url(base_url, path_template, path_params, query_params):
    path = _fill_path_template(path_template, path_params)
    url = base_url + path
    if query_params and isinstance(query_params, dict):
        filtered = {k: v for k, v in query_params.items() if v is not None and v != ""}
        if filtered:
            url += "?" + urlencode(filtered)
    return url


def execute_external_api(base_url, bearer_token, operations_by_id, operation_id, path_params=None, query_params=None, request_body=None):
    """
    Execute one API call. Returns raw response body as string, or an error message.
    """
    op = operations_by_id.get(operation_id)
    if not op:
        return f"Unknown operation_id: {operation_id}"

    path_params = path_params or {}
    query_params = query_params or {}
    if isinstance(path_params, str):
        try:
            path_params = json.loads(path_params)
        except json.JSONDecodeError:
            path_params = {}
    if isinstance(query_params, str):
        try:
            query_params = json.loads(query_params)
        except json.JSONDecodeError:
            query_params = {}
    if request_body is not None and isinstance(request_body, str):
        try:
            request_body = json.loads(request_body) if request_body.strip() else None
        except json.JSONDecodeError:
            request_body = None

    url = _build_url(base_url, op["path_template"], path_params, query_params)
    method = op["method"].upper()

    headers = {"Accept": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    body_bytes = None
    if request_body is not None and method in ("POST", "PUT", "PATCH"):
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(request_body).encode("utf-8")

    req = Request(url, data=body_bytes, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.read().decode("utf-8", errors="replace") or f"HTTP {e.code}: {e.reason}"
    except URLError as e:
        return f"Request failed: {e.reason}"
