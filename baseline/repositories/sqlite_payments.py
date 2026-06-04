from repositories.sqlite_base import SQLiteRepository, dump_json, load_json


class SQLitePaymentMethodsRepository(SQLiteRepository):
    def upsert(self, method):
        method_id = str(method.get("id", "")).strip()
        if not method_id:
            raise RuntimeError("payment method id is required")
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into payment_methods
                (id, asset, chain, enabled, sort_order, data_json, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    method_id,
                    str(method.get("asset", "")),
                    str(method.get("chain", "")),
                    1 if method.get("enabled", True) else 0,
                    int(method.get("sort", method.get("sort_order", 100)) or 100),
                    dump_json(method),
                    str(method.get("updated_at", "")),
                ),
            )
        return method

    def list(self, include_disabled=True):
        where = "" if include_disabled else "where enabled = 1"
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select id, asset, chain, enabled, sort_order, data_json, updated_at
                from payment_methods
                {where}
                order by sort_order asc, id asc
                """
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, method_id):
        with self.transaction() as conn:
            row = conn.execute(
                """
                select id, asset, chain, enabled, sort_order, data_json, updated_at
                from payment_methods
                where id = ?
                """,
                (method_id,),
            ).fetchone()
        return self._inflate(row) if row else None

    def set_enabled(self, method_id, enabled):
        method = self.get(method_id)
        if not method:
            raise RuntimeError("payment method not found")
        method["enabled"] = bool(enabled)
        return self.upsert(method)

    def delete(self, method_id):
        with self.transaction() as conn:
            cursor = conn.execute("delete from payment_methods where id = ?", (method_id,))
            if cursor.rowcount == 0:
                raise RuntimeError("payment method not found")
        return True

    def _inflate(self, row):
        method = load_json(row["data_json"])
        method.update(
            {
                "id": row["id"],
                "asset": row["asset"],
                "chain": row["chain"],
                "enabled": bool(row["enabled"]),
                "sort": row["sort_order"],
            }
        )
        if row["updated_at"]:
            method["updated_at"] = row["updated_at"]
        return method


class SQLitePaymentsRepository(SQLiteRepository):
    def upsert(self, payment):
        payment_id = str(payment.get("id", "")).strip()
        if not payment_id:
            raise RuntimeError("payment id is required")
        with self.transaction() as conn:
            conn.execute(
                """
                insert or replace into payments
                (id, order_id, username, status, asset, chain, txid, data_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment_id,
                    str(payment.get("order_id", "")),
                    str(payment.get("username", "")),
                    str(payment.get("status", "awaiting_payment")),
                    str(payment.get("asset", "")),
                    str(payment.get("chain", "")),
                    str(payment.get("txid", "")),
                    dump_json(payment),
                    str(payment.get("created_at", "")),
                    str(payment.get("updated_at", "")),
                ),
            )
        return payment

    def list(self, username=None, limit=200):
        params = []
        where = ""
        if username is not None:
            where = "where username = ?"
            params.append(username)
        if limit is None:
            limit = 100000
        params.append(int(limit or 200))
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select id, order_id, username, status, asset, chain, txid, data_json, created_at, updated_at
                from payments
                {where}
                order by created_at desc, id desc
                limit ?
                """,
                params,
            ).fetchall()
        return [self._inflate(row) for row in rows]

    def get(self, payment_id):
        with self.transaction() as conn:
            row = conn.execute(
                """
                select id, order_id, username, status, asset, chain, txid, data_json, created_at, updated_at
                from payments
                where id = ?
                """,
                (payment_id,),
            ).fetchone()
        return self._inflate(row) if row else None

    def txid_used(self, txid, exclude_payment_id=None):
        normalized = str(txid or "").strip().lower()
        if not normalized:
            return False
        params = [normalized]
        extra = ""
        if exclude_payment_id:
            extra = "and id != ?"
            params.append(exclude_payment_id)
        with self.transaction() as conn:
            row = conn.execute(
                f"select 1 from payments where lower(txid) = ? {extra} limit 1",
                params,
            ).fetchone()
        return bool(row)

    def update(self, payment_id, **updates):
        payment = self.get(payment_id)
        if not payment:
            raise RuntimeError("payment not found")
        payment.update(updates)
        self.upsert(payment)
        return payment

    def _inflate(self, row):
        payment = load_json(row["data_json"])
        payment.update(
            {
                "id": row["id"],
                "order_id": row["order_id"],
                "username": row["username"],
                "status": row["status"],
                "asset": row["asset"],
                "chain": row["chain"],
                "txid": row["txid"],
            }
        )
        if row["created_at"]:
            payment["created_at"] = row["created_at"]
        if row["updated_at"]:
            payment["updated_at"] = row["updated_at"]
        return payment


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
