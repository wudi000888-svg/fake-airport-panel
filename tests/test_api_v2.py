import importlib
import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


MODULES = [
    "panel_config",
    "json_store",
    "auth_store",
    "user_store",
    "node_catalog",
    "plans_store",
    "orders_store",
    "payments_store",
    "payment_rates",
    "payment_wallets",
    "payment_verifier",
    "payment_service",
    "registration_store",
    "admin_profile",
    "audit_log",
    "backup_manager",
    "subscription_guard",
    "app_urls",
    "link_settings",
    "operations_service",
    "dashboard_service",
    "api_common",
    "api_payment_routes",
    "api_v2_routes",
    "api_get_routes",
    "api_post_routes",
    "api",
    "traffic_store",
]


@pytest.fixture()
def v2_modules(tmp_path, monkeypatch):
    panel_dir = tmp_path / "panel"
    panel_dir.mkdir()
    monkeypatch.setenv("PANEL_DIR", str(panel_dir))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test")
    for name in MODULES:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    user_store = sys.modules["user_store"]
    user_store.save_users(
        {
            "version": 1,
            "users": {
                "alice": {
                    "enabled": True,
                    "sub_token": "tok_alice",
                    "quota_bytes": 100,
                    "used_bytes": 20,
                    "node_groups": ["default"],
                }
            },
        }
    )
    return {name: sys.modules[name] for name in MODULES}


def test_api_app_shell_and_me(v2_modules):
    api = v2_modules["api"]

    status, payload = api.handle_get("/api/app-shell", {"u": "alice", "r": "user", "role": "user"})
    assert status == 200
    assert payload["role"] == "user"
    assert [item["id"] for item in payload["nav"]] == [
        "dashboard",
        "plans",
        "links",
        "orders",
        "account",
    ]

    status, payload = api.handle_get("/api/me", {"u": "alice", "r": "user", "role": "user"})
    assert status == 200
    assert payload["username"] == "alice"
    assert payload["subscription_url"] == "https://example.test/sub/tok_alice"


def test_api_v2_cache_status_and_clear_are_admin_only(v2_modules):
    api = v2_modules["api"]
    cache_store = v2_modules["api_v2_routes"].cache_store
    cache_store.app_cache.get("dashboard", "admin", ttl=30, loader=lambda: {"ok": True})

    status, payload = api.handle_get("/api/cache/status", {"u": "admin", "r": "admin", "role": "admin"})
    assert status == 200
    assert payload["cache"]["items"] == 1

    status, payload = api.handle_post("/api/cache/clear", {}, {"u": "alice", "r": "user", "role": "user"})
    assert status == 403

    status, payload = api.handle_post("/api/cache/clear", {}, {"u": "admin", "r": "admin", "role": "admin"})
    assert status == 200
    assert payload["cache"]["items"] == 0


def test_admin_dashboard_survives_subscription_link_generation_failure(v2_modules, monkeypatch):
    api = v2_modules["api"]
    links = importlib.import_module("links")
    xray_panel = importlib.import_module("xray_panel")
    hy2_panel = importlib.import_module("hy2_panel")

    monkeypatch.setattr(
        links,
        "build_vless_links_for_airport_user",
        lambda username, user: (_ for _ in ()).throw(FileNotFoundError("xray")),
    )
    monkeypatch.setattr(xray_panel, "current_status", lambda: {"xray": "test", "proxy": ""})
    monkeypatch.setattr(hy2_panel, "hy2_status", lambda: {"running": "test"})

    status, payload = api.handle_get("/api/dashboard", {"u": "admin", "r": "admin", "role": "admin"})

    assert status == 200
    assert "data" in payload
    assert payload["data"]["links"]["error"] == "xray"
    assert "users" in payload["data"]


