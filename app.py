# Load .env first so all env vars are set for the rest of the app
import env_loader
env_loader.load_project_env(__file__)

import ollama
from ollama import ResponseError
import json
import os
import sys
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

EXTERNAL_API_KEYWORDS = ("airport", "passenger", "hotel", "flytel", "flight", "dashboard", "settings")

# Map query keyword -> (substrings for fallback match, preferred resource from DB)
_EXTERNAL_API_KEYWORD_TO_MATCH = {
    "airport": (("airport", "airports"), "airports"),
    "passenger": (("passenger", "passengers"), "passengers"),
    "hotel": (("hotel", "hotels"), "hotels"),
    "flytel": (("flytel",), None),
    "flight": (("flight", "flights"), None),
    "dashboard": (("dashboard",), None),
    "settings": (("settings",), None),
}
_LIST_INTENT_PHRASES = ("list", "get me the list", "show all", "all the", "list of")


def _external_api_is_request(user_input, external_api_data):
    """True if user message looks like an external API request (keywords + API loaded)."""
    if not external_api_data or not user_input:
        return False
    user_lower = user_input.lower()
    return any(kw in user_lower for kw in EXTERNAL_API_KEYWORDS)


def _filter_external_tools_by_query(tools, user_input, operations_by_id):
    """
    Return only tools that match the user intent. Uses DB columns resource + action when
    present so "list of airports" -> resource=airports, action=list (e.g. Settings_GetAirports).
    Falls back to keyword match on operation_id/summary when resource/action are missing.
    """
    if not user_input or not operations_by_id:
        return tools
    user_lower = user_input.lower()
    want_list = any(p in user_lower for p in _LIST_INTENT_PHRASES)
    wanted_resources = set()
    match_substrings = []
    for kw, val in _EXTERNAL_API_KEYWORD_TO_MATCH.items():
        if kw in user_lower:
            subs, resource = val
            match_substrings.extend(subs)
            if resource:
                wanted_resources.add(resource)
    if not match_substrings and not wanted_resources:
        return tools
    filtered = []
    for t in tools:
        name = t.get("function", {}).get("name") or ""
        op = operations_by_id.get(name) or {}
        resource = (op.get("resource") or "").strip().lower() if op.get("resource") else None
        action = (op.get("action") or "").strip().lower() if op.get("action") else None
        has_path_params = op.get("has_path_params", "{" in (op.get("path_template") or ""))

        if wanted_resources:
            if resource and resource in wanted_resources:
                pass
            elif not resource:
                summary = (op.get("summary") or "").lower()
                if not any(sub in f"{name} {summary}" for sub in match_substrings):
                    continue
            else:
                continue
        else:
            summary = (op.get("summary") or "").lower()
            if not any(sub in f"{name} {summary}" for sub in match_substrings):
                continue

        if want_list:
            # list = no path params; list_scoped = GET .../resource (e.g. passengers at airport)
            if action in ("list", "list_scoped") or (not has_path_params):
                filtered.append(t)
        else:
            filtered.append(t)
    return filtered if filtered else tools


def _external_api_execute(external_api_data, operation_id, path_params=None, query_params=None, request_body=None):
    """Call the external API with the given operation and params; return raw response body string."""
    from external_api import execute_external_api
    return execute_external_api(
        external_api_data["base_url"],
        external_api_data["bearer_token"],
        external_api_data["operations_by_id"],
        operation_id or "",
        path_params,
        query_params,
        request_body,
    )


def _external_api_handle_call(name, args, external_api_data):
    """
    If tool name is an external operation_id, execute that API call and return result.
    Returns result string for external ops, None so caller runs inventory tools.
    """
    if not external_api_data:
        return None
    operations_by_id = external_api_data.get("operations_by_id") or {}
    op = operations_by_id.get(name)
    if not op:
        return None
    from external_api import args_to_request_parts
    path_params, query_params, request_body = args_to_request_parts(op, args)
    return _external_api_execute(
        external_api_data,
        name,
        path_params,
        query_params,
        request_body,
    )


