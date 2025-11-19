import database

# --- REQUEST MANAGEMENT ---

def supervisor_view_pending_requests() -> str:
    """Returns a list of all requests with status 'PENDING', sorted by urgency."""
    rows = database.get_pending_requests()
    if not rows: 
        return "No pending requests found."
    
    result = "Pending Requests (Sorted by Urgency):\n"
    for r in rows:
        urgency_mark = "🔴 CRITICAL" if r['urgency'] == 'CRITICAL' else "⚪ Normal"
        result += f"- ID {r['id']} [{urgency_mark}]: {r['quantity']}x {r['item_name']} for {r['location']}\n"
    return result

def supervisor_decide_request(request_id: int, decision: str) -> str:
    """
    Supervisor tool to APPROVE or REJECT a request ID.
    """
    decision = decision.upper()
    req = database.get_request_by_id(request_id)
    
    if not req: return f"Error: Request ID {request_id} not found."
    if req['status'] != 'PENDING': return f"Error: Request {request_id} is {req['status']}."

    if decision == "REJECT":
        database.update_request_status(request_id, "REJECTED")
        return f"Request {request_id} has been REJECTED."
    
    if decision == "APPROVE":
        current_stock = database.get_item_stock(req['item_name'])
        if current_stock < req['quantity']:
            return f"Cannot Approve: Insufficient stock. Current: {current_stock}."
        
        new_stock = current_stock - req['quantity']
        database.update_stock(req['item_name'], new_stock)
        database.update_request_status(request_id, "APPROVED")
        return f"Request {request_id} APPROVED. New stock: {new_stock}."

# --- INVENTORY MANAGEMENT (CRUD) ---

def admin_add_new_item(item_name: str, initial_quantity: int) -> str:
    """Creates a new type of item in the inventory system."""
    current = database.get_item_stock(item_name)
    if current != -1:
        return f"Error: Item '{item_name}' already exists (Stock: {current}). Use restock tool instead."
    
    database.add_new_item(item_name, initial_quantity)
    return f"SUCCESS: Added new item '{item_name}' with quantity {initial_quantity}."

def admin_delete_item(item_name: str) -> str:
    """Permanently deletes an item type from the inventory database."""
    current = database.get_item_stock(item_name)
    if current == -1:
        return f"Error: Item '{item_name}' does not exist."
    
    database.delete_item(item_name)
    return f"SUCCESS: Item '{item_name}' deleted from database."

def admin_restock_item(item_name: str, quantity: int) -> str:
    """Sets the absolute stock level of an item."""
    current = database.get_item_stock(item_name)
    if current == -1:
        return f"Error: Cannot restock '{item_name}' because it does not exist."
    
    database.update_stock(item_name, quantity)
    return f"SUCCESS: {item_name} stock updated to {quantity}."

# --- REPORTING ---

def admin_view_full_inventory() -> str:
    """Returns list of all items."""
    rows = database.get_all_items()
    result = "Current Inventory Levels:\n"
    for r in rows:
        result += f"- {r['item_name']}: {r['quantity']}\n"
    return result

def admin_get_low_stock_report(threshold: int = 20) -> str:
    """Returns a list of items where stock is below the threshold."""
    rows = database.get_all_items()
    low_stock = [r for r in rows if r['quantity'] < threshold]
    
    if not low_stock:
        return "All items are well stocked."
    
    result = f"⚠️ LOW STOCK ALERT (< {threshold} units):\n"
    for r in low_stock:
        result += f"- {r['item_name']}: Only {r['quantity']} left\n"
    return result