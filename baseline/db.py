import sqlite3
from contextlib import contextmanager
from pathlib import Path

import panel_config


def database_path(path=None):
    if path is not None:
        return Path(path)
    return Path(panel_config.PANEL_DIR) / "fake-ui.db"


def connect(path=None):
    db_path = database_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma busy_timeout = 5000")
    return conn


def row_dict(row):
    return dict(row) if row is not None else None


@contextmanager
def transaction(path=None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
