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
        "settings",
    }.issubset(tables)


def test_json_to_sqlite_imports_plans_and_orders(tmp_path, monkeypatch):
    import importlib.util
    import json

    import panel_config

    monkeypatch.setattr(panel_config, "PANEL_DIR", tmp_path)

    (tmp_path / "plans.json").write_text(
        json.dumps(
            {
                "version": 1,
                "plans": [
                    {
                        "id": "pro",
                        "name": "Pro",
                        "days": 30,
                        "traffic_gb": 100,
                        "price": "9.9",
                        "enabled": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "orders.json").write_text(
        json.dumps(
            {
                "version": 1,
                "orders": [
                    {
                        "id": "ord_1",
                        "username": "alice",
                        "kind": "renew",
                        "plan_id": "pro",
                        "amount": "9.9",
                        "status": "pending",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "payments.json").write_text(
        json.dumps(
            {
                "version": 1,
                "methods": [
                    {
                        "id": "usdt-bsc",
                        "asset": "USDT",
                        "chain": "bsc",
                        "address": "0x2222222222222222222222222222222222222222",
                        "enabled": True,
                    }
                ],
                "payments": [
                    {
                        "id": "pay_1",
                        "order_id": "ord_1",
                        "username": "alice",
                        "status": "confirmed",
                        "asset": "USDT",
                        "chain": "bsc",
                        "txid": "0xabc",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
                "rates": {"overrides": {"ETH": "3000"}, "cache": {"BTC": {"rate_usd": "90000"}}},
            }
        ),
        encoding="utf-8",
    )

    script = ROOT / "scripts" / "migrate-json-to-sqlite.py"
    spec = importlib.util.spec_from_file_location("migrate_json_to_sqlite", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "fake-ui.db"
    mod.migrate_json_to_sqlite(tmp_path, db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("select name from plans where id='pro'").fetchone()[0] == "Pro"
        assert conn.execute("select username from orders where id='ord_1'").fetchone()[0] == "alice"
        assert conn.execute("select asset from payment_methods where id='usdt-bsc'").fetchone()[0] == "USDT"
        assert conn.execute("select txid from payments where id='pay_1'").fetchone()[0] == "0xabc"
        assert conn.execute("select value_json from settings where key='payment_rates'").fetchone()[0]


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


def test_store_facade_switches_plans_and_orders_to_sqlite(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("PANEL_DIR", str(tmp_path))
    monkeypatch.setenv("FAKE_UI_STORE", "sqlite")

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


def test_store_facade_switches_payments_to_sqlite(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("PANEL_DIR", str(tmp_path))
    monkeypatch.setenv("FAKE_UI_STORE", "sqlite")

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


def test_export_sqlite_to_json_writes_plans_and_orders(tmp_path):
    import importlib.util
    import json

    import db_schema
    from repositories.sqlite_orders import SQLiteOrdersRepository
    from repositories.sqlite_payments import SQLitePaymentMethodsRepository, SQLitePaymentsRepository, SQLiteSettingsRepository
    from repositories.sqlite_plans import SQLitePlansRepository

    db_path = tmp_path / "fake-ui.db"
    export_dir = tmp_path / "export"
    db_schema.migrate(db_path)
    SQLitePlansRepository(db_path).upsert({"id": "pro", "name": "Pro", "days": 30, "traffic_gb": 100, "price": "9"})
    SQLiteOrdersRepository(db_path).upsert({"id": "ord_1", "username": "alice", "status": "pending", "created_at": "2026-01-01T00:00:00+00:00"})
    SQLitePaymentMethodsRepository(db_path).upsert({"id": "usdt-bsc", "asset": "USDT", "chain": "bsc", "address": "0x2222222222222222222222222222222222222222", "enabled": True})
    SQLitePaymentsRepository(db_path).upsert({"id": "pay_1", "order_id": "ord_1", "username": "alice", "status": "confirmed", "asset": "USDT", "chain": "bsc", "txid": "0xabc", "created_at": "2026-01-01T00:00:00+00:00"})
    SQLiteSettingsRepository(db_path).set("payment_rates", {"overrides": {"ETH": "3000"}, "cache": {}})

    script = ROOT / "scripts" / "export-sqlite-to-json.py"
    spec = importlib.util.spec_from_file_location("export_sqlite_to_json", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.export_sqlite_to_json(db_path, export_dir)

    plans = json.loads((export_dir / "plans.json").read_text(encoding="utf-8"))
    orders = json.loads((export_dir / "orders.json").read_text(encoding="utf-8"))
    payments = json.loads((export_dir / "payments.json").read_text(encoding="utf-8"))
    assert plans["plans"][0]["id"] == "pro"
    assert orders["orders"][0]["id"] == "ord_1"
    assert payments["methods"][0]["id"] == "usdt-bsc"
    assert payments["payments"][0]["txid"] == "0xabc"
    assert payments["rates"]["overrides"]["ETH"] == "3000"
