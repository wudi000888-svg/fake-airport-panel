from repositories.sqlite_base import SQLiteRepository


def to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def bucket_expression(granularity):
    if granularity == "day":
        return "strftime('%Y-%m-%dT00:00:00+00:00', sampled_at)"
    return "strftime('%Y-%m-%dT%H:00:00+00:00', sampled_at)"


class SQLiteTrafficRepository(SQLiteRepository):
    def add_sample(self, sample):
        item = {
            "username": str(sample.get("username", "")).strip(),
            "source": str(sample.get("source", "")).strip(),
            "node_id": str(sample.get("node_id", "")).strip(),
            "uplink_bytes": max(0, to_int(sample.get("uplink_bytes", 0))),
            "downlink_bytes": max(0, to_int(sample.get("downlink_bytes", 0))),
            "sampled_at": str(sample.get("sampled_at", "")).strip(),
        }
        item["total_bytes"] = item["uplink_bytes"] + item["downlink_bytes"]
        if not item["username"]:
            raise RuntimeError("username is required")
        if not item["sampled_at"]:
            raise RuntimeError("sampled_at is required")
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                insert into traffic_samples
                (username, source, node_id, uplink_bytes, downlink_bytes, total_bytes, sampled_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["username"],
                    item["source"],
                    item["node_id"],
                    item["uplink_bytes"],
                    item["downlink_bytes"],
                    item["total_bytes"],
                    item["sampled_at"],
                ),
            )
            item["id"] = cursor.lastrowid
        return item

    def series(self, start, end, granularity="hour"):
        bucket = bucket_expression(granularity)
        with self.transaction() as conn:
            rows = conn.execute(
                f"""
                select {bucket} as bucket,
                       coalesce(sum(uplink_bytes), 0) as uplink_bytes,
                       coalesce(sum(downlink_bytes), 0) as downlink_bytes,
                       coalesce(sum(total_bytes), 0) as total_bytes
                from traffic_samples
                where sampled_at >= ? and sampled_at < ?
                group by bucket
                order by bucket asc
                """,
                (start, end),
            ).fetchall()
        return [self._traffic_row(row) | {"bucket": row["bucket"]} for row in rows]

    def top_users(self, start, end, limit=12):
        with self.transaction() as conn:
            rows = conn.execute(
                """
                select username,
                       coalesce(sum(uplink_bytes), 0) as uplink_bytes,
                       coalesce(sum(downlink_bytes), 0) as downlink_bytes,
                       coalesce(sum(total_bytes), 0) as total_bytes
                from traffic_samples
                where sampled_at >= ? and sampled_at < ?
                group by username
                order by total_bytes desc, username asc
                limit ?
                """,
                (start, end, max(1, min(100, to_int(limit, 12)))),
            ).fetchall()
        return [self._traffic_row(row) | {"username": row["username"]} for row in rows]

    def by_node(self, start, end):
        with self.transaction() as conn:
            rows = conn.execute(
                """
                select node_id, source,
                       coalesce(sum(uplink_bytes), 0) as uplink_bytes,
                       coalesce(sum(downlink_bytes), 0) as downlink_bytes,
                       coalesce(sum(total_bytes), 0) as total_bytes
                from traffic_samples
                where sampled_at >= ? and sampled_at < ?
                group by node_id, source
                order by total_bytes desc, node_id asc
                """,
                (start, end),
            ).fetchall()
        return [self._traffic_row(row) | {"node_id": row["node_id"], "source": row["source"]} for row in rows]

    def totals(self, start=None, end=None):
        params = []
        where = []
        if start:
            where.append("sampled_at >= ?")
            params.append(start)
        if end:
            where.append("sampled_at < ?")
            params.append(end)
        clause = f"where {' and '.join(where)}" if where else ""
        with self.transaction() as conn:
            row = conn.execute(
                f"""
                select coalesce(sum(uplink_bytes), 0) as uplink_bytes,
                       coalesce(sum(downlink_bytes), 0) as downlink_bytes,
                       coalesce(sum(total_bytes), 0) as total_bytes
                from traffic_samples
                {clause}
                """,
                params,
            ).fetchone()
        return self._traffic_row(row)

    def delete_before(self, cutoff):
        cutoff = str(cutoff or "").strip()
        if not cutoff:
            return 0
        with self.transaction() as conn:
            cursor = conn.execute("delete from traffic_samples where sampled_at < ?", (cutoff,))
            return cursor.rowcount

    def _traffic_row(self, row):
        return {
            "uplink_bytes": to_int(row["uplink_bytes"]),
            "downlink_bytes": to_int(row["downlink_bytes"]),
            "total_bytes": to_int(row["total_bytes"]),
        }
