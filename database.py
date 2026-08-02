import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "mirror.db"

_lock = threading.Lock()
_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.execute("PRAGMA journal_mode=WAL")
_conn.execute("PRAGMA synchronous=NORMAL")

_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        src_chat_id INTEGER NOT NULL,
        src_msg_id INTEGER NOT NULL,
        dst_chat_id INTEGER NOT NULL,
        dst_msg_id INTEGER NOT NULL,
        media_group_id TEXT,
        UNIQUE(src_chat_id, src_msg_id)
    )
    """
)
_conn.commit()


def add_mapping(src_chat_id, src_msg_id, dst_chat_id, dst_msg_id, media_group_id=None):
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO mappings (src_chat_id, src_msg_id, dst_chat_id, dst_msg_id, media_group_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (src_chat_id, src_msg_id, dst_chat_id, dst_msg_id, media_group_id),
        )
        _conn.commit()


def get_mapping(src_chat_id, src_msg_id):
    with _lock:
        row = _conn.execute(
            "SELECT * FROM mappings WHERE src_chat_id = ? AND src_msg_id = ?",
            (src_chat_id, src_msg_id),
        ).fetchone()
        return dict(row) if row else None


def delete_mapping(src_chat_id, src_msg_id):
    with _lock:
        _conn.execute(
            "DELETE FROM mappings WHERE src_chat_id = ? AND src_msg_id = ?",
            (src_chat_id, src_msg_id),
        )
        _conn.commit()
def get_all_mappings():
    """Return every mapping row (used by the delete poller)."""
    with _lock:
        return [dict(r) for r in _conn.execute("SELECT * FROM mappings ORDER BY id").fetchall()]
