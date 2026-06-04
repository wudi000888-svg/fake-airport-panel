import json

import db


def dump_json(data):
    return json.dumps(data or {}, ensure_ascii=False, sort_keys=True)


def load_json(raw):
    if not raw:
        return {}
    return json.loads(raw)


class SQLiteRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def transaction(self):
        return db.transaction(self.db_path)
