import db
import db_schema


def use_sqlite():
    return True


def ensure_sqlite(path=None):
    db_path = db.database_path(path)
    db_schema.migrate(db_path)
    return db_path
