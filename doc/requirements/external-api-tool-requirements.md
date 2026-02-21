# External API tool – requirements and design

**Status:** Draft  
**Added:** 2025-02-21  
**Context:** One generic tool that reads Swagger-derived operations from Postgres and executes third-party APIs (e.g. Flytel); precomputed build (writer job outside the app).

---

## 1. Overview

- **Goal:** A tool that lets the assistant call a client’s REST API using a Swagger/OpenAPI definition. The LLM chooses an operation and parameters from user input; the app executes the request and returns the **raw response body** only.
- **Auth:** Bearer token (JWT) for now; design allows swapping to API key later.
- **Base URL:** Configurable (per API source).
- **Build strategy:** **Precomputed** — a separate writer job fetches Swagger, parses operations, and writes to Postgres; the app only reads from Postgres and never parses Swagger.

---

## 2. High-level flow

| Component | Responsibility |
|-----------|----------------|
| **Writer (separate process)** | Fetch Swagger from URL → parse paths/operations → write **raw Swagger** + **operations** to Postgres. Runs on a schedule or manually. |
| **App (`app.py`)** | At startup (or first use): **read only** from Postgres (operations table), build the generic tool, run the chat loop. On tool call: build HTTP request from operation_id + params, send request, return response body. No Swagger parsing in the app. |

---

## 3. Database (Postgres)

App uses **read-only** access. Writer needs read+write.

### 3.1 Table: `api_sources`

Stores one row per API (e.g. Flytel).

| Column       | Type      | Description |
|-------------|-----------|-------------|
| `id`        | PK        | UUID or serial. |
| `name`      | string    | e.g. `"Flytel"`. |
| `base_url`  | string    | e.g. `https://app-api-flytel-e2ehbed2hng3g6hj.norwayeast-01.azurewebsites.net`. |
| `swagger_url` | string  | e.g. `.../swagger/v1/swagger.json`. |
| `raw_swagger` | JSONB   | Full Swagger/OpenAPI document. |
| `updated_at` | timestamp | When the writer last refreshed. |

### 3.2 Table: `api_operations`

One row per operation (path + method).

| Column               | Type    | Description |
|----------------------|---------|-------------|
| `id`                 | PK      | UUID or serial. |
| `api_source_id`      | FK      | References `api_sources.id`. |
| `operation_id`       | string  | From Swagger `operationId` (e.g. `Auth_Login`, `Airports_GetPassengers`). |
| `method`             | string  | GET, POST, PUT, PATCH, DELETE. |
| `path_template`      | string  | e.g. `/api/airports/{airportId}/passengers`. |
| `summary`            | string  | From Swagger `summary` (for LLM tool description). |
| `tag`                | string  | Optional; from Swagger `tags[0]`. |
| `parameters_schema`   | JSONB   | Optional; path/query/header params (name, in, required, schema). |
| `request_body_schema_ref` | string | Optional; e.g. body schema name or “has body” flag. |

---

## 4. Writer job (outside the app)

- **Runs:** On a schedule (cron, task queue) or manually (CLI script).
- **Input:** Config: Swagger URL(s), Postgres connection (write access).
- **Steps:**
  1. For each Swagger URL: HTTP GET the Swagger JSON.
  2. Upsert `api_sources`: `base_url` (from `servers[0].url` or config), `swagger_url`, `raw_swagger`, `updated_at`.
  3. Parse `paths`: for each path and method, extract `operationId`, `summary`, `tags`, path template, parameters, requestBody.
  4. For each operation: upsert `api_operations` (`api_source_id`, `operation_id`, `method`, `path_template`, `summary`, `tag`, `parameters_schema`, optional body ref).
- **Output:** Postgres contains up-to-date `raw_swagger` and a flat list of `api_operations` for the app to read.

---

## 5. App side (`app.py` or loader module)

- **When to load:** At **startup** (recommended so the first user request is fast).
- **Steps:**
  1. Read config: Postgres connection (read-only), which API source to use (by name or id), Bearer token for the external API.
  2. Query Postgres:
     - `SELECT id, base_url FROM api_sources WHERE name = ?` (or by id).
     - `SELECT operation_id, method, path_template, summary, tag, parameters_schema FROM api_operations WHERE api_source_id = ? ORDER BY tag, operation_id`.
  3. Build **one generic tool**, e.g. `call_external_api(operation_id, path_params, query_params, request_body)`.
  4. Tool description: include the list of operations (e.g. one line per operation: `- {operation_id}: {method} {path_template} — {summary}`) so the LLM can choose `operation_id` and fill path/query/body from the user message.
  5. Keep in memory: `base_url`, Bearer token, operation list, and the tool definition.
  6. In the chat loop, when the model calls `call_external_api`:
     - Resolve `path_template` with `path_params` (e.g. replace `{airportId}`).
     - Build URL: `base_url + path_template` + query string from `query_params`.
     - Send HTTP request (method, `Authorization: Bearer <token>`, optional JSON body).
     - Return **only the response body** (string/JSON) as the tool result.

No Swagger parsing in the app — only SQL and request building.

---

## 6. Config and credentials

**Writer:**

- Swagger URL(s).
- Postgres connection string (read+write).
- Optionally per-source base URL if not taken from Swagger `servers`.

**App:**

- Postgres connection string (read-only).
- API source identifier (name or id).
- Bearer token for the external API (env var or config; later replace with API key when provided).

---

## 7. Tool shape and scope

- **Tool type:** One generic tool: `call_external_api(operation_id, path_params, query_params, request_body)`.
- **Scope:** All HTTP methods (GET, POST, PUT, PATCH, DELETE) and all tags/paths from the stored operations.
- **Result:** Raw response body only (no status code or headers in the tool result).
- **Security:** Do not log request/response bodies; use Bearer token from config/env.

