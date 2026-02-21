# Project Specification: Advanced Inventory Assistant

## Overview

**Name:** Advanced Inventory Assistant (Ollama_experiment)  
**Purpose:** A CLI inventory assistant powered by **Ollama** and local LLM tool-calling. Users query product catalog, stock levels, locations, transaction history, and inventory value in natural language. All data is stored in local JSON files—no database.

---

## Core Components

| Component | Location | Role |
|-----------|----------|------|
| Main app & tool loop | `app.py` | Chat loop, tool definitions, Ollama `functiongemma` calls |
| Product catalog | `products.json` | Products: id, name, brand, category, price, unit |
| Stock levels | `stocks.json` | product_id, quantity, min_stock_level, location |
| Transactions | `transaction.json` | id, product_id, type (IN/OUT), qty, date |
| Conversation saver | `conversations/save_conversation.py` | Save conversation text to timestamped JSON in `conversations/` |
| External API (optional) | `external_api.py`, `scripts/sync_swagger_to_db.py`, `db/` | Call third-party REST APIs from Swagger; operations precomputed in Postgres |

---

## Data Models

### products.json (array of objects)

- `id` (string) — e.g. `"PROD-001"`
- `name` (string)
- `brand` (string)
- `category` (string)
- `price` (number)
- `unit` (string) — e.g. `"unit"`, `"box"`

### stocks.json (array of objects)

- `product_id` (string) — references `products.id`
- `quantity` (number)
- `min_stock_level` (number)
- `location` (string) — e.g. `"A-101"`

### transaction.json (array of objects)

- `id` (string) — e.g. `"T-1001"`
- `product_id` (string)
- `type` (string) — `"IN"` or `"OUT"`
- `qty` (number)
- `date` (string) — ISO 8601

---

## Tools (app.py)

The LLM is given these tools; **all data reads must go through them** (no direct file reads in model logic).

| Tool | Purpose | Parameters |
|------|---------|------------|
| `check_inventory` | Stock, location, status, price for one product | `product_name` (string) |
| `get_low_stock_report` | All products below min_stock_level | — |
| `get_recent_transactions` | IN/OUT history for one product | `product_name` (string) |
| `calculate_inventory_value` | Total $ value of all stock | — |
| `find_products_by_brand` | All products for a brand | `brand_name` (string) |
| `call_external_api` (optional) | Call external REST API by operation_id; returns raw response body | `operation_id`, `path_params`, `query_params`, `request_body` — loaded from Postgres when `DATABASE_URL`, `API_SOURCE_NAME`, and Bearer token are set |

**Matching:** Product/brand matching is **fuzzy, case-insensitive** (substring in name/brand). **External API:** Operations come from `api_operations` (filled by `scripts/sync_swagger_to_db.py`); see `doc/requirements/external-api-tool-requirements.md`.

---

## User Flows

1. User runs `python app.py` → sees prompt "You:".
2. User types a question → app sends it + system instruction to Ollama with tools.
3. If the model returns tool calls → app executes them (reads JSON via the functions above), appends tool results, gets a final reply from the model, prints "Assistant: ...".
4. If no tool calls → app prints the model reply directly.
5. User types `exit` or `quit` → app exits.

---

## Dependencies

- **Python:** 3.8+
- **Ollama:** Installed and running; model `functiongemma` must be pulled.
- **Python packages:** Listed in **`requirements.txt`** (project root). To add a new requirement, edit that file and use **`doc/requirements-template.txt`** as a format reference (version syntax, comments). Then run `pip install -r requirements.txt`.

---

## File Layout (reference)

```
Ollama_experiment/
├── app.py
├── external_api.py
├── products.json
├── stocks.json
├── transaction.json
├── data.json
├── requirements.txt
├── README.md
├── db/
│   ├── README.md
│   └── 001_api_sources_and_operations.sql
├── scripts/
│   └── sync_swagger_to_db.py
├── conversations/
│   ├── README.md
│   └── save_conversation.py
├── doc/
│   ├── README.md
│   ├── SPEC.md
│   ├── MEMORY.md
│   ├── RULES.md
│   ├── requirements-template.txt
│   ├── BUSINESS-REQUIREMENTS.md
│   └── business-requirements-template.md
└── .cursor/rules/
    └── *.mdc
```

---

## Out of Scope (current version)

- No REST API; CLI only.
- No authentication (inventory); external API uses Bearer token from env.
- No writing to JSON (read-only tools for inventory).
- `data.json` is optional/sample; core app uses `products.json`, `stocks.json`, `transaction.json`. Postgres is optional (only when using the external API tool).
