from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class SQLiteOrdersRepository(SQLiteRepository):
    def upsert(self, order):
        order_id = str(order.get("id", "")).strip()
        if not order_id:
            raise RuntimeError("order id is required")
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into orders
                (id, username, status, kind, plan_id, plan_name, amount, days, traffic_gb,
                 payment_status, payment_id, data_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    str(order.get("username", "")),
                    str(order.get("status", "pending")),
                    str(order.get("kind", "")),
                    str(order.get("plan_id", "")),
                    str(order.get("plan_name", "")),
                    str(order.get("amount", "0")),
                    int(order.get("days", 0) or 0),
                    float(order.get("traffic_gb", 0) or 0),
                    str(order.get("payment_status", "")),
                    str(order.get("payment_id", "")),
                    dump_json(order),
                    str(order.get("created_at", "")),
                    str(order.get("updated_at", "")),
                ),
            )
        return order

    def list(self, username=None, limit=200):
        params = []
        where = ""
        if username:
            where = "where username = ?"
            params.append(username)
        params.append(int(limit or 200))
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select id, username, status, kind, plan_id, plan_name, amount, days, traffic_gb,
                       payment_status, payment_id, data_json, created_at, updated_at
                from orders
                {where}
                order by created_at desc, id desc
                limit ?
                """,
                params,
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, order_id):
        with self.transaction() as conn:
            row = conn.execute(
                """
                select id, username, status, kind, plan_id, plan_name, amount, days, traffic_gb,
                       payment_status, payment_id, data_json, created_at, updated_at
                from orders
                where id = ?
                """,
                (order_id,),
            ).fetchone()
        return self._inflate(row) if row else None

    def _inflate(self, row):
        order = load_json(row["data_json"])
        order.update(
            {
                "id": row["id"],
                "username": row["username"],
                "status": row["status"],
                "kind": row["kind"],
                "plan_id": row["plan_id"],
                "plan_name": row["plan_name"],
                "amount": row["amount"],
                "days": row["days"],
                "traffic_gb": row["traffic_gb"],
                "payment_status": row["payment_status"],
                "payment_id": row["payment_id"],
            }
        )
        if row["created_at"]:
            order["created_at"] = row["created_at"]
        if row["updated_at"]:
            order["updated_at"] = row["updated_at"]
        return order
