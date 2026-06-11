import urllib.parse
from datetime import datetime, timedelta, timezone

import node_catalog
import plans_store
import traffic_store
import user_store


def parse_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value):
    parsed = parse_time(value)
    if parsed is None:
        return None
    return parsed.replace(minute=0, second=0, microsecond=0)


def window_from_query(query):
    start = parse_time((query.get("from") or [""])[0])
    end = parse_time((query.get("to") or [""])[0])
    if start and end and start < end:
        return iso(start), iso(end)

    range_value = (query.get("range") or ["24h"])[0]
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    days = 1
    if range_value in {"7d", "week"}:
        days = 7
    elif range_value in {"30d", "month"}:
        days = 30
    return iso(now - timedelta(days=days)), iso(now)


def query_params(path):
    parsed = urllib.parse.urlparse(path)
    return urllib.parse.parse_qs(parsed.query)


def bytes_to_gb(value):
    return round(int(value or 0) / 1024 / 1024 / 1024, 3)


def zero_row(bucket):
    return {"bucket": iso(bucket), "uplink_bytes": 0, "downlink_bytes": 0, "total_bytes": 0}


def floor_bucket(dt, granularity):
    dt = dt.replace(second=0, microsecond=0)
    if granularity == "day":
        return dt.replace(hour=0, minute=0)
    return dt.replace(minute=0)


def ceil_bucket(dt, granularity):
    floored = floor_bucket(dt, granularity)
    step = timedelta(days=1) if granularity == "day" else timedelta(hours=1)
    return floored if dt == floored else floored + step


def fill_series(start, end, granularity, rows):
    start_dt = parse_time(start)
    end_dt = parse_time(end)
    if not start_dt or not end_dt or start_dt >= end_dt:
        return rows
    step = timedelta(days=1) if granularity == "day" else timedelta(hours=1)
    start_dt = floor_bucket(start_dt, granularity)
    end_dt = ceil_bucket(end_dt, granularity)
    by_bucket = {row.get("bucket"): row for row in rows}
    result = []
    cursor = start_dt
    max_points = 370 if granularity == "day" else 24 * 32
    while cursor < end_dt and len(result) < max_points:
        key = iso(cursor)
        result.append(by_bucket.get(key, zero_row(cursor)))
        cursor += step
    return result


def plan_distribution(users):
    plans = {plan.get("id", ""): plan for plan in plans_store.list_plans(include_disabled=True)}
    counts = {}
    for user in users:
        plan_id = user.get("plan_id", "")
        name = plans.get(plan_id, {}).get("name") or "无套餐"
        counts[name] = counts.get(name, 0) + 1
    return counts


def overview():
    users_data = user_store.load_users().get("users", {})
    users = list(users_data.values())
    enabled = [user for user in users if user.get("enabled", True)]
    nodes = node_catalog.list_public_nodes(admin=True)
    total_quota = sum(int(user.get("quota_bytes", 0) or 0) for user in users)
    total_used = sum(int(user.get("used_bytes", 0) or 0) for user in users)
    traffic = traffic_store.totals()
    return {
        "users_total": len(users),
        "users_enabled": len(enabled),
        "users_disabled": max(0, len(users) - len(enabled)),
        "nodes_total": len(nodes),
        "nodes_online": len([node for node in nodes if node.get("enabled", True)]),
        "quota_total_bytes": total_quota,
        "quota_used_bytes": total_used,
        "quota_used_gb": bytes_to_gb(total_used),
        "traffic_total_bytes": traffic["total_bytes"],
        "traffic_total_gb": bytes_to_gb(traffic["total_bytes"]),
        "traffic_uplink_bytes": traffic["uplink_bytes"],
        "traffic_downlink_bytes": traffic["downlink_bytes"],
        "plans": plan_distribution(users),
    }


def traffic_series(query):
    start, end = window_from_query(query)
    granularity = (query.get("granularity") or ["hour"])[0]
    if granularity not in {"hour", "day"}:
        granularity = "hour"
    return {
        "from": start,
        "to": end,
        "granularity": granularity,
        "series": fill_series(start, end, granularity, traffic_store.series(start, end, granularity)),
    }


def top_users(query):
    start, end = window_from_query(query)
    limit = (query.get("limit") or ["12"])[0]
    return {
        "from": start,
        "to": end,
        "users": traffic_store.top_users(start, end, limit),
    }


def nodes(query):
    start, end = window_from_query(query)
    names = {node.get("id", ""): node.get("name", "") for node in node_catalog.list_public_nodes(admin=True)}
    rows = traffic_store.by_node(start, end)
    for row in rows:
        row["name"] = names.get(row.get("node_id", ""), row.get("node_id", "") or row.get("source", ""))
    return {"from": start, "to": end, "nodes": rows}


def plans():
    distribution = overview()["plans"]
    return {
        "plans": [
            {"name": name, "users": count}
            for name, count in sorted(distribution.items(), key=lambda item: (-item[1], item[0]))
        ]
    }
