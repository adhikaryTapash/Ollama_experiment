# API operations: data needed to select the proper tool

## Current `api_operations` table (what we have)

| Column                 | Source        | Used for tool selection? |
|------------------------|---------------|---------------------------|
| operation_id           | Swagger `operationId` | Yes – name of the tool; we match keywords (airport, hotel) against it |
| method                | HTTP method   | Shown in description only |
| path_template         | Path with `{param}`   | Yes – we skip ops with `{` in path for “list” queries |
| summary               | Swagger summary/description | Yes – we match keywords against it |
| tag                   | First Swagger tag     | Not used for selection |
| parameters_schema     | Path/query params    | Used for building tool params, not selection |
| request_body_schema_ref | Body $ref    | Not used for selection |

## Why the wrong tool is selected

1. **Ambiguous keyword match**  
   Both “Settings_GetAirports” and “Airports_GetAirportHotel” contain “airport”. So for “list of airports” we rely on:
   - excluding operations whose `path_template` contains `{` when the user says “list”.

2. **No explicit “what this op is for”**  
   We never store:
   - which **resource** this op is about (airports vs hotels vs passengers),
   - whether it is a **list** (no path params) vs **get-by-id** (needs ids in path).

3. **Summary is unreliable**  
   Swagger summaries may be missing or generic. We can’t depend on them alone to decide “list all airports” vs “get one hotel at an airport”.

4. **Heuristics are brittle**  
   Using “list” in the user message + “{” in path works only for simple cases. It doesn’t scale if paths or phrasing change.

## Data we need to select the proper tool

We need **structured, queryable fields** so that:

- **“List of airports”** → only operations that (a) are about **airports**, and (b) are **list** operations (no path params).
- **“Hotels at airport X”** → operations about **hotels** that accept an **airport** context (may have path params).

Recommended additions to `api_operations`:

| Column / field        | Type     | Purpose |
|-----------------------|----------|---------|
| **has_path_params**  | BOOLEAN  | `true` if `path_template` contains `{...}`. Lets us separate “list” (no path params) from “get by id” (has path params) without parsing. |
| **resource**         | VARCHAR(64) | Main entity: e.g. `airports`, `hotels`, `passengers`, `pricelists`. Derived from path/tag/operation_id. Used to match “list of **airports**” → `resource = 'airports'`. |
| **action**           | VARCHAR(32) | Kind of operation: `list` (GET, no path params), `list_scoped` (GET, path ends in resource, e.g. passengers at airport), `get_by_id` (GET with path params), `create`/`update`/`delete`, or `other`. “List of X” → `action = 'list'` and `resource = 'X'`. |

With these we can:

1. **List-style queries** (“get me the list of airports”, “list of hotels”):
   - Filter: `resource` matches the entity (from user or mapping) and `action = 'list'` (or `has_path_params = false`).
2. **By-id or contextual queries** (“hotels at airport X”):
   - Filter: `resource = 'hotels'` and allow `has_path_params = true` so we get ops that take airportId/id.

Optionally, a short **user-facing description** (e.g. “Returns all airports” vs “Returns one hotel at an airport by airport and hotel id”) can be added later for the model; the above three fields are enough for **reliable selection** in code.

## Summary

- **Current data:** We only have free text (operation_id, summary) and path_template. That leads to ambiguous matches and fragile “list” heuristics.
- **Data we need:** Add **has_path_params**, **resource**, and **action** to `api_operations`, and populate them in the sync from Swagger (path + method). **resource** comes from the last path segment (e.g. passengers, airports). **action** includes `list_scoped` for GETs that return a list but have path params (e.g. `GET /api/airports/{airportId}/passengers` → resource=passengers, action=list_scoped). The Swagger **tag** (e.g. "Airports") is only grouping and is not used for tool selection. Then the app filters by **resource + action** so "list of passengers" includes Airports_GetPassengers.
