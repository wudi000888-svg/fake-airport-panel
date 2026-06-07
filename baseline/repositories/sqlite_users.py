from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class SQLiteUsersRepository(SQLiteRepository):
    def upsert(self, user):
        username = str(user.get("username", "")).strip()
        if not username:
            raise RuntimeError("username is required")
        item = dict(user)
        item["username"] = username
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into users
                (username, data_json, enabled, plan_id, expires_at, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    dump_json(item),
                    1 if item.get("enabled", True) else 0,
                    str(item.get("plan_id", "")),
                    str(item.get("expires_at", "")),
                    str(item.get("updated_at", "")),
                ),
            )
        return item

    def list(self):
        with self.transaction() as conn:
            rows = conn.execute(
                """
                select username, data_json, enabled, plan_id, expires_at, updated_at
                from users
                order by username asc
                """
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, username):
        with self.transaction() as conn:
            row = conn.execute(
                """
                select username, data_json, enabled, plan_id, expires_at, updated_at
                from users
                where username = ?
                """,
                (username,),
            ).fetchone()
        return self._inflate(row) if row else None

    def delete(self, username):
        with self.transaction() as conn:
            cursor = conn.execute("delete from users where username = ?", (username,))
        return cursor.rowcount > 0

    def _inflate(self, row):
        user = load_json(row["data_json"])
        user.update(
            {
                "username": row["username"],
                "enabled": bool(row["enabled"]),
                "plan_id": row["plan_id"],
                "expires_at": row["expires_at"],
            }
        )
        if row["updated_at"]:
            user["updated_at"] = row["updated_at"]
        return user
