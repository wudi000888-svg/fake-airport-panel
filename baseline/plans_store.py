import secrets
from datetime import datetime, timezone

import store_facade
from repositories.sqlite_plans import SQLitePlansRepository


def now_iso():
    return datetime.now(timezone.utc).isoformat()


DEFAULT_PLANS = [
    {
        "id": "starter",
        "name": "Starter",
        "days": 30,
        "traffic_gb": 100,
        "price": 0,
        "node_groups": ["default"],
        "enabled": True,
        "sort": 10,
    },
    {
        "id": "standard",
        "name": "Standard",
        "days": 30,
        "traffic_gb": 300,
        "price": 0,
        "node_groups": ["default"],
        "enabled": True,
        "sort": 20,
    },
]


def default_data():
    return {"version": 1, "plans": DEFAULT_PLANS}


def load_plans():
    store_facade.ensure_sqlite()
    plans = SQLitePlansRepository().list()
    existing_ids = {plan.get("id") for plan in plans}
    changed = False
    for plan in DEFAULT_PLANS:
        if plan["id"] not in existing_ids:
            item = dict(plan)
            item.setdefault("created_at", now_iso())
            item.setdefault("updated_at", now_iso())
            SQLitePlansRepository().upsert(item)
            changed = True
    if changed:
        plans = SQLitePlansRepository().list()
    return {"version": 2, "plans": plans}


def save_plans(data):
    store_facade.ensure_sqlite()
    repo = SQLitePlansRepository()
    for plan in (data or {}).get("plans", []):
        repo.upsert(plan)
    return data


def list_plans(include_disabled=True):
    plans = load_plans().get("plans", [])
    if not include_disabled:
        plans = [p for p in plans if p.get("enabled", True)]
    return sorted(plans, key=lambda p: (int(p.get("sort", 0) or 0), p.get("id", "")))


def get_plan(plan_id):
    for plan in load_plans().get("plans", []):
        if plan.get("id") == plan_id:
            return plan
    return None


def normalize_plan(data):
    plan_id = (data.get("id") or data.get("name") or secrets.token_hex(4)).strip()
    plan_id = "".join(ch for ch in plan_id.lower().replace(" ", "-") if ch.isalnum() or ch in "-_")
    if not plan_id:
        plan_id = secrets.token_hex(4)
    days = int(data.get("days", 30))
    traffic_gb = float(data.get("traffic_gb", 0) or 0)
    price = float(data.get("price", 0) or 0)
    if days <= 0:
        raise RuntimeError("plan days must be greater than 0")
    if traffic_gb < 0:
        raise RuntimeError("plan traffic cannot be negative")
    groups = data.get("node_groups", ["default"])
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.split(",") if g.strip()]
    return {
        "id": plan_id,
        "name": (data.get("name") or plan_id).strip(),
        "days": days,
        "traffic_gb": traffic_gb,
        "price": price,
        "node_groups": groups or ["default"],
        "enabled": bool(data.get("enabled", True)),
        "sort": int(data.get("sort", 100) or 100),
        "updated_at": now_iso(),
    }


def upsert_plan(data):
    plan = normalize_plan(data)
    store_facade.ensure_sqlite()
    existing = SQLitePlansRepository().get(plan["id"])
    if existing and existing.get("created_at"):
        plan["created_at"] = existing["created_at"]
    else:
        plan["created_at"] = now_iso()
    return SQLitePlansRepository().upsert(plan)


def set_plan_enabled(plan_id, enabled):
    store_facade.ensure_sqlite()
    return SQLitePlansRepository().set_enabled(plan_id, enabled)


def delete_plan(plan_id):
    store_facade.ensure_sqlite()
    return SQLitePlansRepository().delete(plan_id)
