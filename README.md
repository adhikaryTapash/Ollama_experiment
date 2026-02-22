# Advanced Inventory Assistant

A CLI inventory assistant powered by **Ollama** and local LLM tool-calling. Query product catalog, stock levels, locations, transaction history, and inventory value using natural language. Data is stored in local JSON files; an optional external REST API (via Postgres-backed operations) can be enabled for additional data sources.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Example Queries](#example-queries)
- [Project Structure](#project-structure)
- [Optional: External API](#optional-external-api)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [License](#license)

---

## Features

| Feature | Description |
|--------|-------------|
| **Natural language queries** | Ask about stock, prices, locations, and history in plain English. |
| **Tool-calling** | The assistant uses defined tools to fetch real data from JSON (and optionally from an external API). |
| **Fuzzy search** | Match products by partial name or brand (case-insensitive). |
| **Low-stock alerts** | Report of items below minimum stock levels. |
| **Transaction history** | IN/OUT movement history for any product. |
| **Inventory valuation** | Total dollar value of warehouse stock. |
| **Brand filtering** | List all products by brand (e.g. Logitech, Sony). |
| **Configurable model** | Choose the Ollama model via `OLLAMA_MODEL` in `.env` (must support tools). |

---

## Prerequisites

| Requirement | Version / Notes |
|-------------|-----------------|
| **Python** | 3.8+ |
| **Ollama** | [ollama.com](https://ollama.com) — installed and running locally |
| **Ollama model** | A **tool-capable** model (e.g. `functiongemma`). The default is `functiongemma`; set `OLLAMA_MODEL` in `.env` to override. |

**Ollama models in this project**

- **functiongemma** — Recommended. Supports tool/function calling and is the default (`OLLAMA_MODEL=functiongemma`). Use this for the full assistant experience (inventory tools and optional external API).
- **Phi-3** — Also available in the project. You can install it with `ollama pull phi3` (appears as `phi3:latest` in `ollama list`). Phi-3 does **not** support tool calling in Ollama, so this app will not run with it; if you set `OLLAMA_MODEL=phi3` or `phi3:latest`, the app will exit with a clear message. Use **functiongemma** for this assistant.

> **Note:** Not all Ollama models support tool/function calling. Use a model that does (e.g. `functiongemma`); otherwise the app will report that the model does not support tools.

---

## Installation

### 1. Install Ollama

1. Download and install [Ollama](https://ollama.com) for your platform.
2. Start Ollama (it typically runs in the background after install).
3. Pull a tool-capable model (required for this app):

   ```bash
   ollama pull functiongemma
   ```

   Verify:

   ```bash
   ollama list
   ```

   You should see `functiongemma` (or `functiongemma:latest`) in the list.

### 2. Clone the repository

```bash
git clone <your-repo-url>
cd Ollama_experiment
```

### 3. Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

Confirm the environment is active (e.g. `(venv)` in the prompt).

### 4. Install dependencies

With the virtual environment activated:

```bash
pip install -r requirements.txt
```

### 5. Data files

Ensure these JSON files exist in the project root (sample data may be included):

| File | Purpose |
|------|---------|
| `products.json` | Product catalog (id, name, brand, category, price, unit) |
| `stocks.json` | Stock levels, min levels, warehouse locations |
| `transaction.json` | IN/OUT movement history |

If a file is missing, the app still runs but may return empty or limited results for related queries.

---

## Configuration

Optional configuration is done via environment variables. Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | Ollama model name used for chat and tool calls. Must support tools (e.g. `functiongemma`). | `functiongemma` |
| `DATABASE_URL` | PostgreSQL connection string (only for optional External API). | — |
| `API_SOURCE_NAME` | API source name in DB (only when using External API). | — |
| `EXTERNAL_API_BEARER_TOKEN` | Bearer token for external API calls (only when using External API). | — |

See `.env.example` for the full list and comments. Do not commit `.env` if it contains secrets.

---

## Usage

1. Ensure **Ollama is running** and a **tool-capable model** is available (e.g. `functiongemma`).
2. Activate the virtual environment.
3. Run the application:

   ```bash
   python app.py
   ```

4. Type your question at the `You:` prompt. Type `exit` or `quit` to end the session.

**Example:**

```
--- 🛠️  Advanced Inventory Assistant Ready ---
(Type 'exit' to quit)

You: How many Wireless Mouses are in the warehouse?
[10:00:00]   ... thinking ...
[10:00:01]   ... using tool: check_inventory ...
[10:00:02]   ... getting answer ...
Assistant: There are 25 Wireless Mouses in stock, located at A-102...

You: What's the total value of our inventory?
...

You: exit
```

---

## Example Queries

**Stock & availability**

- *"How many Wireless Mouses are currently in the warehouse?"*
- *"Do we have any Office Chairs left?"*
- *"What is the stock level for the Standing Desk?"*

**Location**

- *"Where can I find the Mechanical Keyboards?"*
- *"What is the shelf location for PROD-004?"*

**Brand**

- *"How much Logitech gear do we have in stock?"*
- *"Find all products by Keychron."*

**Reports & value**

- *"Which items are low on stock?"*
- *"What is the total inventory value?"*
- *"Show me recent transactions for the USB-C Hub."*

---

## Project Structure

```
Ollama_experiment/
├── app.py                 # Main application: chat loop, tools, Ollama integration
├── env_loader.py           # Loads .env from project root
├── external_api.py        # Optional: external REST API tool (Postgres-backed operations)
├── products.json          # Product catalog
├── stocks.json            # Stock levels and locations
├── transaction.json       # IN/OUT movement history
├── requirements.txt       # Python dependencies
├── .env.example           # Example environment variables (copy to .env)
├── doc/                    # Specification, rules, and requirements
│   ├── SPEC.md            # Data models, tools, flows
│   └── MEMORY.md          # Conventions and where to change what
├── scripts/               # Utilities (e.g. sync Swagger to DB for external API)
├── db/                    # SQL migrations for external API (optional)
├── conversations/         # Optional: save conversation output
└── venv/                  # Virtual environment (create via python -m venv venv)
```

---

## Optional: External API

When `DATABASE_URL`, `API_SOURCE_NAME` (or `API_SOURCE_ID`), and `EXTERNAL_API_BEARER_TOKEN` are set in `.env`, the app loads API operations from Postgres and adds a generic `call_external_api`-style tool (e.g. for listing airports, hotels, or other REST endpoints). Operations are populated by the writer script `scripts/sync_swagger_to_db.py`; schema is in `db/001_api_sources_and_operations.sql`. See `doc/requirements/external-api-tool-requirements.md` and `doc/SPEC.md` for details.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| `ModuleNotFoundError: No module named 'ollama'` | Activate the virtual environment and run `pip install -r requirements.txt`. |
| Connection error or no response | Ensure Ollama is running (`ollama list` succeeds) and the model in `OLLAMA_MODEL` is pulled. |
| **Model not found (404)** | Run `ollama pull <model>` with the exact name from `ollama list` (e.g. `functiongemma` or `functiongemma:latest`). Set `OLLAMA_MODEL` in `.env` to match. |
| **"does not support tools" (400)** | The model in `OLLAMA_MODEL` does not support tool calling. Set `OLLAMA_MODEL=functiongemma` (or another tool-capable model) in `.env`. |
| Empty or incorrect data in answers | Confirm `products.json`, `stocks.json`, and `transaction.json` exist and follow the structure described in `doc/SPEC.md`. |

---

## Documentation

- **`doc/SPEC.md`** — Data models, tools, user flows, file layout.
- **`doc/MEMORY.md`** — Conventions, decisions, and where to change what.
- **`doc/RULES.md`** — Rules for code, data, and docs.
- **`doc/requirements/external-api-tool-requirements.md`** — External API tool setup and multi-tenant notes.

---

## License

Use and modify as needed for your project.
