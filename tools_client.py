import database

# --- HELPER: Fuzzy Matcher ---
def find_closest_item_name(user_input_name: str) -> str:
    """
    Tries to match user input (e.g., "water bottles") to DB keys (e.g., "water_bottles").
    Returns the DB key if found, or None.
    """
    all_items = database.get_all_items()
    valid_names = [r['item_name'] for r in all_items]
    
    # 1. Exact Match
    if user_input_name in valid_names:
        return user_input_name
    
    # 2. Case Insensitive & Underscore/Space swap
    normalized_input = user_input_name.lower().replace(" ", "_")
    for name in valid_names:
        if name.lower() == normalized_input:
            return name
            
    # 3. Partial match (e.g. "water" matches "water_bottles")
    for name in valid_names:
        if normalized_input in name.lower():
            return name
            
    return None

def check_inventory(item_name: str) -> str:
    """Checks the current stock of a specific item."""
    # 🔥 Use Fuzzy Matcher
    db_item_name = find_closest_item_name(item_name)
    
    if not db_item_name:
        # Helper to show what IS available
        all_items = database.get_all_items()
        names = ", ".join([r['item_name'].replace("_", " ") for r in all_items])
        return f"Error: '{item_name}' not found. We stock: {names}."

    stock = database.get_item_stock(db_item_name)
    return f"{db_item_name}: {stock} units available."

def request_relief(item_name: str, quantity: int, location: str, is_critical: bool = False) -> str:
    """Processes a relief request."""
    
    # 🔥 Use Fuzzy Matcher
    db_item_name = find_closest_item_name(item_name)
    
    if not db_item_name:
        all_items = database.get_all_items()
        names = ", ".join([r['item_name'] for r in all_items])
        return f"Error: Item '{item_name}' does not exist. Available: {names}"

    current_stock = database.get_item_stock(db_item_name)
    urgency = "CRITICAL" if is_critical else "NORMAL"
    
    if current_stock < quantity: 
        return f"Error: Insufficient stock for {db_item_name}. Only {current_stock} available."

    needs_approval = quantity > 10
    
    if needs_approval:
        # Note: We save the DB_ITEM_NAME (with underscore) to the database
        req_id = database.create_request(db_item_name, quantity, location, "PENDING", urgency, "Awaiting Approval")
        return f"Request ID {req_id} created. Status: PENDING ({urgency} priority)."
    else:
        new_stock = current_stock - quantity
        database.update_stock(db_item_name, new_stock)
        database.create_request(db_item_name, quantity, location, "APPROVED", urgency, "Auto-approved")
        return f"APPROVED. Dispatched {quantity} {db_item_name}. New Stock: {new_stock}."

def check_request_status(request_id: int) -> str:
    """Allows a user to check the status of a previous request ID."""
    req = database.get_request_by_id(request_id)
    if not req:
        return f"Error: Request ID {request_id} not found."
    
    return f"Request {request_id} Status: {req['status']} (Item: {req['item_name']}, Location: {req['location']})"