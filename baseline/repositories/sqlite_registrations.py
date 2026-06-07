from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class _SQLiteTokenRepository(SQLiteRepository):
    table = ""

    def upsert(self, item):
        token = str(item.get("token") or item.get("id") or "").strip()
        if not token:
            raise RuntimeError("token is required")
        data = dict(item)
        data["token"] = token
        with self.transaction() as conn:
            conn.execute(
                f"""
                insert or replace into {self.table}
                (id, username, status, data_json, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    token,
                    str(data.get("username", "")),
                    str(data.get("status", "")),
                    dump_json(data),
                    str(data.get("created_at", "")),
                ),
            )
        return data

    def list(self, status=None):
        params = []
        where = ""
        if status:
            where = "where status = ?"
            params.append(status)
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select id, username, status, data_json, created_at
                from {self.table}
                {where}
                order by created_at desc, id desc
                """,
                params,
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, token):
        with self.transaction() as conn:
            row = conn.execute(
                f"""
                select id, username, status, data_json, created_at
                from {self.table}
                where id = ?
                """,
                (token,),
            ).fetchone()
        return self._inflate(row) if row else None

    def update(self, token, **updates):
        item = self.get(token)
        if not item:
            raise RuntimeError("request not found")
        item.update(updates)
        return self.upsert(item)

    def _inflate(self, row):
        item = load_json(row["data_json"])
        item.update(
            {
                "token": row["id"],
                "username": row["username"],
                "status": row["status"],
            }
        )
        if row["created_at"]:
            item["created_at"] = row["created_at"]
        return item


class SQLiteRegistrationsRepository(_SQLiteTokenRepository):
    table = "registrations"


class SQLitePasswordResetsRepository(_SQLiteTokenRepository):
    table = "password_resets"
