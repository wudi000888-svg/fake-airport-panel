#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))

import db
import db_schema


def read_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_raw(item):
    return json.dumps(item or {}, ensure_ascii=False, sort_keys=True)


def migrate_plans(conn, plans):
    for plan in plans:
        plan_id = str(plan.get("id", "")).strip()
        if not plan_id:
            continue
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
                dump_raw(plan),
                1 if plan.get("enabled", True) else 0,
                int(plan.get("sort", 100) or 100),
                str(plan.get("created_at", "")),
                str(plan.get("updated_at", "")),
            ),
        )


def migrate_orders(conn, orders):
    for order in orders:
        order_id = str(order.get("id", "")).strip()
        if not order_id:
            continue
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
                str(order.get("kind", "renew")),
                str(order.get("plan_id", "")),
                str(order.get("plan_name", "")),
                str(order.get("amount", "0")),
                int(order.get("days", 0) or 0),
                float(order.get("traffic_gb", 0) or 0),
                str(order.get("payment_status", "")),
                str(order.get("payment_id", "")),
                dump_raw(order),
                str(order.get("created_at", "")),
                str(order.get("updated_at", "")),
            ),
        )


def migrate_payment_methods(conn, methods):
    for method in methods:
        method_id = str(method.get("id", "")).strip()
        if not method_id:
            continue
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
                int(method.get("sort", 100) or 100),
                dump_raw(method),
                str(method.get("updated_at", "")),
            ),
        )


def migrate_payments(conn, payments):
    for payment in payments:
        payment_id = str(payment.get("id", "")).strip()
        if not payment_id:
            continue
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
                str(payment.get("status", "")),
                str(payment.get("asset", "")),
                str(payment.get("chain", "")),
                str(payment.get("txid", "")),
                dump_raw(payment),
                str(payment.get("created_at", "")),
                str(payment.get("updated_at", "")),
            ),
        )


def migrate_settings(conn, key, value):
    conn.execute(
        """
        insert or replace into settings (key, value_json, updated_at)
        values (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        """,
        (key, dump_raw(value)),
    )


def migrate_json_to_sqlite(data_dir, db_path):
    data_dir = Path(data_dir)
    db_schema.migrate(db_path)
    plans = read_json(data_dir / "plans.json", {"plans": []}).get("plans", [])
    orders = read_json(data_dir / "orders.json", {"orders": []}).get("orders", [])
    payments_data = read_json(data_dir / "payments.json", {"methods": [], "payments": [], "rates": {"overrides": {}, "cache": {}}})
    with db.transaction(db_path) as conn:
        migrate_plans(conn, plans)
        migrate_orders(conn, orders)
        migrate_payment_methods(conn, payments_data.get("methods", []))
        migrate_payments(conn, payments_data.get("payments", []))
        migrate_settings(conn, "payment_rates", payments_data.get("rates", {"overrides": {}, "cache": {}}))


def main():
    parser = argparse.ArgumentParser(description="Import fake-ui JSON data into SQLite.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    migrate_json_to_sqlite(Path(args.data_dir), Path(args.db))


if __name__ == "__main__":
    main()
