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


def _operation_params_schema_list(op):
    """Return list of param dicts (name, in, required, schema) from operation. Handles JSONB from DB."""
    raw = op.get("parameters_schema")
    if not raw:
        return []
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict) and p.get("name")]
    return []


def _tool_parameters_from_operation(op):
    """Build Ollama tool parameters (properties + required) from operation's parameters_schema."""
    params_list = _operation_params_schema_list(op)
    properties = {}
    required = []
    for p in params_list:
        loc = (p.get("in") or "query").lower()
        if loc not in ("path", "query"):
            continue
        name = p.get("name")
        if not name:
            continue
        schema = p.get("schema") or {}
        prop_type = schema.get("type") or "string"
        properties[name] = {
            "type": prop_type,
            "description": f"{loc} parameter",
        }
        if p.get("required"):
            required.append(name)
    method = (op.get("method") or "").upper()
    if method in ("POST", "PUT", "PATCH"):
        properties["request_body"] = {
            "type": "object",
            "description": "JSON body for the request (optional)",
        }
    return {"type": "object", "properties": properties, "required": required}


def build_dynamic_tools_from_operations(operations_list):
    """
    Build one tool per DB operation. Each tool has name=operation_id and parameters from parameters_schema.
    Returns list of tool dicts for Ollama (type/function/name/description/parameters).
    """
    tools = []
    for op in operations_list:
        oid = op.get("operation_id")
        if not oid:
            continue
        summary = (op.get("summary") or "").strip() or "External API call"
        method = (op.get("method") or "").upper()
        path = (op.get("path_template") or "").strip()
        description = f"{summary} — {method} {path}"
        if len(description) > 300:
            description = description[:297] + "..."
        tools.append({
            "type": "function",
            "function": {
                "name": oid,
                "description": description,
                "parameters": _tool_parameters_from_operation(op),
            },
        })
    return tools


def args_to_request_parts(operation, args):
    """
    Split flat tool-call args into path_params, query_params, request_body using operation's parameters_schema.
    Returns (path_params, query_params, request_body).
    """
    if not isinstance(args, dict):
        args = {}
    params_list = _operation_params_schema_list(operation)
    path_params = {}
    query_params = {}
    for p in params_list:
        loc = (p.get("in") or "query").lower()
        name = p.get("name")
        if name not in args:
            continue
        if loc == "path":
            path_params[name] = args[name]
        elif loc == "query":
            query_params[name] = args[name]
    request_body = args.get("request_body") if args.get("request_body") is not None else args.get("body")
    return path_params, query_params, request_body


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
