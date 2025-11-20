import sqlite3

DB_FILE = "relief_logistics.db"

def init_db():
    """Initializes the database with updated schema."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Inventory Table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    item_name TEXT PRIMARY KEY,
                    quantity INTEGER
                )''')
    
    # 2. Requests Table (Added 'urgency' column)
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    quantity INTEGER,
                    location TEXT,
                    status TEXT,
                    urgency TEXT,
                    notes TEXT
                )''')
    
    # 3. Seed Data
    c.execute("SELECT count(*) FROM inventory")
    if c.fetchone()[0] == 0:
        print("🌱 Seeding database with initial inventory...")
        seed_data = [
            ("water_bottles", 100),
            ("food_packs", 50),
            ("medical_kits", 10),
            ("blankets", 30),
            ("batteries", 200)
        ]
        c.executemany("INSERT INTO inventory (item_name, quantity) VALUES (?, ?)", seed_data)
        conn.commit()
    
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- INVENTORY CRUD ---

def get_item_stock(item_name: str) -> int:
    conn = get_db_connection()
    row = conn.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,)).fetchone()
    conn.close()
    return row['quantity'] if row else -1

def get_all_items() -> list[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_new_item(item_name: str, quantity: int):
    """Adds a new item type to the database."""
    conn = get_db_connection()
    conn.execute("INSERT INTO inventory (item_name, quantity) VALUES (?, ?)", (item_name, quantity))
    conn.commit()
    conn.close()

def delete_item(item_name: str):
    """Permanently removes an item type from inventory."""
    conn = get_db_connection()
    conn.execute("DELETE FROM inventory WHERE item_name = ?", (item_name,))
    conn.commit()
    conn.close()

def update_stock(item_name: str, new_quantity: int):
    conn = get_db_connection()
    conn.execute("UPDATE inventory SET quantity = ? WHERE item_name = ?", (new_quantity, item_name))
    conn.commit()
    conn.close()

# --- REQUEST OPERATIONS ---

def create_request(item_name: str, quantity: int, location: str, status: str, urgency: str, notes: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO requests (item_name, quantity, location, status, urgency, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (item_name, quantity, location, status, urgency, notes)
    )
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id

def get_pending_requests() -> list[dict]:
    conn = get_db_connection()
    # prioritize CRITICAL requests first
    rows = conn.execute("SELECT * FROM requests WHERE status = 'PENDING' ORDER BY urgency DESC, id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_request_by_id(request_id: int) -> dict:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_request_status(request_id: int, status: str):
    conn = get_db_connection()
    conn.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()
    conn.close()
    
def increment_stock(item_name: str, amount_to_add: int) -> int:
    """
    Adds the specified amount to the existing stock.
    Returns the new total quantity.
    """
    conn = get_db_connection()
    # SQLite allows calculation in the UPDATE statement
    conn.execute(
        "UPDATE inventory SET quantity = quantity + ? WHERE item_name = ?", 
        (amount_to_add, item_name)
    )
    conn.commit()
    
    # Fetch and return the new total
    row = conn.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,)).fetchone()
    conn.close()
    return row['quantity'] if row else 0