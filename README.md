# My Ollama Experiment

Ollama-powered inventory assistant with tool-calling. Uses local JSON data for products, stock, and transactions.

## Setup (venv)

1. **Create and activate a virtual environment**

   Windows (PowerShell):
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

   Windows (cmd):
   ```cmd
   python -m venv venv
   venv\Scripts\activate.bat
   ```

   Linux/macOS:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app** (with [Ollama](https://ollama.com) running and the `functiongemma` model pulled)
   ```bash
   python app.py
   ```

## Example Queries

### Simple Stock Inquiries
- "How many Wireless Mouses are currently in the warehouse?"
- "Do we have any Office Chairs left?"
- "What is the stock level for the Standing Desk?"

### Location-Based Queries
- "Where can I find the Mechanical Keyboards?"
- "What is the shelf location for PROD-004?"
- "Tell me the location and quantity of the BenQ Desk Lamp."

### Brand-Specific Queries
- "How much Logitech gear do we have in stock?"
- "Check the inventory for Sony products."
- "Is there any Keychron equipment available?"

### Multi-Attribute Queries
- "Give me a status update on the Herman Miller Office Chair."
- "How many 27-inch Monitors are at location A-105?"

## Tips for Better Results

- **Be specific with names:** Using the exact name from `products.json` (e.g. "USB-C Hub") helps the script find the match.
- **Identify by ID:** You can ask "Check the stock for PROD-009" for a direct hit.

## Data Files

- `products.json` – product catalog (name, brand, category, price, unit)
- `stocks.json` – stock levels, min levels, locations
- `transaction.json` – IN/OUT movement history
- `data.json` – additional sample data

## Running

1. Activate the virtual environment (see above).
2. Run: `python app.py`
3. Type your question at the prompt, or `exit` to quit.

Example:
```
--- 🛠️  Advanced Inventory Assistant Ready ---
(Type 'exit' to quit)

You: What is the price of wireless mouse
Assistant: ...
```
