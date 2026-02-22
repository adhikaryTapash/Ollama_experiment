# Business requirements

This file is the **single place to add new business requirements** (features, capabilities, user needs) for the Advanced Inventory Assistant. Cursor and the team use it to know what to build next.

**How to add a new requirement**

1. Open **`doc/business-requirements-template.md`** and copy the template block.
2. Fill in the fields (title, priority, summary, acceptance criteria, etc.).
3. Paste the filled block **below** in this file, under a new `## [REQ-XXX] ...` heading. Use the next number in sequence (e.g. REQ-002, REQ-003).
4. Optionally add a short line in **`doc/MEMORY.md`** under "Where to Change What" if the requirement implies a new file or major change.

---

## [REQ-001] Example: export low-stock report to file

**Priority:** Nice-to-have  
**Status:** Draft  
**Added:** 2025-02-21  

### Summary

Allow the user to export the low-stock report to a text or CSV file so it can be shared or processed elsewhere, instead of only viewing it in the chat.

### User / stakeholder

Warehouse or inventory manager who needs to send reports to procurement or management.

### Acceptance criteria

- [ ] User can ask the assistant to "export low stock report" or similar and get a file path in the response.
- [ ] The file contains the same information as the in-chat low-stock report (product name, quantity, min level).
- [ ] File is written under a known folder (e.g. `exports/` or project root) with a timestamped or predictable name.

### Notes / constraints

Should not require new Python dependencies if possible; use stdlib file writing. See `get_low_stock_report()` in `app.py`.

### Implementation hint

New tool (e.g. `export_low_stock_report`) in `app.py` that calls `get_low_stock_report()`, writes result to a file, returns the path. Add tool to `tools` list and tool-call branch. Optionally create `exports/` and add to `.gitignore`.

---

*(Add new requirements below.)*