def test_admin_metrics_api_returns_operational_dashboard_data(v2_modules):
    api = v2_modules["api"]
    plans_store = v2_modules["plans_store"]
    user_store = v2_modules["user_store"]
    traffic_store = v2_modules["traffic_store"]

    plans_store.upsert_plan({"id": "starter", "name": "Starter", "days": 30, "traffic_gb": 50, "price": "9", "enabled": True})
    users = user_store.load_users()
    users["users"]["alice"].update({"plan_id": "starter", "quota_bytes": 1000, "used_bytes": 200})
    users["users"]["bob"] = {"enabled": True, "sub_token": "tok_bob", "plan_id": "", "quota_bytes": 0, "used_bytes": 0}
    user_store.save_users(users)

    traffic_store.add_sample(
        {
            "username": "alice",
            "source": "xray",
            "node_id": "vless-main",
            "uplink_bytes": 100,
            "downlink_bytes": 900,
            "sampled_at": "2026-06-09T00:10:00+00:00",
        }
    )
    traffic_store.add_sample(
        {
            "username": "bob",
            "source": "hy2",
            "node_id": "hy2-main",
            "uplink_bytes": 50,
            "downlink_bytes": 150,
            "sampled_at": "2026-06-09T01:20:00+00:00",
        }
    )

    session = {"u": "admin", "r": "admin", "role": "admin"}
    status, payload = api.handle_get("/api/admin/metrics/overview", session)
    assert status == 200
    assert payload["metrics"]["users_total"] == 2
    assert payload["metrics"]["users_enabled"] == 2
    assert payload["metrics"]["traffic_total_bytes"] == 1200
    assert payload["metrics"]["plans"]["Starter"] == 1
    assert payload["metrics"]["plans"]["无套餐"] == 1

    window = "from=2026-06-09T00:00:00%2B00:00&to=2026-06-09T02:00:00%2B00:00"
    status, payload = api.handle_get(f"/api/admin/metrics/traffic?{window}&granularity=hour", session)
    assert status == 200
    assert payload["traffic"]["series"] == [
        {"bucket": "2026-06-09T00:00:00+00:00", "uplink_bytes": 100, "downlink_bytes": 900, "total_bytes": 1000},
        {"bucket": "2026-06-09T01:00:00+00:00", "uplink_bytes": 50, "downlink_bytes": 150, "total_bytes": 200},
    ]

    status, payload = api.handle_get(
        "/api/admin/metrics/traffic?from=2026-06-09T00:00:00%2B00:00&to=2026-06-09T03:00:00%2B00:00&granularity=hour",
        session,
    )
    assert status == 200
    assert payload["traffic"]["series"] == [
        {"bucket": "2026-06-09T00:00:00+00:00", "uplink_bytes": 100, "downlink_bytes": 900, "total_bytes": 1000},
        {"bucket": "2026-06-09T01:00:00+00:00", "uplink_bytes": 50, "downlink_bytes": 150, "total_bytes": 200},
        {"bucket": "2026-06-09T02:00:00+00:00", "uplink_bytes": 0, "downlink_bytes": 0, "total_bytes": 0},
    ]

    status, payload = api.handle_get(
        "/api/admin/metrics/traffic?from=2026-06-09T00:30:00%2B00:00&to=2026-06-09T01:30:00%2B00:00&granularity=hour",
        session,
    )
    assert status == 200
    assert payload["traffic"]["series"] == [
        {"bucket": "2026-06-09T00:00:00+00:00", "uplink_bytes": 0, "downlink_bytes": 0, "total_bytes": 0},
        {"bucket": "2026-06-09T01:00:00+00:00", "uplink_bytes": 50, "downlink_bytes": 150, "total_bytes": 200},
    ]

    status, payload = api.handle_get(
        "/api/admin/metrics/traffic?from=2026-06-09T01:00:00%2B00:00&to=2026-06-11T01:00:00%2B00:00&granularity=day",
        session,
    )
    assert status == 200
    assert payload["traffic"]["series"] == [
        {"bucket": "2026-06-09T00:00:00+00:00", "uplink_bytes": 50, "downlink_bytes": 150, "total_bytes": 200},
        {"bucket": "2026-06-10T00:00:00+00:00", "uplink_bytes": 0, "downlink_bytes": 0, "total_bytes": 0},
        {"bucket": "2026-06-11T00:00:00+00:00", "uplink_bytes": 0, "downlink_bytes": 0, "total_bytes": 0},
    ]

    status, payload = api.handle_get(f"/api/admin/metrics/users/top?{window}&limit=1", session)
    assert status == 200
    assert payload["users"][0]["username"] == "alice"
    assert payload["users"][0]["total_bytes"] == 1000

    status, payload = api.handle_get(f"/api/admin/metrics/nodes?{window}", session)
    assert status == 200
    assert {item["node_id"] for item in payload["nodes"]} == {"vless-main", "hy2-main"}

    status, payload = api.handle_get("/api/admin/metrics/plans", session)
    assert status == 200
    assert payload["plans"][0]["name"] in {"Starter", "无套餐"}


def test_admin_metrics_api_is_admin_only(v2_modules):
    api = v2_modules["api"]

    status, _ = api.handle_get("/api/admin/metrics/overview", {"u": "alice", "r": "user", "role": "user"})
    assert status == 403
