import database
import json

def supervisor_view_pending_requests() -> str:
    rows = database.get_pending_requests()
    if not rows: return "No items require attention."
    result = "Attention Queue:\n"
    for r in rows:
        if r['status'] == 'ACTION_REQUIRED':
            result += f"- ❗ ACTION (ID {r['id']}): {r['notes']} at {r['location']}\n"
        else:
            urgency = "🔴" if r['urgency'] == 'CRITICAL' else "⚪"
            result += f"- ⏳ PENDING (ID {r['id']}) [{urgency}]: {r['quantity']}x {r['item_name']}\n"
    return result

def supervisor_mark_action_taken(task_id: int, notes: str) -> str:
    task = database.get_request_by_id(task_id)
    if not task: return f"ERROR: Task {task_id} not found."
    database.update_request_status(task_id, "ACTION_TAKEN", f"Human action: {notes}")
    return f"SUCCESS: Task {task_id} marked completed."

def supervisor_decide_request(request_id: int, decision: str) -> str:
    decision = decision.upper()
    req = database.get_request_by_id(request_id)
    if not req: return f"Error: Request {request_id} not found."
    if decision == "REJECT":
        database.update_request_status(request_id, "REJECTED", "Rejected by supervisor.")
        return f"Request {request_id} REJECTED."
    if decision == "APPROVE":
        current = database.get_item_stock(req['item_name'])
        if current < req['quantity']: return "Cannot Approve: Insufficient stock."
        new_stock = current - req['quantity']
        database.update_stock(req['item_name'], new_stock)
        database.update_request_status(request_id, "APPROVED_MANUAL", "Approved by supervisor.")
        return f"Request {request_id} APPROVED."

def supervisor_batch_decide_requests(request_ids_json: str, decision: str) -> str:
    try: ids = json.loads(request_ids_json)
    except: return "Error: Invalid JSON list."
    return "\n".join([supervisor_decide_request(i, decision) for i in ids])

def admin_add_new_item(item_name: str, initial_quantity: int) -> str:
    if database.get_item_stock(item_name) != -1: return "Error: Item exists."
    database.add_new_item(item_name, initial_quantity)
    return f"SUCCESS: Added {item_name}."

def admin_delete_item(item_name: str) -> str:
    database.delete_item(item_name)
    return f"SUCCESS: Deleted {item_name}."

def admin_restock_item(item_name: str, quantity_to_add: int) -> str:
    if database.get_item_stock(item_name) == -1: return "Error: Item not found."
    total = database.increment_stock(item_name, quantity_to_add)
    return f"SUCCESS: Added {quantity_to_add} to {item_name}. Total: {total}."

def admin_batch_update_inventory(updates_json: str) -> str:
    try: updates = json.loads(updates_json)
    except: return "Error: Invalid JSON dict."
    log = []
    for item, qty in updates.items():
        if database.get_item_stock(item) == -1:
            database.add_new_item(item, qty)
            log.append(f"Created {item} = {qty}")
        else:
            database.update_stock(item, qty)
            log.append(f"Updated {item} = {qty}")
    return "\n".join(log)

def admin_view_full_inventory() -> str:
    rows = database.get_all_items()
    return "Inventory:\n" + "\n".join([f"- {r['item_name']}: {r['quantity']}" for r in rows])

def admin_get_low_stock_report(threshold: int = 20) -> str:
    rows = [r for r in database.get_all_items() if r['quantity'] < threshold]
    return "Low Stock:\n" + "\n".join([f"- {r['item_name']}: {r['quantity']}" for r in rows]) if rows else "All OK."

def supervisor_view_audit_log(limit: int = 10) -> str:
    rows = database.get_recent_completed_requests(limit)
    return "Audit Log:\n" + "\n".join([f"- ID {r['id']} [{r['status']}]: {r['item_name']}" for r in rows]) if rows else "No logs."

def log_user_complaint(complaint_text: str) -> str:
    if not complaint_text: return "Error: Empty complaint."
    database.create_system_log(complaint_text)
    return "SUCCESS: Complaint logged."