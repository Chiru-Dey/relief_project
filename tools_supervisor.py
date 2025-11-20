import database
import json

# --- REQUEST MANAGEMENT ---

def supervisor_view_pending_requests() -> str:
    """Returns a list of all requests with status 'PENDING', sorted by urgency."""
    rows = database.get_pending_requests()
    if not rows: return "No pending requests found."
    
    result = "Pending Requests (Sorted by Urgency):\n"
    for r in rows:
        urgency_mark = "🔴 CRITICAL" if r['urgency'] == 'CRITICAL' else "⚪ Normal"
        result += f"- ID {r['id']} [{urgency_mark}]: {r['quantity']}x {r['item_name']} for {r['location']}\n"
    return result

def supervisor_decide_request(request_id: int, decision: str) -> str:
    """Supervisor tool to APPROVE or REJECT a single request ID."""
    decision = decision.upper()
    req = database.get_request_by_id(request_id)
    if not req: return f"Error: Request ID {request_id} not found."
    if req['status'] != 'PENDING': return f"Error: Request {request_id} is {req['status']}."

    if decision == "REJECT":
        database.update_request_status(request_id, "REJECTED")
        return f"Request {request_id} REJECTED."
    
    if decision == "APPROVE":
        current_stock = database.get_item_stock(req['item_name'])
        if current_stock < req['quantity']:
            return f"Cannot Approve Req {request_id}: Insufficient stock."
        
        new_stock = current_stock - req['quantity']
        database.update_stock(req['item_name'], new_stock)
        database.update_request_status(request_id, "APPROVED")
        return f"Request {request_id} APPROVED."

def supervisor_batch_decide_requests(request_ids_json: str, decision: str) -> str:
    """
    Batch approve or reject multiple requests at once.
    Args:
        request_ids_json: A JSON string list of integers, e.g., "[1, 2, 5]"
        decision: "APPROVE" or "REJECT"
    """
    try:
        req_ids = json.loads(request_ids_json)
        if not isinstance(req_ids, list): raise ValueError
    except:
        return "Error: request_ids_json must be a JSON list of integers (e.g., '[1, 2]')."

    results = []
    for rid in req_ids:
        res = supervisor_decide_request(rid, decision)
        results.append(res)
    
    return "\n".join(results)

# --- INVENTORY MANAGEMENT (CRUD) ---

def admin_add_new_item(item_name: str, initial_quantity: int) -> str:
    """Creates a new type of item in the inventory system."""
    if database.get_item_stock(item_name) != -1:
        return f"Error: Item '{item_name}' already exists."
    database.add_new_item(item_name, initial_quantity)
    return f"SUCCESS: Added '{item_name}'."

def admin_delete_item(item_name: str) -> str:
    """Permanently deletes an item type."""
    if database.get_item_stock(item_name) == -1:
        return f"Error: Item '{item_name}' does not exist."
    database.delete_item(item_name)
    return f"SUCCESS: Deleted '{item_name}'."

def admin_restock_item(item_name: str, quantity: int) -> str:
    """Sets the absolute stock level of an item."""
    if database.get_item_stock(item_name) == -1:
        return f"Error: '{item_name}' not found."
    database.update_stock(item_name, quantity)
    return f"SUCCESS: {item_name} set to {quantity}."

def admin_batch_update_inventory(updates_json: str) -> str:
    """
    Batch update multiple inventory items at once.
    Args:
        updates_json: JSON dictionary string {"item_name": quantity, ...}
                      Example: '{"water_bottles": 500, "tents": 50}'
    """
    try:
        updates = json.loads(updates_json)
        if not isinstance(updates, dict): raise ValueError
    except:
        return "Error: updates_json must be a JSON dict '{\"item\": qty}'."

    log = []
    for item, qty in updates.items():
        # Check if item exists; if not, add it automatically (Upsert logic)
        if database.get_item_stock(item) == -1:
            database.add_new_item(item, qty)
            log.append(f"Created & Set {item} to {qty}")
        else:
            database.update_stock(item, qty)
            log.append(f"Updated {item} to {qty}")
            
    return "\n".join(log)

# --- REPORTING ---

def admin_view_full_inventory() -> str:
    rows = database.get_all_items()
    result = "Current Inventory Levels:\n"
    for r in rows:
        result += f"- {r['item_name']}: {r['quantity']}\n"
    return result

def admin_get_low_stock_report(threshold: int = 20) -> str:
    rows = database.get_all_items()
    low_stock = [r for r in rows if r['quantity'] < threshold]
    if not low_stock: return "All items are well stocked."
    
    result = f"⚠️ LOW STOCK ALERT (< {threshold} units):\n"
    for r in low_stock:
        result += f"- {r['item_name']}: Only {r['quantity']} left\n"
    return result