def _load_external_api_tool():
    """
    If config is set, load API source and operations from Postgres and return
    (tools_list_append, handler_data) or ([], None).
    handler_data: dict with base_url, bearer_token, operations_by_id for dynamic API tools.
    """
    try:
        from external_api import (
            load_api_source_and_operations,
            build_dynamic_tools_from_operations,
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

    dynamic_tools = build_dynamic_tools_from_operations(operations_list)
    operations_by_id = {op["operation_id"]: op for op in operations_list}
    handler_data = {
        "base_url": base_url,
        "bearer_token": bearer_token,
        "operations_by_id": operations_by_id,
    }
    return dynamic_tools, handler_data


# --- MAIN RUN LOOP ---

def run():
    inventory_tools = [
        {'type': 'function', 'function': {'name': 'check_inventory', 'description': 'Get price and stock for a specific item', 'parameters': {'type': 'object', 'properties': {'product_name': {'type': 'string'}}, 'required': ['product_name']}}},
        {'type': 'function', 'function': {'name': 'get_low_stock_report', 'description': 'List all items that are low on stock'}},
        {'type': 'function', 'function': {'name': 'get_recent_transactions', 'description': 'See history of IN/OUT movements for a product', 'parameters': {'type': 'object', 'properties': {'product_name': {'type': 'string'}}, 'required': ['product_name']}}},
        {'type': 'function', 'function': {'name': 'calculate_inventory_value', 'description': 'Calculate the total dollar value of the whole inventory'}},
        {'type': 'function', 'function': {'name': 'find_products_by_brand', 'description': 'Search for all products by a brand name', 'parameters': {'type': 'object', 'properties': {'brand_name': {'type': 'string'}}, 'required': ['brand_name']}}}
    ]

    ollama_model = os.environ.get("OLLAMA_MODEL", "functiongemma")

    dynamic_external_tools, external_api_data = _load_external_api_tool()
    # Combined list: static inventory tools + dynamic tools (one per DB operation)
    tools = inventory_tools + (dynamic_external_tools if external_api_data else [])
    if external_api_data:
        _log("--- External API tool loaded (from Postgres). ---")
    else:
        _log("--- (External API not loaded: set DATABASE_URL, API_SOURCE_NAME, EXTERNAL_API_BEARER_TOKEN in .env to enable.) ---")

    _log("--- 🛠️  Advanced Inventory Assistant Ready ---")
    _log("(Type 'exit' to quit)")

    if external_api_data:
        system_instruction = (
            "CRITICAL: Use the API tool whose name matches the request: list of airports -> Settings_GetAirports; "
            "list of hotels -> Settings_GetHotels; passengers -> Airports_GetPassengers or similar. "
            "Do NOT use Settings_GetProducts or inventory tools for airports/hotels/passengers. "
            "You can chain API calls: first call Settings_GetAirports to get airport IDs, then use the airport id (UUID) in later calls. "
            "When a user refers to an airport by name (e.g. 'Oslo Gardermoen'), look up its id in the previous tool result and pass that id (e.g. airportId), never the name. "
            "If a tool returns 'Missing required path parameters', call the suggested list endpoint first and use the returned IDs in the next call. "
            "For products, stock, inventory, brand -> use inventory tools. If a tool errors, explain to the user."
        )
    else:
        system_instruction = (
            "You are an inventory manager. You have access to local data files via tools. "
            "When a user asks about prices, stock, or history, you MUST call the appropriate tool. "
            "If a tool returns an error, explain it to the user."
        )

    def _handle_tool_response(response, messages, tools, use_tools, external_api_data, user_input=""):
        while True:
            if not response.message.tool_calls:
                _log(f"Assistant: {response.message.content}")
                break
            messages.append(response.message)
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

                if external_api_data and name in (external_api_data.get("operations_by_id") or {}):
                    op = external_api_data["operations_by_id"][name]
                    from external_api import args_to_request_parts, _fill_path_template
                    from urllib.parse import urlencode
                    path_params, query_params, _ = args_to_request_parts(op, args)
                    base = (external_api_data.get("base_url") or "").rstrip("/")
                    path_tpl = (op.get("path_template") or "").strip()
                    path = _fill_path_template(path_tpl, path_params)
                    full_route = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
                    if query_params and isinstance(query_params, dict):
                        q = {k: v for k, v in query_params.items() if v is not None and v != ""}
                        if q:
                            full_route += "?" + urlencode(q)
                    _log(f"  ... calling API: {name} — {op.get('method', 'GET')} {full_route} ...")
                else:
                    _log(f"  ... using tool: {name} ...")

                result = _external_api_handle_call(name, args, external_api_data)
                if result is None:
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
                    else:
                        result = f"Unknown tool: {name}"

                messages.append({'role': 'tool', 'content': result})

            _log("  ... getting answer ...")
            response = ollama.chat(model=ollama_model, messages=messages)

    # Keep conversation history so the model can use previous tool results (e.g. airport ID from list of airports)
    conversation_messages = []
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']: break

        _log("  ... thinking ...")
        conversation_messages.append({'role': 'user', 'content': user_input})
        messages = [{'role': 'system', 'content': system_instruction}] + conversation_messages

        is_external_api_request = _external_api_is_request(user_input, external_api_data)
        op_ids = (external_api_data or {}).get("operations_by_id") or {}
        if is_external_api_request and external_api_data:
            external_only = [t for t in tools if t.get("function", {}).get("name") in op_ids]
            use_tools = _filter_external_tools_by_query(external_only, user_input, op_ids)
        else:
            use_tools = tools
        try:
            response = ollama.chat(model=ollama_model, messages=messages, tools=use_tools)
        except ResponseError as e:
            err_text = (getattr(e, "error", None) or str(e)) or ""
            if "does not support tools" in err_text.lower() or (e.status_code == 400 and "tools" in err_text.lower()):
                _log(f"Error: The model '{ollama_model}' does not support tool calling.")
                print("This app needs a model that supports tools (e.g. functiongemma).")
                print("Set OLLAMA_MODEL=functiongemma in your .env file, then run again.")
                sys.exit(1)
            raise
        _handle_tool_response(response, messages, tools, use_tools, external_api_data, user_input)
        # Persist this turn (user + assistant/tool messages) so next turn has full context
        conversation_messages = messages[1:]

if __name__ == "__main__":
    run()
