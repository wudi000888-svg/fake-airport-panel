import secrets
from copy import deepcopy
from datetime import datetime, timezone

import payment_wallets
import store_facade
from repositories.sqlite_payments import SQLitePaymentMethodsRepository, SQLitePaymentsRepository
from repositories.sqlite_settings import SQLiteSettingsRepository


PUBLIC_METHOD_FIELDS = {
    "id",
    "label",
    "asset",
    "chain",
    "address",
    "decimals",
    "confirmations_required",
    "enabled",
    "sort",
    "created_at",
    "updated_at",
}
SECRET_PAYMENT_FIELDS = {"internal_note"}
DEFAULT_PAYMENT_STATUS = "awaiting_payment"


def default_payments():
    return {
        "version": 1,
        "methods": [],
        "payments": [],
        "rates": {"overrides": {}, "cache": {}},
    }


def _ensure_shape(data):
    if not isinstance(data, dict):
        data = default_payments()
    data.setdefault("version", 1)
    data.setdefault("methods", [])
    data.setdefault("payments", [])
    data.setdefault("rates", {"overrides": {}, "cache": {}})
    data["rates"].setdefault("overrides", {})
    data["rates"].setdefault("cache", {})
    return data


def public_method(method, admin=False):
    view = deepcopy(method)
    if not admin:
        view = {k: v for k, v in view.items() if k in PUBLIC_METHOD_FIELDS}
    return view


def public_payment(payment, admin=False):
    view = deepcopy(payment)
    if not admin:
        view = {k: v for k, v in view.items() if k not in SECRET_PAYMENT_FIELDS}
    return view


def _new_payment_id():
    return f"pay_{secrets.token_urlsafe(12)}"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_payments():
    store_facade.ensure_sqlite()
    return {
        "version": 2,
        "methods": SQLitePaymentMethodsRepository().list(include_disabled=True),
        "payments": SQLitePaymentsRepository().list(limit=100000),
        "rates": SQLiteSettingsRepository().get("payment_rates", {"overrides": {}, "cache": {}}),
    }


def save_payments(data):
    store_facade.ensure_sqlite()
    shaped = _ensure_shape(data)
    methods_repo = SQLitePaymentMethodsRepository()
    payments_repo = SQLitePaymentsRepository()
    settings_repo = SQLiteSettingsRepository()
    for method in shaped.get("methods", []):
        methods_repo.upsert(method)
    for payment in shaped.get("payments", []):
        payments_repo.upsert(payment)
    settings_repo.set("payment_rates", shaped.get("rates", {"overrides": {}, "cache": {}}))
    return shaped


def list_methods(admin=False):
    store_facade.ensure_sqlite()
    methods = SQLitePaymentMethodsRepository().list(include_disabled=admin)
    return [public_method(method, admin=admin) for method in methods]


def get_method(method_id):
    store_facade.ensure_sqlite()
    method = SQLitePaymentMethodsRepository().get(method_id)
    return deepcopy(method)


def upsert_method(method):
    store_facade.ensure_sqlite()
    repo = SQLitePaymentMethodsRepository()
    item = payment_wallets.normalize_method(method)
    existing = repo.get(item["id"])
    if existing and existing.get("created_at"):
        item["created_at"] = existing["created_at"]
    else:
        item.setdefault("created_at", _now_iso())
    item["updated_at"] = _now_iso()
    return deepcopy(repo.upsert(item))


def set_method_enabled(method_id, enabled):
    store_facade.ensure_sqlite()
    return deepcopy(SQLitePaymentMethodsRepository().set_enabled(method_id, enabled))


def delete_method(method_id):
    store_facade.ensure_sqlite()
    return SQLitePaymentMethodsRepository().delete(method_id)


def list_payments(username=None, admin=False, limit=200):
    if not admin and username is None:
        return []
    store_facade.ensure_sqlite()
    payments = SQLitePaymentsRepository().list(username=username, limit=limit)
    return [public_payment(payment, admin=admin) for payment in payments]


def get_payment(payment_id):
    store_facade.ensure_sqlite()
    payment = SQLitePaymentsRepository().get(payment_id)
    return deepcopy(payment) if payment else None


def txid_used(txid, exclude_payment_id=None):
    normalized = str(txid or "").strip().lower()
    if not normalized:
        return False
    store_facade.ensure_sqlite()
    return SQLitePaymentsRepository().txid_used(normalized, exclude_payment_id=exclude_payment_id)


def create_payment(payment):
    store_facade.ensure_sqlite()
    repo = SQLitePaymentsRepository()
    item = dict(payment)
    item.setdefault("id", _new_payment_id())
    while repo.get(item["id"]):
        item["id"] = _new_payment_id()
    item.setdefault("status", DEFAULT_PAYMENT_STATUS)
    item.setdefault("created_at", _now_iso())
    item.setdefault("updated_at", item["created_at"])
    return deepcopy(repo.upsert(item))


def update_payment(payment_id, **updates):
    if "txid" in updates:
        normalized_txid = str(updates.get("txid") or "").strip()
        if not normalized_txid:
            raise RuntimeError("txid required")
        if txid_used(normalized_txid, exclude_payment_id=payment_id):
            raise RuntimeError("txid already used")
        updates["txid"] = normalized_txid

    store_facade.ensure_sqlite()
    updates["updated_at"] = _now_iso()
    return deepcopy(SQLitePaymentsRepository().update(payment_id, **updates))


def attach_txid(payment_id, txid):
    normalized = str(txid or "").strip()
    if not normalized:
        raise RuntimeError("txid required")
    if txid_used(normalized, exclude_payment_id=payment_id):
        raise RuntimeError("txid already used")
    return update_payment(payment_id, txid=normalized)


def load_rates():
    store_facade.ensure_sqlite()
    rates = SQLiteSettingsRepository().get("payment_rates", {"overrides": {}, "cache": {}})
    return deepcopy(_ensure_shape({"rates": rates})["rates"])


def save_rates(rates):
    store_facade.ensure_sqlite()
    data = _ensure_shape({"rates": dict(rates or {})})
    SQLiteSettingsRepository().set("payment_rates", data["rates"])
    return deepcopy(data["rates"])
