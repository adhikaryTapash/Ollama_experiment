# Project Rules (for Cursor / AI)

Use these when editing or extending the Ollama_experiment project.

---

## General

- **Read the spec first:** Use `doc/SPEC.md` for data models, tools, and flows. Use `doc/MEMORY.md` for conventions and gotchas.
- **No database:** Data lives in JSON files only. Do not introduce a DB unless the user explicitly asks.
- **Python 3.8+:** No syntax or stdlib that requires a newer version.

---

## Code

- **Single main app:** Core logic stays in `app.py`. Helpers and data loading live there; only the conversation saver is in `conversations/`.
- **Tool pattern:** New tools require: (1) a function that uses `load_data()` and returns a string, (2) an entry in the `tools` list in `run()`, (3) a branch in the `response.message.tool_calls` loop that calls the function and appends the result.
- **Errors:** Missing JSON files are handled by `load_data()` (returns `[]`). Prefer clear, user-facing messages when a product or brand is not found.
- **Ollama:** Model name is `functiongemma`; do not change it without updating the README and this doc.

---

## Data

- **IDs:** Keep `product_id` in `stocks.json` and `transaction.json` consistent with `products.json` `id`. No new ID schemes without updating SPEC and MEMORY.
- **Fuzzy match:** Product/brand matching is case-insensitive substring; preserve this behavior when changing lookup logic.

---

## Docs

- Update `doc/SPEC.md` when adding tools or changing data shapes.
- Update `doc/MEMORY.md` when adding conventions or known issues.
- Keep root `README.md` in sync with setup, usage, and file list.

---

## File / scope

- **app.py:** Inventory tools and chat loop only. Do not move tool definitions to another module unless the user requests a refactor.
- **conversations/:** Only for saving conversation text; do not add inventory logic there.
- **doc/:** Authoritative project docs; Cursor rules in `.cursor/rules/` can reference or summarize these.
