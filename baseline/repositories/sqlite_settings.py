from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class SQLiteSettingsRepository(SQLiteRepository):
    def get(self, key, default=None):
        with self.transaction() as conn:
            row = conn.execute("select value_json from settings where key = ?", (key,)).fetchone()
        if not row:
            return default
        return load_json(row["value_json"])

    def set(self, key, value):
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into settings (key, value_json, updated_at)
                values (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                """,
                (key, dump_json(value)),
            )
        return value
