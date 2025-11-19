import sqlite3

DB_FILE = "relief_logistics.db"

def init_db():
    """Initializes the database with tables and seed data."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Inventory Table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    item_name TEXT PRIMARY KEY,
                    quantity INTEGER
                )''')
    
    # 2. Requests Table
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    quantity INTEGER,
                    location TEXT,
                    status TEXT,
                    notes TEXT
                )''')
    
    # 3. Seed Data (only if empty)
    c.execute("SELECT count(*) FROM inventory")
    if c.fetchone()[0] == 0:
        print("🌱 Seeding database with initial inventory...")
        seed_data = [
            ("water_bottles", 100),
            ("food_packs", 50),
            ("medical_kits", 10),
            ("blankets", 30)
        ]
        c.executemany("INSERT INTO inventory (item_name, quantity) VALUES (?, ?)", seed_data)
        conn.commit()
    
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- INVENTORY OPERATIONS ---

def get_item_stock(item_name: str) -> int:
    """Returns quantity of item, or -1 if item doesn't exist."""
    conn = get_db_connection()
    row = conn.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,)).fetchone()
    conn.close()
    return row['quantity'] if row else -1

def get_all_item_names() -> list[str]:
    """Returns list of all item names in inventory."""
    conn = get_db_connection()
    rows = conn.execute("SELECT item_name FROM inventory").fetchall()
    conn.close()
    return [r['item_name'] for r in rows]

def update_stock(item_name: str, new_quantity: int):
    """Updates the stock level of an item."""
    conn = get_db_connection()
    conn.execute("UPDATE inventory SET quantity = ? WHERE item_name = ?", (new_quantity, item_name))
    conn.commit()
    conn.close()

# --- REQUEST OPERATIONS ---

def create_request(item_name: str, quantity: int, location: str, status: str, notes: str) -> int:
    """Creates a new request and returns the Request ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO requests (item_name, quantity, location, status, notes) VALUES (?, ?, ?, ?, ?)",
        (item_name, quantity, location, status, notes)
    )
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id

def get_pending_requests() -> list[dict]:
    """Returns a list of dictionaries representing pending requests."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM requests WHERE status = 'PENDING'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_request_by_id(request_id: int) -> dict:
    """Returns a single request dict or None."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_request_status(request_id: int, status: str):
    """Updates the status of a request."""
    conn = get_db_connection()
    conn.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()
    conn.close()