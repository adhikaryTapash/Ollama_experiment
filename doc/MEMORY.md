# Project Memory

Context, decisions, and conventions so Cursor (and humans) can work on this project consistently.

---

## Tech Choices

- **LLM:** Ollama with model `functiongemma` (chosen for tool-calling).
- **Data:** Local JSON files for inventory; optional Postgres for external API tool (precomputed Swagger operations).
- **Interface:** CLI; input via `input()`, no web UI.

---

## Conventions

- **Python:** 3.8+; standard library + `ollama` only in main app. Use `load_data()` in `app.py` for reading JSON (returns `[]` on missing file).
- **Product lookup:** Fuzzy, case-insensitive substring match on `name`; same idea for brand on `brand`.
- **IDs:** Products use ids like `PROD-001`; transactions use `T-1001`. Referenced in `stocks` and `transaction` via `product_id`.
- **Conversations:** Optional; `conversations/save_conversation.py` writes timestamped JSON; filenames can include an optional name prefix.

---

## Gotchas & Known Gaps

- **products.json:** Required by `app.py` but may not be in repo; if missing, catalog lookups fail. Create or restore it when testing.
- **Ollama must be running:** App talks to local Ollama; connection errors usually mean Ollama is not running or model not pulled.
- **Tool dispatch:** Inventory tools are static in `run()`. External API tools are **dynamic**: one tool per row in `api_operations` (built in `external_api.build_dynamic_tools_from_operations`). Tool-call handler dispatches by name: if name is in `operations_by_id` it runs the API; otherwise runs an inventory function.
- **Low stock:** Status is "LOW STOCK ALERT" when `quantity < min_stock_level`, else "OK".

---

## Where to Change What

| Change | File / place |
|--------|----------------|
| Add/remove tools | `app.py`: `tools` list, tool-call branch, new function |
| System prompt / behavior | `app.py`: `system_instruction` |
| Data shape | `products.json`, `stocks.json`, `transaction.json` + `load_data` and tool functions in `app.py` |
| Conversation export | `conversations/save_conversation.py` |
| **Add new Python dependency** | **`requirements.txt`** (project root); format reference: `doc/requirements-template.txt` |
| **Add new business requirement** | **`doc/BUSINESS-REQUIREMENTS.md`**; use format from `doc/business-requirements-template.md` |
| External API (Swagger → Postgres → app) | `doc/requirements/external-api-tool-requirements.md`, `db/`, `scripts/sync_swagger_to_db.py`, `external_api.py` |
| Project docs | `doc/` and root `README.md` |

---

## Cursor / AI Hints

- Inventory data stays in JSON; external API tool uses Postgres (read-only in app) for precomputed operations. See `doc/requirements/external-api-tool-requirements.md`.
- When adding tools, keep the same pattern: function in app, entry in `tools`, and one branch in the tool-call loop.
- Use this file and `doc/SPEC.md` for context; use `doc/RULES.md` and `.cursor/rules/*.mdc` for coding and project rules.
