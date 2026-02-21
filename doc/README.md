# Project documentation

This folder holds docs that Cursor and humans can use to understand and work on the project.

| File | Purpose |
|------|--------|
| **SPEC.md** | Project specification: components, data models, tools, flows, dependencies. |
| **MEMORY.md** | Decisions, conventions, gotchas, and “where to change what.” |
| **RULES.md** | Rules for AI/Cursor: code style, data, docs, and scope. |
| **requirements-template.txt** | Template and format reference for adding entries to `requirements.txt`. |
| **BUSINESS-REQUIREMENTS.md** | **Where to add new business/feature requirements.** List of requirements with summary, criteria, status. |
| **business-requirements-template.md** | Template for each new requirement (copy into BUSINESS-REQUIREMENTS.md). |

Cursor rules that apply during editing live in **`.cursor/rules/`** (`.mdc` files). Those rules reference or summarize the content here so the agent gets consistent context.

**Quick links**

- New to the project → read **SPEC.md** then **MEMORY.md**.
- Editing code → follow **RULES.md** and the rules in `.cursor/rules/`.
- Adding a tool or changing data → update **SPEC.md** and **MEMORY.md** as needed.