---

## 8. Implementation order

1. **DB:** Create `api_sources` and `api_operations` (migrations or DDL scripts).
2. **Writer:** Script that fetches the Flytel Swagger URL, parses paths/operations, writes to `api_sources` and `api_operations`. Run once manually to backfill.
3. **App:** At startup, read from Postgres, build the generic tool, add it to the Ollama tools list, and implement the `call_external_api` branch in the tool-call loop (build URL, send request, return body only).
4. **Config:** Wire base URL, Swagger URL, DB credentials, and Bearer token (env or config file).

---

## 8b. Implemented artifacts (reference)

| Item | Location |
|------|----------|
| DDL | `db/001_api_sources_and_operations.sql` |
| Writer script | `scripts/sync_swagger_to_db.py` |
| App loader & executor | `external_api.py`; used by `app.py` at startup |
| Env (writer) | `DATABASE_URL`, `SWAGGER_URL`, `SOURCE_NAME`, optional `BASE_URL` |
| Env (app) | `DATABASE_URL`, `API_SOURCE_NAME` or `API_SOURCE_ID`, `EXTERNAL_API_BEARER_TOKEN` or `BEARER_TOKEN` |

**Run writer once (or on a schedule):**
```bash
set DATABASE_URL=postgresql://user:pass@host:5432/dbname
set SWAGGER_URL=https://app-api-flytel-..../swagger/v1/swagger.json
set SOURCE_NAME=Flytel
python scripts/sync_swagger_to_db.py
```

**Run app with external API:** set `DATABASE_URL`, `API_SOURCE_NAME` (e.g. `Flytel`), and `EXTERNAL_API_BEARER_TOKEN`, then `python app.py`. If any of these are missing, the app runs without the external API tool.

---

## 9. Reference: Flytel Swagger

- **Example Swagger URL:** `https://app-api-flytel-e2ehbed2hng3g6hj.norwayeast-01.azurewebsites.net/swagger/v1/swagger.json`
- **API:** Flytel Airport Hotel Management (airports, passengers, hotels, auth, dashboard, etc.).
- **Auth:** Most endpoints require JWT Bearer; use provided token for testing until API key is available.

---

## 10. Multi-tenant: same route, different tenants

### The scenario

- **Tenant 1:** Swagger URL A, has route `GET /api/customers` (e.g. operation_id `Customers_GetAll`).
- **Tenant 2:** Swagger URL B, has the same route `GET /api/customers` (same path, possibly same operation_id).
- **User says:** “Give me the list of customers.”

The same logical route exists on both tenants, but each tenant has a different **base URL** and **auth**. The app must call the correct tenant’s API; otherwise it would call the wrong backend or fail auth.

### Why it’s ambiguous

- In the DB you have two rows in `api_operations`: one for tenant 1 (`api_source_id` = Flytel), one for tenant 2 (`api_source_id` = Acme), both with e.g. path `/api/customers` and maybe the same `operation_id`.
- If the app loads **all** tenants’ operations into one tool list, “list of customers” could map to either tenant’s operation. The LLM has no way to know which tenant the user means unless we add tenant context or ask.

### Option A: One tenant per session (recommended)

**Idea:** Each run or each user session is bound to **one** API source (tenant). The app loads operations only for that tenant.

- **At startup (or login):** Config or user choice sets “current tenant” (e.g. `api_source_id` or name).
- **App loads:** Only operations for that tenant. So there is only one “get customers” operation in the tool list.
- **User says “give me the list of customers”:** The LLM picks the single `Customers_GetAll` (or whatever the operation_id is) for the current tenant → app uses that tenant’s `base_url` and Bearer token → correct API is called.

**Adding another tenant:** Add a new row in `api_sources` (new Swagger URL, base URL, name). Run the writer for that Swagger URL so `api_operations` is filled for the new tenant. No change to app logic: when the user (or config) selects “tenant 2”, the app loads operations for tenant 2 only. Same route name across tenants does not conflict, because only one tenant is active at a time.

**Pros:** No ambiguity; “list of customers” always means the current tenant. Simple tool list and simple tool implementation.  
**Cons:** User cannot mix tenants in one session without switching “current tenant”.

### Option B: All tenants in one tool (explicit tenant in the call)

**Idea:** The app loads operations for **all** tenants. The generic tool takes an extra parameter: **which API source (tenant)** to use.

- **Tool shape:** e.g. `call_external_api(api_source_id_or_name, operation_id, path_params, query_params, request_body)`.
- **Tool description:** List operations **per tenant**, e.g. “Flytel: Customers_GetAll — get customers; Acme: Customers_GetAll — get customers”.
- **User says “give me the list of customers”:** The LLM must choose both tenant and operation. That is ambiguous unless:
  - You define a **default tenant** (e.g. in system prompt: “If the user does not specify which client, use Flytel”), or
  - The user says which tenant (“Flytel: give me list of customers”), or
  - The app asks “Which tenant (Flytel or Acme)?” when both have a matching operation.

**Adding another tenant:** Same as today: new row in `api_sources`, writer run for new Swagger. The app already loads all sources, so the new tenant’s operations appear in the list. You may want to store per-tenant Bearer tokens (e.g. in config or a secure store keyed by `api_source_id`).

**Pros:** One session can call multiple tenants; user can say “Flytel customers” vs “Acme customers”.  
**Cons:** Ambiguity when the user does not name the tenant; need a default or clarification; tool description and LLM prompt become more complex.

### Recommendation

- Prefer **Option A (one tenant per session)** so that “give me the list of customers” is unambiguous and always uses the current tenant’s base URL and auth.
- Use **Option B** only if you need to support multiple tenants in the same session and are willing to enforce “user must name the tenant” or a default tenant in the system prompt.
