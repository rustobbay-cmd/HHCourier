import sqlite3
import os
from contextlib import contextmanager
from config import CAFE_DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(CAFE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_courier_tables():
    with get_conn() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS couriers
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER UNIQUE,
                         name TEXT,
                         phone TEXT,
                         status TEXT DEFAULT "pending")''')
        conn.execute('''CREATE TABLE IF NOT EXISTS deliveries
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         order_id INTEGER,
                         courier_id INTEGER,
                         taken_at TEXT,
                         delivered_at TEXT,
                         payment_method TEXT)''')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_couriers_user ON couriers(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_courier ON deliveries(courier_id)")

        for col, coltype in [
            ("update_type", "TEXT"),
            ("courier_user_id", "INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE pending_updates ADD COLUMN {col} {coltype}")
            except Exception:
                pass


def get_courier(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM couriers WHERE user_id = ?", (user_id,)
        ).fetchone()


def add_courier(user_id: int, name: str, phone: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO couriers (user_id, name, phone, status) VALUES (?, ?, ?, 'pending')",
            (user_id, name, phone)
        )


def update_courier_status(user_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE couriers SET status = ? WHERE user_id = ?", (status, user_id)
        )


def get_active_couriers():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM couriers WHERE status = 'active'"
        ).fetchall()


def get_active_orders():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE status = 'В пути'"
        ).fetchall()


def get_order_by_id(order_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()


def update_order_status(order_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
        )


def take_order(order_id: int, courier_id: int) -> bool:
    from datetime import datetime
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM deliveries WHERE order_id = ?", (order_id,)
        ).fetchone()
        if exists:
            return False
        conn.execute(
            "INSERT INTO deliveries (order_id, courier_id, taken_at) VALUES (?, ?, ?)",
            (order_id, courier_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        return True


def complete_delivery(order_id: int, payment_method: str):
    from datetime import datetime
    with get_conn() as conn:
        conn.execute(
            "UPDATE deliveries SET delivered_at = ?, payment_method = ? WHERE order_id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), payment_method, order_id)
        )


def get_courier_history(courier_id: int):
    with get_conn() as conn:
        return conn.execute(
            '''SELECT d.*, o.details, o.address, o.daily_number, o.order_date
               FROM deliveries d
               JOIN orders o ON d.order_id = o.id
               WHERE d.courier_id = ?
               AND d.delivered_at IS NOT NULL
               ORDER BY d.delivered_at DESC
               LIMIT 20''',
            (courier_id,)
        ).fetchall()


def add_pending_update(order_id: int, courier_name: str, courier_user_id: int,
                       payment_method: str, update_type: str = "delivered") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO pending_updates "
            "(order_id, courier_name, courier_user_id, payment_method, update_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, courier_name, courier_user_id, payment_method, update_type)
        )


def get_my_notifications(courier_user_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM courier_notifications "
            "WHERE courier_user_id = ? AND processed = 0",
            (courier_user_id,)
        ).fetchall()


def mark_my_notification_processed(notification_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE courier_notifications SET processed = 1 WHERE id = ?",
            (notification_id,)
        )


def format_order_number(order_id: int, daily_number, order_date) -> str:
    if daily_number and order_date:
        parts = order_date.split(".")
        short_date = f"{parts[0]}.{parts[1]}"
        return f"№{daily_number} ({short_date})"
    return f"№{order_id}"
