"""ElectroPOS - data layer (pure stdlib, no Kivy dependency)."""
import csv
import datetime
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    cost REAL DEFAULT 0,
    price REAL DEFAULT 0,
    stock INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    barcode TEXT,
    name TEXT,
    price REAL,
    qty INTEGER
);
"""

_conn = None
_path = None


def set_db_path(path):
    global _path, _conn
    _path = path
    _conn = None


def _default_path():
    base = os.environ.get('ELECTROPOS_HOME') or os.path.join(os.path.expanduser('~'), '.electropos')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, 'electropos.db')


def get_db():
    global _conn
    if _conn is None:
        path = _path or _default_path()
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        _conn = sqlite3.connect(path)
        _conn.row_factory = sqlite3.Row
        _conn.execute('PRAGMA foreign_keys = ON')
        _conn.executescript(SCHEMA)
        _seed(_conn)
        _conn.commit()
    return _conn


def _seed(conn):
    count = conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    if count == 0:
        conn.execute(
            'INSERT OR IGNORE INTO products (barcode, name, category, cost, price, stock) VALUES (?,?,?,?,?,?)',
            ('1234567890123', 'HDMI Cable 1.5m (sample)', 'Cables', 2.50, 5.99, 20),
        )


# ---------------- products ----------------
def search_products(term=''):
    like = '%' + term + '%'
    return get_db().execute(
        'SELECT * FROM products WHERE name LIKE ? OR barcode LIKE ? OR category LIKE ? ORDER BY name',
        (like, like, like)).fetchall()


def get_product(pid):
    return get_db().execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()


def get_product_by_barcode(barcode):
    return get_db().execute('SELECT * FROM products WHERE barcode = ?', (barcode,)).fetchone()


def add_product(barcode, name, category='', cost=0.0, price=0.0, stock=0):
    conn = get_db()
    conn.execute('INSERT INTO products (barcode, name, category, cost, price, stock) VALUES (?,?,?,?,?,?)',
                 (barcode, name, category, cost, price, stock))
    conn.commit()


def update_product(pid, barcode, name, category='', cost=0.0, price=0.0, stock=0):
    conn = get_db()
    conn.execute('UPDATE products SET barcode=?, name=?, category=?, cost=?, price=?, stock=? WHERE id=?',
                 (barcode, name, category, cost, price, stock, pid))
    conn.commit()


def delete_product(pid):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id = ?', (pid,))
    conn.commit()


def check_stock(items):
    """items: list of dicts with keys product_id, qty, name. Returns list of (name, available)."""
    conn = get_db()
    problems = []
    for it in items:
        row = conn.execute('SELECT name, stock FROM products WHERE id = ?', (it['product_id'],)).fetchone()
        avail = row['stock'] if row else 0
        if avail < it['qty']:
            problems.append((it['name'], avail))
    return problems


# ---------------- sales ----------------
def create_sale(items):
    """items: list of dicts with keys product_id, barcode, name, price, qty.
    Saves the sale, decrements stock atomically. Returns (sale_id, total)."""
    conn = get_db()
    total = sum(i['price'] * i['qty'] for i in items)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO sales (created_at, total) VALUES (?,?)', (now, total))
        sale_id = cur.lastrowid
        for i in items:
            cur.execute('INSERT INTO sale_items (sale_id, product_id, barcode, name, price, qty) VALUES (?,?,?,?,?,?)',
                        (sale_id, i['product_id'], i['barcode'], i['name'], i['price'], i['qty']))
            cur.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (i['qty'], i['product_id']))
        conn.commit()
        return sale_id, total
    except sqlite3.Error:
        conn.rollback()
        raise


def list_sales():
    return get_db().execute(
        "SELECT s.id AS id, s.created_at AS created_at, s.total AS total, "
        "COALESCE(SUM(i.qty), 0) AS items "
        "FROM sales s LEFT JOIN sale_items i ON i.sale_id = s.id "
        "GROUP BY s.id ORDER BY s.id DESC").fetchall()


def get_sale(sale_id):
    return get_db().execute('SELECT * FROM sales WHERE id = ?', (sale_id,)).fetchone()


def get_sale_items(sale_id):
    return get_db().execute('SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id', (sale_id,)).fetchall()


# ---------------- export ----------------
def export_csv(filename, header, rows):
    base = os.path.dirname(os.path.abspath(_path or _default_path()))
    path = os.path.join(base, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow([r[h] for h in header])
    return path
