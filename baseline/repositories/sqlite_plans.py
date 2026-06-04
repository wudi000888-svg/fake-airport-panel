from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class SQLitePlansRepository(SQLiteRepository):
    def upsert(self, plan):
        plan_id = str(plan.get("id", "")).strip()
        if not plan_id:
            raise RuntimeError("plan id is required")
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into plans
                (id, name, days, traffic_gb, price, data_json, enabled, sort_order, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    str(plan.get("name") or plan_id),
                    int(plan.get("days", 0) or 0),
                    float(plan.get("traffic_gb", 0) or 0),
                    str(plan.get("price", plan.get("amount", "0"))),
                    dump_json(plan),
                    1 if plan.get("enabled", True) else 0,
                    int(plan.get("sort", plan.get("sort_order", 100)) or 100),
                    str(plan.get("created_at", "")),
                    str(plan.get("updated_at", "")),
                ),
            )
        return plan

    def list(self, include_disabled=True):
        where = "" if include_disabled else "where enabled = 1"
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select id, name, days, traffic_gb, price, data_json, enabled, sort_order, created_at, updated_at
                from plans
                {where}
                order by sort_order asc, id asc
                """
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, plan_id):
        with self.transaction() as conn:
            row = conn.execute(
                """
                select id, name, days, traffic_gb, price, data_json, enabled, sort_order, created_at, updated_at
                from plans
                where id = ?
                """,
                (plan_id,),
            ).fetchone()
        return self._inflate(row) if row else None

    def set_enabled(self, plan_id, enabled):
        plan = self.get(plan_id)
        if not plan:
            raise RuntimeError("plan not found")
        plan["enabled"] = bool(enabled)
        return self.upsert(plan)

    def delete(self, plan_id):
        with self.transaction() as conn:
            cursor = conn.execute("delete from plans where id = ?", (plan_id,))
            if cursor.rowcount == 0:
                raise RuntimeError("plan not found")
        return True

    def _inflate(self, row):
        plan = load_json(row["data_json"])
        plan.update(
            {
                "id": row["id"],
                "name": row["name"],
                "days": row["days"],
                "traffic_gb": row["traffic_gb"],
                "price": row["price"],
                "enabled": bool(row["enabled"]),
                "sort": row["sort_order"],
            }
        )
        if row["created_at"]:
            plan["created_at"] = row["created_at"]
        if row["updated_at"]:
            plan["updated_at"] = row["updated_at"]
        return plan
