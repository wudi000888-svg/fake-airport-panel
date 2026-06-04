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

    script = ROOT / "scripts" / "migrate-json-to-sqlite.py"
    spec = importlib.util.spec_from_file_location("migrate_json_to_sqlite", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "fake-ui.db"
    mod.migrate_json_to_sqlite(tmp_path, db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("select name from plans where id='pro'").fetchone()[0] == "Pro"
        assert conn.execute("select username from orders where id='ord_1'").fetchone()[0] == "alice"


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
