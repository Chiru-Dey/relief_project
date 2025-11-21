import database
import json

# --- REQUEST MANAGEMENT ---

def supervisor_view_pending_requests() -> str:
    """Returns a list of all requests with status 'PENDING' or 'FLAGGED', sorted by urgency."""
    rows = database.get_pending_requests()
    if not rows: 
        return "No requests or system flags require attention."
    
    result = "Attention Queue (Pending Approvals & System Flags):\n"
    for r in rows:
        if r['status'] == 'FLAGGED':
            result += f"- 🚩 FLAG (ID {r['id']}): {r['notes']}\n"
        else:
            urgency_mark = "🔴 CRITICAL" if r['urgency'] == 'CRITICAL' else "⚪ Normal"
            result += f"- ID {r['id']} [{urgency_mark}]: {r['quantity']}x {r['item_name']} for {r['location']}\n"
    return result

def supervisor_decide_request(request_id: int, decision: str) -> str:
    """Supervisor tool to APPROVE or REJECT a single PENDING request ID."""
    decision = decision.upper()
    req = database.get_request_by_id(request_id)
    if not req: return f"Error: Request ID {request_id} not found."
    if req['status'] != 'PENDING': return f"Error: Request {request_id} is not PENDING. Current status: {req['status']}."

    if decision == "REJECT":
        database.update_request_status(request_id, "REJECTED")
        return f"Request {request_id} has been REJECTED."
    
    if decision == "APPROVE":
        current_stock = database.get_item_stock(req['item_name'])
        if current_stock < req['quantity']:
            return f"Cannot Approve Req {request_id}: Insufficient stock."
        
        new_stock = current_stock - req['quantity']
        database.update_stock(req['item_name'], new_stock)
        database.update_request_status(request_id, "APPROVED_MANUAL") # Note new status
        return f"Request {request_id} manually APPROVED. New stock: {new_stock}."

def supervisor_batch_decide_requests(request_ids_json: str, decision: str) -> str:
    """Batch approve or reject multiple PENDING requests at once."""
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
    if database.get_item_stock(item_name) != -1:
        return f"Error: Item '{item_name}' already exists."
    database.add_new_item(item_name, initial_quantity)
    return f"SUCCESS: Added '{item_name}'."

def admin_delete_item(item_name: str) -> str:
    if database.get_item_stock(item_name) == -1:
        return f"Error: Item '{item_name}' does not exist."
    database.delete_item(item_name)
    return f"SUCCESS: Deleted '{item_name}'."

def admin_restock_item(item_name: str, quantity_to_add: int) -> str:
    current = database.get_item_stock(item_name)
    if current == -1:
        return f"Error: Cannot restock '{item_name}' because it does not exist."
    
    new_total = database.increment_stock(item_name, quantity_to_add)
    return f"SUCCESS: Added {quantity_to_add} to {item_name}. New Total: {new_total}."

def admin_batch_update_inventory(updates_json: str) -> str:
    try:
        updates = json.loads(updates_json)
        if not isinstance(updates, dict): raise ValueError
    except:
        return "Error: updates_json must be a JSON dict '{\"item\": qty}'."

    log = []
    for item, qty in updates.items():
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

def supervisor_view_audit_log(limit: int = 10) -> str:
    """Views the most recent completed requests (AI and human approved)."""
    rows = database.get_recent_completed_requests(limit)
    if not rows:
        return "No completed requests in the log."
    
    result = f"Audit Log (Last {limit} completed requests):\n"
    for r in rows:
        status_tag = f"[{r['status']}]"
        result += f"- ID {r['id']} {status_tag}: {r['quantity']}x {r['item_name']} for {r['location']}\n"
    return result

# --- 🔥 FIX: ADDED MISSING FUNCTION ---
def log_user_complaint(complaint_text: str) -> str:
    """
    Logs a non-urgent issue, user complaint, or inventory gap for a supervisor to review later.
    Use this when a user reports a problem that the agent cannot solve itself.
    """
    if not complaint_text:
        return "ERROR: Complaint text cannot be empty."
    
    database.create_system_log(complaint_text)
    return "SUCCESS: The issue has been logged and flagged for supervisor attention."