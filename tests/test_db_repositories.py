import sqlite3
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


def test_db_schema_creates_required_tables(tmp_path, monkeypatch):
    import panel_config

    monkeypatch.setattr(panel_config, "PANEL_DIR", tmp_path)

    import db_schema

    db_path = tmp_path / "fake-ui.db"
    db_schema.migrate(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type='table'")
        }
        versions = {
            row[0]
            for row in conn.execute("select version from schema_migrations")
        }

    assert {
        "schema_migrations",
        "users",
        "plans",
        "orders",
        "payment_methods",
        "payments",
        "nodes",
        "registrations",
        "password_resets",
        "audit_logs",
        "subscription_access",
        "traffic_samples",
        "settings",
    }.issubset(tables)
    assert 2 in versions


def test_legacy_json_migration_tools_are_removed():
    assert not (ROOT / "scripts" / "migrate-json-to-sqlite.py").exists()
    assert not (ROOT / "scripts" / "export-sqlite-to-json.py").exists()


def test_business_backup_manifest_is_sqlite_only():
    import backup_manager

    assert "fake-ui.db" in backup_manager.BACKUP_FILES
    for legacy_name in [
        "plans.json",
        "orders.json",
        "payments.json",
        "users.json",
        "nodes.json",
        "registrations.json",
        "admin_profile.json",
        "link_settings.json",
    ]:
        assert legacy_name not in backup_manager.BACKUP_FILES


