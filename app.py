import ollama
import json

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

# --- MAIN RUN LOOP ---

def run():
    tools = [
        {'type': 'function', 'function': {'name': 'check_inventory', 'description': 'Get price and stock for a specific item', 'parameters': {'type': 'object', 'properties': {'product_name': {'type': 'string'}}, 'required': ['product_name']}}},
        {'type': 'function', 'function': {'name': 'get_low_stock_report', 'description': 'List all items that are low on stock'}},
        {'type': 'function', 'function': {'name': 'get_recent_transactions', 'description': 'See history of IN/OUT movements for a product', 'parameters': {'type': 'object', 'properties': {'product_name': {'type': 'string'}}, 'required': ['product_name']}}},
        {'type': 'function', 'function': {'name': 'calculate_inventory_value', 'description': 'Calculate the total dollar value of the whole inventory'}},
        {'type': 'function', 'function': {'name': 'find_products_by_brand', 'description': 'Search for all products by a brand name', 'parameters': {'type': 'object', 'properties': {'brand_name': {'type': 'string'}}, 'required': ['brand_name']}}}
    ]

    print("--- 🛠️  Advanced Inventory Assistant Ready ---")
    print("(Type 'exit' to quit)")

    # System prompt helps the AI understand it MUST use tools for data
    system_instruction = (
        "You are an inventory manager. You have access to local data files via tools. "
        "When a user asks about prices, stock, or history, you MUST call the appropriate tool. "
        "If a tool returns an error, explain it to the user."
    )

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']: break

        messages = [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_input}
        ]

        response = ollama.chat(model='functiongemma', messages=messages, tools=tools)
        #print(f"response: {response.message}")
        if response.message.tool_calls:
            for tool in response.message.tool_calls:
                name = tool.function.name
                args = tool.function.arguments
                
                if name == 'check_inventory': result = check_inventory(args['product_name'])
                elif name == 'get_low_stock_report': result = get_low_stock_report()
                elif name == 'get_recent_transactions': result = get_recent_transactions(args['product_name'])
                elif name == 'calculate_inventory_value': result = calculate_inventory_value()
                elif name == 'find_products_by_brand': result = find_products_by_brand(args['brand_name'])
                
                messages.append(response.message)
                messages.append({'role': 'tool', 'content': result})
                
                final = ollama.chat(model='functiongemma', messages=messages)
                print(f"Assistant: {final.message.content}")
        else:
            print(f"Assistant: {response.message.content}")

if __name__ == "__main__":
    run()
