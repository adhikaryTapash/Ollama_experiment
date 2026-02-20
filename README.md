# Advanced Inventory Assistant

A conversational inventory assistant powered by **Ollama** and local LLM tool-calling. Query product catalog, stock levels, locations, transaction history, and inventory value using natural language. Data is stored in local JSON files—no database required.

---

## Features

- **Natural language queries** — Ask about stock, prices, locations, and history in plain English.
- **Tool-calling** — The assistant uses defined tools to fetch real data from your JSON files.
- **Fuzzy search** — Match products by partial name or brand (case-insensitive).
- **Low-stock alerts** — Get a report of items below minimum stock levels.
- **Transaction history** — View IN/OUT movements for any product.
- **Inventory valuation** — Calculate total dollar value of warehouse stock.
- **Brand filtering** — List all products by brand (e.g. Logitech, Sony).

---

## Prerequisites

| Requirement | Version / Notes |
|-------------|-----------------|
| **Python** | 3.8 or higher |
| **Ollama** | [ollama.com](https://ollama.com) — must be installed and running locally |
| **Model** | `functiongemma` (pulled via Ollama) |

---

## Installation

### Step 1: Install Ollama

1. **Download and install Ollama** for your OS:
   - **Windows / macOS / Linux:** [https://ollama.com](https://ollama.com)
2. **Start Ollama** (it usually runs in the background after install).
3. **Pull the required model** (function-calling capable):

   ```bash
   ollama pull functiongemma
   ```

   Verify it’s available:

   ```bash
   ollama list
   ```

   You should see `functiongemma` in the list.

### Step 2: Clone or Download the Project

```bash
git clone <your-repo-url>
cd Ollama_experiment
```

*(Or extract the project folder if you downloaded a ZIP.)*

### Step 3: Create a Virtual Environment

Using a virtual environment keeps dependencies isolated from your system Python.

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

You should see `(venv)` in your prompt when the environment is active.

### Step 4: Install Python Dependencies

With the virtual environment **activated**, run:

```bash
pip install -r requirements.txt
```

This installs the `ollama` Python client and its dependencies (e.g. `httpx`, `pydantic`).

### Step 5: Verify Data Files

Ensure these JSON files exist in the project root (they are used by the app):

| File | Purpose |
|------|--------|
| `products.json` | Product catalog (name, brand, category, price, unit) |
| `stocks.json` | Stock levels, min levels, warehouse locations |
| `transaction.json` | IN/OUT movement history |
| `data.json` | Additional sample data (if used) |

If any are missing, the app may return empty or error responses for related queries.

---

## Usage

1. **Ensure Ollama is running** and the `functiongemma` model is pulled.
2. **Activate the virtual environment** (see Step 3 above).
3. **Run the application:**

   ```bash
   python app.py
   ```

4. **Type your question** at the `You:` prompt. Type `exit` or `quit` to stop.

**Example session:**

```
--- 🛠️  Advanced Inventory Assistant Ready ---
(Type 'exit' to quit)

You: How many Wireless Mouses are in the warehouse?
Assistant: [Uses check_inventory and responds with stock and location]

You: What's the total value of our inventory?
Assistant: [Uses calculate_inventory_value and responds with the total]

You: exit
```

---

## Example Queries

### Stock & availability
- *"How many Wireless Mouses are currently in the warehouse?"*
- *"Do we have any Office Chairs left?"*
- *"What is the stock level for the Standing Desk?"*

### Location
- *"Where can I find the Mechanical Keyboards?"*
- *"What is the shelf location for PROD-004?"*
- *"Tell me the location and quantity of the BenQ Desk Lamp."*

### Brand
- *"How much Logitech gear do we have in stock?"*
- *"Check the inventory for Sony products."*
- *"Find all products by Keychron."*

### Reports & value
- *"Which items are low on stock?"*
- *"What is the total inventory value?"*
- *"Show me recent transactions for the USB-C Hub."*

### Multi-attribute
- *"Give me a status update on the Herman Miller Office Chair."*
- *"How many 27-inch Monitors are at location A-105?"*

---

## Tips for Best Results

- **Use product names from the catalog** — e.g. "USB-C Hub" from `products.json` gives reliable matches.
- **Refer to product IDs** — e.g. *"Check stock for PROD-009"* for a direct lookup.
- **Keep Ollama running** — The app talks to your local Ollama server; if it’s stopped, the app will fail to get responses.

---

## Project Structure

```
Ollama_experiment/
├── app.py              # Main application and tool definitions
├── products.json       # Product catalog
├── stocks.json         # Stock levels and locations
├── transaction.json    # IN/OUT movement history
├── data.json           # Additional sample data
├── requirements.txt    # Python dependencies (ollama>=0.6.1)
├── README.md           # This file
└── venv/               # Virtual environment (create with python -m venv venv)
```

---

## Troubleshooting

| Issue | What to do |
|-------|------------|
| `ModuleNotFoundError: No module named 'ollama'` | Activate the venv and run `pip install -r requirements.txt`. |
| Connection error or no response | Ensure Ollama is running (`ollama list` works) and you have pulled `functiongemma`. |
| "Model not found" | Run `ollama pull functiongemma`. |
| Empty or wrong data in answers | Check that `products.json`, `stocks.json`, and `transaction.json` exist and have the expected structure. |

---

## License

Use and modify as needed for your project.
