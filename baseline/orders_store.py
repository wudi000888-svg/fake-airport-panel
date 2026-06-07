import secrets
from datetime import datetime, timezone

import store_facade
from repositories.sqlite_orders import SQLiteOrdersRepository


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_orders():
    store_facade.ensure_sqlite()
    return {"version": 2, "orders": SQLiteOrdersRepository().list(limit=100000)}


def save_orders(data):
    store_facade.ensure_sqlite()
    repo = SQLiteOrdersRepository()
    for order in (data or {}).get("orders", []):
        repo.upsert(order)
    return data


def list_orders(username=None, limit=200):
    store_facade.ensure_sqlite()
    return SQLiteOrdersRepository().list(username=username, limit=limit)


def record_order(username, kind, plan=None, amount=0, status="completed", note="", operator="system"):
    order = {
        "id": "ord_" + secrets.token_hex(8),
        "username": username,
        "kind": kind,
        "plan_id": (plan or {}).get("id", ""),
        "plan_name": (plan or {}).get("name", ""),
        "days": int((plan or {}).get("days", 0) or 0),
        "traffic_gb": float((plan or {}).get("traffic_gb", 0) or 0),
        "amount": float(amount or 0),
        "status": status,
        "note": note,
        "operator": operator,
        "created_at": now_iso(),
    }
    store_facade.ensure_sqlite()
    return SQLiteOrdersRepository().upsert(order)


def get_order(order_id):
    store_facade.ensure_sqlite()
    return SQLiteOrdersRepository().get(order_id)


def create_pending_order(username, kind, plan, note="", operator="user"):
    return record_order(
        username=username,
        kind=kind,
        plan=plan,
        amount=(plan or {}).get("price", 0),
        status="pending",
        note=note,
        operator=operator,
    )


def update_order(order_id, **updates):
    store_facade.ensure_sqlite()
    updates["updated_at"] = now_iso()
    return SQLiteOrdersRepository().update(order_id, **updates)
