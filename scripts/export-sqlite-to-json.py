#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))

from repositories.sqlite_orders import SQLiteOrdersRepository
from repositories.sqlite_payments import SQLitePaymentMethodsRepository, SQLitePaymentsRepository, SQLiteSettingsRepository
from repositories.sqlite_plans import SQLitePlansRepository


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_sqlite_to_json(db_path, data_dir):
    db_path = Path(db_path)
    data_dir = Path(data_dir)
    plans = SQLitePlansRepository(db_path).list(include_disabled=True)
    orders = SQLiteOrdersRepository(db_path).list(limit=100000)
    methods = SQLitePaymentMethodsRepository(db_path).list(include_disabled=True)
    payments = SQLitePaymentsRepository(db_path).list(limit=100000)
    rates = SQLiteSettingsRepository(db_path).get("payment_rates", {"overrides": {}, "cache": {}})
    write_json(data_dir / "plans.json", {"version": 1, "plans": plans})
    write_json(data_dir / "orders.json", {"version": 1, "orders": orders})
    write_json(data_dir / "payments.json", {"version": 1, "methods": methods, "payments": payments, "rates": rates})


def main():
    parser = argparse.ArgumentParser(description="Export fake-ui SQLite data back to JSON files.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    export_sqlite_to_json(Path(args.db), Path(args.data_dir))


if __name__ == "__main__":
    main()