def test_sqlite_repositories_preserve_plan_and_order_listing(tmp_path):
    import db_schema
    from repositories.sqlite_orders import SQLiteOrdersRepository
    from repositories.sqlite_plans import SQLitePlansRepository

    db_path = tmp_path / "fake-ui.db"
    db_schema.migrate(db_path)

    plans = SQLitePlansRepository(db_path)
    orders = SQLiteOrdersRepository(db_path)
    plans.upsert(
        {
            "id": "team",
            "name": "Team",
            "days": 90,
            "traffic_gb": 500,
            "price": "29.9",
            "enabled": True,
            "sort": 20,
        }
    )
    plans.upsert(
        {
            "id": "hidden",
            "name": "Hidden",
            "days": 30,
            "traffic_gb": 100,
            "price": "5",
            "enabled": False,
            "sort": 10,
        }
    )
    orders.upsert(
        {
            "id": "ord_new",
            "username": "alice",
            "kind": "renew",
            "plan_id": "team",
            "amount": "29.9",
            "status": "pending",
            "created_at": "2026-01-02T00:00:00+00:00",
        }
    )
    orders.upsert(
        {
            "id": "ord_old",
            "username": "bob",
            "kind": "new",
            "plan_id": "team",
            "amount": "29.9",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )

    assert [plan["id"] for plan in plans.list(include_disabled=False)] == ["team"]
    assert orders.list(username="alice", limit=10)[0]["id"] == "ord_new"
    assert [order["id"] for order in orders.list(limit=2)] == ["ord_new", "ord_old"]


def test_sqlite_repositories_preserve_users_nodes_registrations_and_settings(tmp_path):
    import db_schema
    from repositories.sqlite_nodes import SQLiteNodesRepository
    from repositories.sqlite_registrations import SQLitePasswordResetsRepository, SQLiteRegistrationsRepository
    from repositories.sqlite_settings import SQLiteSettingsRepository
    from repositories.sqlite_users import SQLiteUsersRepository

    db_path = tmp_path / "fake-ui.db"
    db_schema.migrate(db_path)

    users = SQLiteUsersRepository(db_path)
    nodes = SQLiteNodesRepository(db_path)
    registrations = SQLiteRegistrationsRepository(db_path)
    resets = SQLitePasswordResetsRepository(db_path)
    settings = SQLiteSettingsRepository(db_path)

    users.upsert(
        {
            "username": "alice",
            "enabled": True,
            "plan_id": "standard",
            "expires_at": "2026-07-01T00:00:00+00:00",
            "sub_token": "sub_alice",
        }
    )
    users.upsert(
        {
            "username": "bob",
            "enabled": False,
            "plan_id": "starter",
            "expires_at": "",
            "sub_token": "sub_bob",
        }
    )
    nodes.upsert({"id": "vless-main", "kind": "vless", "enabled": True, "sort": 10, "name": "VLESS"})
    nodes.upsert({"id": "hy2-main", "kind": "hy2", "enabled": True, "sort": 20, "name": "Hysteria2"})
    registrations.upsert({"token": "reg_1", "username": "alice", "status": "pending", "created_at": "2026-01-01T00:00:00+00:00"})
    resets.upsert({"token": "rst_1", "username": "alice", "status": "pending", "created_at": "2026-01-02T00:00:00+00:00"})
    settings.set("link_settings", {"vless_address": "vless.example.com", "hy2_name": "H2"})

    assert users.get("alice")["plan_id"] == "standard"
    assert [user["username"] for user in users.list()] == ["alice", "bob"]
    assert [node["id"] for node in nodes.list()] == ["vless-main", "hy2-main"]
    assert nodes.list(kind="vless")[0]["name"] == "VLESS"
    assert registrations.get("reg_1")["username"] == "alice"
    assert resets.get("rst_1")["status"] == "pending"
    assert settings.get("link_settings")["hy2_name"] == "H2"


def test_sqlite_traffic_repository_records_and_aggregates_samples(tmp_path):
    import db_schema
    from repositories.sqlite_traffic import SQLiteTrafficRepository

    db_path = tmp_path / "fake-ui.db"
    db_schema.migrate(db_path)

    traffic = SQLiteTrafficRepository(db_path)
    traffic.add_sample(
        {
            "username": "alice",
            "source": "xray",
            "node_id": "vless-main",
            "uplink_bytes": 100,
            "downlink_bytes": 400,
            "sampled_at": "2026-06-09T00:10:00+00:00",
        }
    )
    traffic.add_sample(
        {
            "username": "alice",
            "source": "hy2",
            "node_id": "hy2-main",
            "uplink_bytes": 200,
            "downlink_bytes": 800,
            "sampled_at": "2026-06-09T00:40:00+00:00",
        }
    )
    traffic.add_sample(
        {
            "username": "bob",
            "source": "xray",
            "node_id": "vless-main",
            "uplink_bytes": 50,
            "downlink_bytes": 150,
            "sampled_at": "2026-06-09T01:05:00+00:00",
        }
    )

    series = traffic.series("2026-06-09T00:00:00+00:00", "2026-06-09T02:00:00+00:00", "hour")
    assert series == [
        {"bucket": "2026-06-09T00:00:00+00:00", "uplink_bytes": 300, "downlink_bytes": 1200, "total_bytes": 1500},
        {"bucket": "2026-06-09T01:00:00+00:00", "uplink_bytes": 50, "downlink_bytes": 150, "total_bytes": 200},
    ]

    assert traffic.top_users("2026-06-09T00:00:00+00:00", "2026-06-09T02:00:00+00:00", 2) == [
        {"username": "alice", "uplink_bytes": 300, "downlink_bytes": 1200, "total_bytes": 1500},
        {"username": "bob", "uplink_bytes": 50, "downlink_bytes": 150, "total_bytes": 200},
    ]
    assert traffic.by_node("2026-06-09T00:00:00+00:00", "2026-06-09T02:00:00+00:00") == [
        {"node_id": "hy2-main", "source": "hy2", "uplink_bytes": 200, "downlink_bytes": 800, "total_bytes": 1000},
        {"node_id": "vless-main", "source": "xray", "uplink_bytes": 150, "downlink_bytes": 550, "total_bytes": 700},
    ]


def test_sqlite_traffic_repository_deletes_samples_before_cutoff(tmp_path):
    import db_schema
    from repositories.sqlite_traffic import SQLiteTrafficRepository

    db_path = tmp_path / "fake-ui.db"
    db_schema.migrate(db_path)

    traffic = SQLiteTrafficRepository(db_path)
    for sampled_at in [
        "2026-06-01T00:00:00+00:00",
        "2026-06-10T00:00:00+00:00",
        "2026-06-11T00:00:00+00:00",
    ]:
        traffic.add_sample(
            {
                "username": "alice",
                "source": "xray",
                "node_id": "vless-main",
                "uplink_bytes": 10,
                "downlink_bytes": 20,
                "sampled_at": sampled_at,
            }
        )

    assert traffic.delete_before("2026-06-10T00:00:00+00:00") == 1
    assert traffic.top_users("2026-06-01T00:00:00+00:00", "2026-06-12T00:00:00+00:00", 10) == [
        {"username": "alice", "uplink_bytes": 20, "downlink_bytes": 40, "total_bytes": 60},
    ]


def test_plans_and_orders_use_sqlite_runtime(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("PANEL_DIR", str(tmp_path))

    for name in ["panel_config", "db", "db_schema", "plans_store", "orders_store"]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)

    plans_store = sys.modules["plans_store"]
    orders_store = sys.modules["orders_store"]

    plan = plans_store.upsert_plan(
        {
            "id": "sqlite-plan",
            "name": "SQLite Plan",
            "days": 30,
            "traffic_gb": 200,
            "price": "12.5",
            "enabled": True,
        }
    )
    order = orders_store.create_pending_order("alice", "renew", plan, note="sqlite")

    assert plans_store.get_plan("sqlite-plan")["name"] == "SQLite Plan"
    assert orders_store.get_order(order["id"])["username"] == "alice"
    assert (tmp_path / "fake-ui.db").exists()


def test_payments_use_sqlite_runtime(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("PANEL_DIR", str(tmp_path))

    for name in ["panel_config", "db", "db_schema", "payments_store"]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)

    payments_store = sys.modules["payments_store"]

    method = payments_store.upsert_method(
        {
            "id": "usdt-bsc",
            "asset": "USDT",
            "chain": "bsc",
            "address": "0x2222222222222222222222222222222222222222",
            "enabled": True,
        }
    )
    payment = payments_store.create_payment(
        {
            "order_id": "ord_sqlite",
            "username": "alice",
            "method_id": method["id"],
            "asset": "USDT",
            "chain": "bsc",
            "usd_amount": "10.00",
            "crypto_amount": "10.000000000000000000",
            "rate_usd": "1",
            "address": method["address"],
            "qr_payload": method["address"],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    payments_store.attach_txid(payment["id"], "0xabc")
    payments_store.save_rates({"overrides": {"ETH": "3000"}, "cache": {"BTC": {"rate_usd": "90000"}}})

    assert payments_store.get_method("usdt-bsc")["asset"] == "USDT"
    assert payments_store.get_payment(payment["id"])["txid"] == "0xabc"
    assert payments_store.txid_used("0XABC") is True
    assert payments_store.load_rates()["overrides"]["ETH"] == "3000"
    assert not (tmp_path / "payments.json").exists()

    with sqlite3.connect(tmp_path / "fake-ui.db") as conn:
        assert conn.execute("select count(*) from payment_methods").fetchone()[0] == 1
        assert conn.execute("select count(*) from payments").fetchone()[0] == 1
        assert conn.execute("select value_json from settings where key='payment_rates'").fetchone()[0]


def test_database_path_uses_fake_ui_db_env(tmp_path, monkeypatch):
    import importlib

    custom_db = tmp_path / "custom" / "fake-ui.sqlite"
    monkeypatch.setenv("FAKE_UI_DB", str(custom_db))

    if "db" in sys.modules:
        importlib.reload(sys.modules["db"])
    else:
        importlib.import_module("db")

    db = sys.modules["db"]
    assert db.database_path() == custom_db


def test_business_stores_are_sqlite_only_by_default(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("PANEL_DIR", str(tmp_path))

    modules = [
        "panel_config",
        "db",
        "db_schema",
        "store_facade",
        "plans_store",
        "orders_store",
        "payments_store",
        "user_store",
        "node_catalog",
        "registration_store",
        "admin_profile",
        "link_settings",
    ]
    for name in modules:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)

    plans_store = sys.modules["plans_store"]
    orders_store = sys.modules["orders_store"]
    payments_store = sys.modules["payments_store"]
    user_store = sys.modules["user_store"]
    node_catalog = sys.modules["node_catalog"]
    registration_store = sys.modules["registration_store"]
    admin_profile = sys.modules["admin_profile"]
    link_settings = sys.modules["link_settings"]

    plan = plans_store.upsert_plan({"id": "sqlite-only", "name": "SQLite Only", "days": 30, "traffic_gb": 100, "price": "10"})
    order = orders_store.create_pending_order("alice", "new", plan)
    method = payments_store.upsert_method({"id": "usdt-bsc", "asset": "USDT", "chain": "bsc", "address": "0x2222222222222222222222222222222222222222"})
    payment = payments_store.create_payment({"order_id": order["id"], "username": "alice", "method_id": method["id"], "asset": "USDT", "chain": "bsc"})
    users = user_store.load_users()
    users["users"]["alice"] = {"enabled": True, "sub_token": "sub_alice", "panel_password": {}}
    user_store.save_users(users)
    node_catalog.upsert_node({"id": "vless-test", "name": "VLESS Test", "kind": "vless", "enabled": True})
    registration_store.create_password_reset("alice")
    admin = admin_profile.get_admin_user()
    links = link_settings.read()

    assert plans_store.get_plan("sqlite-only")["name"] == "SQLite Only"
    assert orders_store.get_order(order["id"])["username"] == "alice"
    assert payments_store.get_payment(payment["id"])["order_id"] == order["id"]
    assert user_store.get_user("alice")["sub_token"] == "sub_alice"
    assert node_catalog.get_node("vless-test")["name"] == "VLESS Test"
    assert registration_store.list_resets()[0]["username"] == "alice"
    assert admin["role"] == "admin"
    assert links["vless_address"]
    assert (tmp_path / "fake-ui.db").exists()
    for legacy_name in [
        "plans.json",
        "orders.json",
        "payments.json",
        "users.json",
        "nodes.json",
        "registrations.json",
        "admin_profile.json",
        "link_settings.json",
    ]:
        assert not (tmp_path / legacy_name).exists(), legacy_name
