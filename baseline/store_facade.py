import os

import db
import db_schema


def use_sqlite():
    return os.getenv("FAKE_UI_STORE", "").strip().lower() in {"sqlite", "db"}


def ensure_sqlite(path=None):
    db_path = db.database_path(path)
    db_schema.migrate(db_path)
    return db_path
