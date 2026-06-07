from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class SQLiteNodesRepository(SQLiteRepository):
    def upsert(self, node):
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            raise RuntimeError("node id is required")
        item = dict(node)
        item["id"] = node_id
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into nodes
                (id, kind, enabled, sort_order, data_json, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    str(item.get("kind", "")),
                    1 if item.get("enabled", True) else 0,
                    int(item.get("sort", item.get("sort_order", 100)) or 100),
                    dump_json(item),
                    str(item.get("updated_at", "")),
                ),
            )
        return item

    def list(self, kind=None, include_disabled=True):
        params = []
        where = []
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if not include_disabled:
            where.append("enabled = 1")
        clause = "where " + " and ".join(where) if where else ""
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select id, kind, enabled, sort_order, data_json, updated_at
                from nodes
                {clause}
                order by sort_order asc, id asc
                """,
                params,
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, node_id):
        with self.transaction() as conn:
            row = conn.execute(
                """
                select id, kind, enabled, sort_order, data_json, updated_at
                from nodes
                where id = ?
                """,
                (node_id,),
            ).fetchone()
        return self._inflate(row) if row else None

    def delete(self, node_id):
        with self.transaction() as conn:
            cursor = conn.execute("delete from nodes where id = ?", (node_id,))
        return cursor.rowcount > 0

    def _inflate(self, row):
        node = load_json(row["data_json"])
        node.update(
            {
                "id": row["id"],
                "kind": row["kind"],
                "enabled": bool(row["enabled"]),
                "sort": row["sort_order"],
            }
        )
        if row["updated_at"]:
            node["updated_at"] = row["updated_at"]
        return node
