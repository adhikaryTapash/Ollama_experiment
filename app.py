# Load .env first so all env vars are set for the rest of the app
import env_loader
env_loader.load_project_env(__file__)

import ollama
import json
import os
from pathlib import Path
from datetime import datetime


def _log(msg):
    """Print message with current time prefix [HH:MM:SS]."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- DATA UTILITY FUNCTIONS ---
def load_data(file_name):
    try:
        with open(file_name, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# --- CORE INVENTORY FUNCTIONS ---

def check_inventory(product_name):
    """Checks stock, location, status, and price of a specific item."""
    products = load_data('products.json')
    stocks = load_data('stocks.json')
    
    # Fuzzy search: matches if the input is part of the product name (case-insensitive)
    product = next((p for p in products if product_name.lower() in p['name'].lower()), None)
    
    if not product:
        return f"I couldn't find any product matching '{product_name}' in the catalog."
    
    stock = next((s for s in stocks if s['product_id'] == product['id']), None)
    
    if stock:
        status = "OK" if stock['quantity'] >= stock['min_stock_level'] else "LOW STOCK ALERT"
        return (f"--- {product['name']} ---\n"
                f"Brand: {product['brand']} | Category: {product['category']}\n"
                f"Price: ${product['price']:.2f} per {product['unit']}\n"
                f"Stock Level: {stock['quantity']} units\n"
                f"Location: {stock['location']}\n"
                f"Status: {status}")
    
    return f"Product {product['name']} found, but no stock information is available."

def get_low_stock_report():
    """Returns a list of all products below minimum stock levels."""
    products_list = load_data('products.json')
    products_map = {p['id']: p['name'] for p in products_list}
    stocks = load_data('stocks.json')
    
    low = [f"{products_map.get(s['product_id'], 'Unknown')}: {s['quantity']} left (Min: {s['min_stock_level']})" 
           for s in stocks if s['quantity'] < s['min_stock_level']]
    
    return "Items needing restock:\n- " + "\n- ".join(low) if low else "All stock levels are healthy."

def get_recent_transactions(product_name):
    """Shows the movement history (IN/OUT) for a specific product."""
    products = load_data('products.json')
    transactions = load_data('transaction.json')
    
    product = next((p for p in products if product_name.lower() in p['name'].lower()), None)
    if not product: return "Cannot find history for an unknown product."
    
    history = [f"[{t['date'][:10]}] {t['type']} {t['qty']} units" 
               for t in transactions if t['product_id'] == product['id']]
    
    return f"Transaction History for {product['name']}:\n" + "\n".join(history) if history else f"No recent transactions for {product['name']}."

def calculate_inventory_value():
    """Calculates the total monetary value of all stock in the warehouse."""
    products = {p['id']: p['price'] for p in load_data('products.json')}
    stocks = load_data('stocks.json')
    
    total_value = sum(products.get(s['product_id'], 0) * s['quantity'] for s in stocks)
    return f"The total valuation of all warehouse stock is currently ${total_value:,.2f}."

def find_products_by_brand(brand_name):
    """Lists all products belonging to a specific brand."""
    products = load_data('products.json')
    matches = [f"{p['name']} (${p['price']})" for p in products if brand_name.lower() in p['brand'].lower()]
    
    return f"Products by {brand_name}:\n- " + "\n- ".join(matches) if matches else f"No products found under the brand '{brand_name}'."


# --- EXTERNAL API (from Postgres, precomputed) ---

def _load_external_api_tool():
    """
    If config is set, load API source and operations from Postgres and return
    (tools_list_append, handler_data) or ([], None).
    handler_data: dict with base_url, bearer_token, operations_by_id for call_external_api.
    """
    try:
        from external_api import (
            load_api_source_and_operations,
            build_external_api_tool,
        )
    except ImportError:
        return [], None

    database_url = os.environ.get("DATABASE_URL")
    source_name = os.environ.get("API_SOURCE_NAME")
    source_id = os.environ.get("API_SOURCE_ID")
    if source_id:
        try:
            source_id = int(source_id)
        except ValueError:
            source_id = None
    bearer_token = os.environ.get("EXTERNAL_API_BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")

    if not database_url or not bearer_token:
        return [], None
    if not source_name and source_id is None:
        return [], None

    base_url, operations_list = load_api_source_and_operations(
        database_url, source_name=source_name, source_id=source_id
    )
    if not base_url or not operations_list:
        return [], None

    tool_def = build_external_api_tool(operations_list)
    operations_by_id = {op["operation_id"]: op for op in operations_list}
    handler_data = {
        "base_url": base_url,
        "bearer_token": bearer_token,
        "operations_by_id": operations_by_id,
    }
    return [tool_def], handler_data


# --- MAIN RUN LOOP ---

def run():
    inventory_tools = [
        {'type': 'function', 'function': {'name': 'check_inventory', 'description': 'Get price and stock for a specific item', 'parameters': {'type': 'object', 'properties': {'product_name': {'type': 'string'}}, 'required': ['product_name']}}},
        {'type': 'function', 'function': {'name': 'get_low_stock_report', 'description': 'List all items that are low on stock'}},
        {'type': 'function', 'function': {'name': 'get_recent_transactions', 'description': 'See history of IN/OUT movements for a product', 'parameters': {'type': 'object', 'properties': {'product_name': {'type': 'string'}}, 'required': ['product_name']}}},
        {'type': 'function', 'function': {'name': 'calculate_inventory_value', 'description': 'Calculate the total dollar value of the whole inventory'}},
        {'type': 'function', 'function': {'name': 'find_products_by_brand', 'description': 'Search for all products by a brand name', 'parameters': {'type': 'object', 'properties': {'brand_name': {'type': 'string'}}, 'required': ['brand_name']}}}
    ]

    external_tools, external_api_data = _load_external_api_tool()
    # Put external API tool first so the model prefers it for airport/hotel/passenger questions
    tools = (external_tools + inventory_tools) if external_api_data else inventory_tools
    if external_api_data:
        _log("--- External API tool loaded (from Postgres). ---")
    else:
        _log("--- (External API not loaded: set DATABASE_URL, API_SOURCE_NAME, EXTERNAL_API_BEARER_TOKEN in .env to enable.) ---")

    _log("--- 🛠️  Advanced Inventory Assistant Ready ---")
    _log("(Type 'exit' to quit)")

    if external_api_data:
        system_instruction = (
            "CRITICAL: For airports, passengers, hotels, flights, Flytel -> use call_external_api (e.g. Settings_GetAirports for airports). "
            "For products, stock, inventory, brand -> use inventory tools. If a tool errors, explain to the user."
        )
    else:
        system_instruction = (
            "You are an inventory manager. You have access to local data files via tools. "
            "When a user asks about prices, stock, or history, you MUST call the appropriate tool. "
            "If a tool returns an error, explain it to the user."
        )

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']: break

        _log("  ... thinking ...")
        messages = [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_input}
        ]

        # When user clearly asks for Flytel/external API data, only offer call_external_api so the model cannot pick an inventory tool
        external_keywords = ("airport", "passenger", "hotel", "flytel", "flight", "dashboard", "settings")
        user_lower = user_input.lower()
        use_tools = tools
        if external_api_data and any(kw in user_lower for kw in external_keywords):
            use_tools = [t for t in tools if t.get("function", {}).get("name") == "call_external_api"]

        response = ollama.chat(model='functiongemma', messages=messages, tools=use_tools)
        if response.message.tool_calls:
            for i, tool in enumerate(response.message.tool_calls):
                name = getattr(tool.function, "name", None) or (use_tools[i]["function"]["name"] if i < len(use_tools) else None) or "unknown"
                args = tool.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        args = {}
                if not isinstance(args, dict):
                    args = {}

                # When we forced external API for airport/passenger/hotel etc., default operation_id if model left it empty
                if name == "call_external_api" and external_api_data and not args.get("operation_id"):
                    if any(kw in user_lower for kw in ("airport", "airports")):
                        args["operation_id"] = "Settings_GetAirports"
                    elif any(kw in user_lower for kw in ("passenger", "passengers")):
                        args["operation_id"] = "Airports_GetPassengers"
                    elif any(kw in user_lower for kw in ("hotel", "hotels")):
                        args["operation_id"] = "Settings_GetHotels"

                # Progress: what we're doing
                if name == 'call_external_api':
                    op_id = args.get("operation_id", "?")
                    _log(f"  ... calling API: {op_id} ...")
                else:
                    _log(f"  ... using tool: {name} ...")

                if name == 'check_inventory':
                    result = check_inventory(args.get('product_name', ''))
                elif name == 'get_low_stock_report':
                    result = get_low_stock_report()
                elif name == 'get_recent_transactions':
                    result = get_recent_transactions(args.get('product_name', ''))
                elif name == 'calculate_inventory_value':
                    result = calculate_inventory_value()
                elif name == 'find_products_by_brand':
                    result = find_products_by_brand(args.get('brand_name', ''))
                elif name == 'call_external_api' and external_api_data:
                    from external_api import execute_external_api
                    result = execute_external_api(
                        external_api_data["base_url"],
                        external_api_data["bearer_token"],
                        external_api_data["operations_by_id"],
                        args.get("operation_id", ""),
                        args.get("path_params"),
                        args.get("query_params"),
                        args.get("request_body"),
                    )
                else:
                    result = f"Unknown tool: {name}"

                messages.append(response.message)
                messages.append({'role': 'tool', 'content': result})

            _log("  ... getting answer ...")
            final = ollama.chat(model='functiongemma', messages=messages)
            _log(f"Assistant: {final.message.content}")
        else:
            _log(f"Assistant: {response.message.content}")

if __name__ == "__main__":
    run()
