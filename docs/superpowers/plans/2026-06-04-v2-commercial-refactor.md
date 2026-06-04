# v2.0.0 Commercial Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build v2.0.0 as a mobile-first, database-backed, cached, commercial-grade fake-ui while preserving single-VPS multi-exit orchestration.

**Architecture:** Keep the Python HTTP backend and static frontend deployment model, but split the frontend into ES modules, add SQLite repositories behind current service APIs, introduce TTL caches, and deploy destructively only to the Singapore test server with explicit reset flags. Hong Kong production is excluded.

**Tech Stack:** Python 3.12 standard library, SQLite (`sqlite3`), native ES modules, CSS tokens/components/pages, Docker Compose, pytest, in-app browser verification.

---

## File Structure

| Path | Responsibility |
|---|---|
| `baseline/db.py` | SQLite connection, row helpers, transaction context, database path resolution. |
| `baseline/db_schema.py` | Schema DDL and migration runner. |
| `baseline/repositories/` | SQLite repositories mirroring current store APIs. |
| `baseline/store_facade.py` | Switch between JSON and SQLite repositories during migration. |
| `baseline/cache_store.py` | Named TTL cache and invalidation helpers. |
| `baseline/api_v2_routes.py` | Resource-specific GET APIs for app shell, me, orders, payments, admin overview. |
| `baseline/frontend/assets/js/` | Modular v2 frontend source. |
| `baseline/frontend/assets/css/` | Split CSS tokens, layout, components, pages. |
| `scripts/migrate-json-to-sqlite.py` | JSON-to-SQLite import tool. |
| `scripts/export-sqlite-to-json.py` | SQLite-to-JSON export tool. |
| `scripts/reset-singapore-test-data.sh` | Explicit destructive reset helper for Singapore test only. |
| `tests/test_db_repositories.py` | DB schema/repository/migration tests. |
| `tests/test_cache_store.py` | TTL cache and invalidation tests. |
| `tests/test_api_v2.py` | New API endpoint tests. |
| `tests/test_frontend_v2_structure.py` | Frontend modularity and mobile UX source tests. |

---

## Task 1: Isolated v2 Worktree and Baseline

**Files:**
- Modify only if needed: `.gitignore`
- Worktree path: `.worktrees/v2-commercial-refactor`

- [ ] **Step 1: Detect worktree state**

```powershell
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git rev-parse --show-superproject-working-tree
```

Expected: normal checkout on `main`, no superproject.

- [ ] **Step 2: Ensure `.worktrees/` is ignored**

```powershell
git check-ignore -q .worktrees
if ($LASTEXITCODE -ne 0) {
  Add-Content -Path .gitignore -Value "`n.worktrees/"
  git add .gitignore
  git commit -m "chore: ignore local worktrees"
}
```

Expected: `.worktrees/` ignored before creating a project-local worktree.

- [ ] **Step 3: Create the v2 worktree**

```powershell
git worktree add .worktrees/v2-commercial-refactor -b v2-commercial-refactor
Set-Location .worktrees/v2-commercial-refactor
```

Expected: new branch `v2-commercial-refactor` checked out in isolated directory.

- [ ] **Step 4: Run baseline tests**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local.ps1
```

Expected: `73 passed`.

- [ ] **Step 5: Commit nothing**

```powershell
git status --short
```

Expected: clean worktree.

---

## Task 2: SQLite Core and Schema

**Files:**
- Create: `baseline/db.py`
- Create: `baseline/db_schema.py`
- Create: `tests/test_db_repositories.py`

- [ ] **Step 1: Write failing schema test**

Add to `tests/test_db_repositories.py`:

```python
import sqlite3


def test_db_schema_creates_required_tables(tmp_path, monkeypatch):
    import panel_config
    monkeypatch.setattr(panel_config, "PANEL_DIR", tmp_path)

    import db
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
```

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest tests/test_db_repositories.py::test_db_schema_creates_required_tables -q
```

Expected: FAIL because `db` or `db_schema` does not exist.

- [ ] **Step 3: Implement `baseline/db.py`**

```python
from contextlib import contextmanager
import sqlite3

from panel_config import PANEL_DIR


DB_FILE = PANEL_DIR / "fake-ui.db"


def connect(path=None):
    db_path = path or DB_FILE
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


@contextmanager
def transaction(path=None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_dict(row):
    return dict(row) if row is not None else None
```

- [ ] **Step 4: Implement `baseline/db_schema.py`**

Add DDL for all required tables. Use `text` for JSON-compatible fields and ISO timestamps, with indexes on common query keys:

```python
import db


SCHEMA_VERSION = 1

DDL = [
    """create table if not exists schema_migrations (
        version integer primary key,
        applied_at text not null
    )""",
    """create table if not exists users (
        username text primary key,
        password_hash text,
        role text not null default 'user',
        enabled integer not null default 1,
        plan_id text,
        quota_gb integer not null default 0,
        used_bytes integer not null default 0,
        expires_at text,
        sub_token text,
        note text,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create table if not exists plans (
        id text primary key,
        name text not null,
        days integer not null default 0,
        traffic_gb integer not null default 0,
        price text not null default '0',
        enabled integer not null default 1,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create table if not exists orders (
        id text primary key,
        username text not null,
        kind text not null,
        plan_id text,
        plan_name text,
        amount text not null default '0',
        days integer not null default 0,
        traffic_gb integer not null default 0,
        status text not null default 'pending',
        payment_status text,
        payment_id text,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create index if not exists idx_orders_username_created on orders(username, created_at desc)""",
    """create table if not exists payment_methods (
        id text primary key,
        asset text not null,
        chain text not null,
        address text not null,
        enabled integer not null default 1,
        sort integer not null default 100,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create table if not exists payments (
        id text primary key,
        order_id text not null,
        username text not null,
        method_id text not null,
        asset text not null,
        chain text not null,
        status text not null default 'awaiting_payment',
        crypto_amount text,
        usd_amount text,
        txid text,
        confirmations integer not null default 0,
        error text,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create index if not exists idx_payments_user_created on payments(username, created_at desc)""",
    """create table if not exists nodes (
        id text primary key,
        kind text not null,
        name text,
        enabled integer not null default 1,
        sort integer not null default 100,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create table if not exists registrations (
        id text primary key,
        username text,
        status text,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create table if not exists password_resets (
        id text primary key,
        username text,
        status text,
        raw_json text not null default '{}',
        created_at text,
        updated_at text
    )""",
    """create table if not exists audit_logs (
        id integer primary key autoincrement,
        actor text,
        action text,
        target text,
        detail text,
        created_at text
    )""",
    """create table if not exists subscription_access (
        id integer primary key autoincrement,
        username text,
        token text,
        path text,
        ip text,
        user_agent text,
        status text,
        created_at text
    )""",
    """create table if not exists settings (
        key text primary key,
        value text not null,
        updated_at text
    )""",
]


def migrate(path=None):
    with db.transaction(path) as conn:
        for statement in DDL:
            conn.execute(statement)
        conn.execute(
            "insert or ignore into schema_migrations(version, applied_at) values (?, datetime('now'))",
            (SCHEMA_VERSION,),
        )
```

- [ ] **Step 5: Run schema test**

```powershell
python -m pytest tests/test_db_repositories.py::test_db_schema_creates_required_tables -q
```

Expected: PASS.

- [ ] **Step 6: Run full tests**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local.ps1
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add baseline/db.py baseline/db_schema.py tests/test_db_repositories.py
git commit -m "feat: add sqlite schema core"
```

---

## Task 3: JSON Import and Repository Facade

**Files:**
- Create: `baseline/repositories/__init__.py`
- Create: `baseline/repositories/sqlite_base.py`
- Create: `baseline/repositories/sqlite_plans.py`
- Create: `baseline/repositories/sqlite_orders.py`
- Create: `scripts/migrate-json-to-sqlite.py`
- Modify: `tests/test_db_repositories.py`

- [ ] **Step 1: Add failing import test**

```python
def test_json_to_sqlite_imports_plans_and_orders(tmp_path, monkeypatch):
    import json
    import panel_config
    monkeypatch.setattr(panel_config, "PANEL_DIR", tmp_path)

    (tmp_path / "plans.json").write_text(json.dumps({
        "version": 1,
        "plans": [{"id": "pro", "name": "Pro", "days": 30, "traffic_gb": 100, "price": "9.9", "enabled": True}],
    }), encoding="utf-8")
    (tmp_path / "orders.json").write_text(json.dumps({
        "version": 1,
        "orders": [{"id": "ord_1", "username": "alice", "kind": "renew", "plan_id": "pro", "amount": "9.9", "status": "pending", "created_at": "2026-01-01T00:00:00+00:00"}],
    }), encoding="utf-8")

    import importlib.util
    script = Path(__file__).resolve().parents[1] / "scripts" / "migrate-json-to-sqlite.py"
    spec = importlib.util.spec_from_file_location("migrate_json_to_sqlite", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "fake-ui.db"
    mod.migrate_json_to_sqlite(tmp_path, db_path)

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("select name from plans where id='pro'").fetchone()[0] == "Pro"
        assert conn.execute("select username from orders where id='ord_1'").fetchone()[0] == "alice"
```

Add `from pathlib import Path` to the test file.

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest tests/test_db_repositories.py::test_json_to_sqlite_imports_plans_and_orders -q
```

Expected: FAIL because migration script does not exist.

- [ ] **Step 3: Implement migration helpers**

Create `scripts/migrate-json-to-sqlite.py` with:

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "baseline"))

import db_schema


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_raw(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def migrate_json_to_sqlite(data_dir, db_path):
    data_dir = Path(data_dir)
    db_schema.migrate(db_path)
    import db

    plans = read_json(data_dir / "plans.json", {"plans": []}).get("plans", [])
    orders = read_json(data_dir / "orders.json", {"orders": []}).get("orders", [])

    with db.transaction(db_path) as conn:
        for plan in plans:
            conn.execute(
                """insert or replace into plans
                (id, name, days, traffic_gb, price, enabled, raw_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan.get("id"),
                    plan.get("name", plan.get("id", "")),
                    int(plan.get("days", 0) or 0),
                    int(plan.get("traffic_gb", 0) or 0),
                    str(plan.get("price", plan.get("amount", "0"))),
                    1 if plan.get("enabled", True) else 0,
                    dump_raw(plan),
                    plan.get("created_at"),
                    plan.get("updated_at"),
                ),
            )
        for order in orders:
            conn.execute(
                """insert or replace into orders
                (id, username, kind, plan_id, plan_name, amount, days, traffic_gb, status, payment_status, payment_id, raw_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order.get("id"),
                    order.get("username", ""),
                    order.get("kind", "renew"),
                    order.get("plan_id", ""),
                    order.get("plan_name", ""),
                    str(order.get("amount", "0")),
                    int(order.get("days", 0) or 0),
                    int(order.get("traffic_gb", 0) or 0),
                    order.get("status", "pending"),
                    order.get("payment_status", ""),
                    order.get("payment_id", ""),
                    dump_raw(order),
                    order.get("created_at"),
                    order.get("updated_at"),
                ),
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    migrate_json_to_sqlite(Path(args.data_dir), Path(args.db))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run import test**

```powershell
python -m pytest tests/test_db_repositories.py::test_json_to_sqlite_imports_plans_and_orders -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts/migrate-json-to-sqlite.py tests/test_db_repositories.py
git commit -m "feat: import json data into sqlite"
```

---

## Task 4: Cache Store

**Files:**
- Create: `baseline/cache_store.py`
- Create: `tests/test_cache_store.py`

- [ ] **Step 1: Write failing cache tests**

```python
def test_ttl_cache_hits_expires_and_invalidates(monkeypatch):
    import cache_store

    now = {"value": 100.0}
    monkeypatch.setattr(cache_store.time, "monotonic", lambda: now["value"])

    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return {"value": calls["count"]}

    cache = cache_store.TTLCache()
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 1}
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 1}
    now["value"] = 111.0
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 2}
    cache.invalidate("dashboard")
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 3}
```

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest tests/test_cache_store.py -q
```

Expected: FAIL because `cache_store` does not exist.

- [ ] **Step 3: Implement `baseline/cache_store.py`**

```python
import time
from threading import RLock


class TTLCache:
    def __init__(self):
        self._items = {}
        self._lock = RLock()

    def get(self, namespace, key, ttl, loader):
        cache_key = (str(namespace), str(key))
        now = time.monotonic()
        with self._lock:
            item = self._items.get(cache_key)
            if item and item["expires_at"] > now:
                return item["value"]
        value = loader()
        with self._lock:
            self._items[cache_key] = {"value": value, "expires_at": now + float(ttl)}
        return value

    def invalidate(self, namespace=None):
        with self._lock:
            if namespace is None:
                self._items.clear()
                return
            prefix = str(namespace)
            for key in list(self._items):
                if key[0] == prefix:
                    self._items.pop(key, None)


cache = TTLCache()


def cached(namespace, key, ttl, loader):
    return cache.get(namespace, key, ttl, loader)


def invalidate(namespace=None):
    cache.invalidate(namespace)
```

- [ ] **Step 4: Run cache tests**

```powershell
python -m pytest tests/test_cache_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add baseline/cache_store.py tests/test_cache_store.py
git commit -m "feat: add ttl cache store"
```

---

## Task 5: v2 Resource APIs

**Files:**
- Create: `baseline/api_v2_routes.py`
- Modify: `baseline/api_get_routes.py`
- Create: `tests/test_api_v2.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_api_app_shell_and_me(payment_modules):
    api = payment_modules["api"]

    status, payload = api.handle_get("/api/app-shell", {"u": "alice", "r": "user", "role": "user"})
    assert status == 200
    assert payload["role"] == "user"
    assert [item["id"] for item in payload["nav"]] == ["dashboard", "plans", "links", "orders", "account"]

    status, payload = api.handle_get("/api/me", {"u": "alice", "r": "user", "role": "user"})
    assert status == 200
    assert payload["username"] == "alice"
    assert "subscription_url" in payload
```

- [ ] **Step 2: Run failing tests**

```powershell
python -m pytest tests/test_api_v2.py -q
```

Expected: FAIL because routes are missing.

- [ ] **Step 3: Implement `baseline/api_v2_routes.py`**

```python
import app_urls
from api_common import ok
import dashboard_service


USER_NAV = [
    {"id": "dashboard", "label": "首页"},
    {"id": "plans", "label": "套餐"},
    {"id": "links", "label": "订阅"},
    {"id": "orders", "label": "订单"},
    {"id": "account", "label": "账号"},
]

ADMIN_NAV = [
    {"id": "dashboard", "label": "概览"},
    {"id": "users", "label": "用户"},
    {"id": "orders", "label": "订单"},
    {"id": "nodes", "label": "节点"},
    {"id": "settings", "label": "设置"},
]


def handle_get(clean, session):
    role = (session or {}).get("role") or (session or {}).get("r") or "user"
    username = (session or {}).get("u", "")

    if clean == "/api/app-shell":
        return ok(role=role, nav=ADMIN_NAV if role == "admin" else USER_NAV, version="2.0.0")

    if clean == "/api/me":
        payload = dashboard_service.dashboard(session or {})
        profile = dict(payload.get("profile") or {})
        token = profile.get("sub_token", "")
        profile["username"] = username
        profile["subscription_url"] = app_urls.subscription_url(token) if token else ""
        return ok(**profile)

    return None
```

- [ ] **Step 4: Wire `api_get_routes.py`**

At the top import:

```python
import api_v2_routes
```

At the start of `handle_get`, before existing route checks:

```python
    v2 = api_v2_routes.handle_get(clean, session)
    if v2 is not None:
        return v2
```

- [ ] **Step 5: Run API tests**

```powershell
python -m pytest tests/test_api_v2.py tests/test_core_api.py tests/test_crypto_payments.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add baseline/api_v2_routes.py baseline/api_get_routes.py tests/test_api_v2.py
git commit -m "feat: add v2 app shell api"
```

---

## Task 6: Frontend Module Skeleton and Mobile Shell

**Files:**
- Create: `baseline/frontend/assets/js/main.js`
- Create: `baseline/frontend/assets/js/api.js`
- Create: `baseline/frontend/assets/js/state.js`
- Create: `baseline/frontend/assets/js/router.js`
- Create: `baseline/frontend/assets/js/components/layout.js`
- Create: `baseline/frontend/assets/css/tokens.css`
- Create: `baseline/frontend/assets/css/layout.css`
- Create: `baseline/frontend/assets/css/components.css`
- Modify: `baseline/frontend/index.html`
- Create: `tests/test_frontend_v2_structure.py`

- [ ] **Step 1: Write failing frontend structure test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "baseline" / "frontend" / "assets"


def test_frontend_v2_modules_exist_and_index_uses_module_entry():
    index = (ROOT / "baseline" / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'type="module"' in index
    assert "assets/js/main.js" in index

    for path in [
        "js/main.js",
        "js/api.js",
        "js/state.js",
        "js/router.js",
        "js/components/layout.js",
        "css/tokens.css",
        "css/layout.css",
        "css/components.css",
    ]:
        assert (ASSETS / path).exists(), path


def test_frontend_v2_mobile_shell_tokens_are_present():
    css = (ASSETS / "css" / "layout.css").read_text(encoding="utf-8")
    assert "@media (max-width: 767px)" in css
    assert "bottom-nav" in css
    assert "min-height: 44px" in css
```

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest tests/test_frontend_v2_structure.py -q
```

Expected: FAIL because module files do not exist.

- [ ] **Step 3: Add module entry to `index.html`**

Keep old assets temporarily for rollback, then add:

```html
<link rel="stylesheet" href="/assets/css/tokens.css">
<link rel="stylesheet" href="/assets/css/layout.css">
<link rel="stylesheet" href="/assets/css/components.css">
<script type="module" src="/assets/js/main.js"></script>
```

- [ ] **Step 4: Create `js/api.js`**

```javascript
export async function api(path, options = {}) {
  const init = { method: options.method || "GET", headers: { "Content-Type": "application/json" } };
  if (options.body) init.body = JSON.stringify(options.body);
  const response = await fetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}
```

- [ ] **Step 5: Create `js/state.js`**

```javascript
export const state = {
  session: null,
  shell: null,
  route: location.pathname === "/" ? "dashboard" : location.pathname.replace("/", "") || "dashboard",
  data: {},
  busy: false,
  notice: null,
};

export function setNotice(message, type = "info") {
  state.notice = message ? { message, type } : null;
}
```

- [ ] **Step 6: Create `js/router.js`**

```javascript
import { state } from "./state.js";

export function navigate(route) {
  state.route = route || "dashboard";
  history.pushState(null, "", state.route === "dashboard" ? "/" : `/${state.route}`);
  window.dispatchEvent(new CustomEvent("fake-ui:navigate"));
}

export function bindPopstate() {
  window.addEventListener("popstate", () => {
    state.route = location.pathname === "/" ? "dashboard" : location.pathname.replace("/", "") || "dashboard";
    window.dispatchEvent(new CustomEvent("fake-ui:navigate"));
  });
}
```

- [ ] **Step 7: Create `js/components/layout.js`**

```javascript
import { state } from "../state.js";
import { navigate } from "../router.js";

export function layout(content) {
  const nav = (state.shell?.nav || []).map((item) => `
    <button class="nav-item ${state.route === item.id ? "active" : ""}" data-nav="${item.id}">
      <span>${item.label}</span>
    </button>
  `).join("");
  return `
    <div class="app-shell-v2">
      <header class="topbar"><div><strong>fake-ui</strong><span>单机多出口代理编排系统</span></div></header>
      <main class="main-v2">${state.notice ? `<div class="notice ${state.notice.type}">${state.notice.message}</div>` : ""}${content}</main>
      <nav class="bottom-nav">${nav}</nav>
    </div>
  `;
}

export function bindLayoutEvents(root) {
  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-nav]");
    if (button) navigate(button.dataset.nav);
  });
}
```

- [ ] **Step 8: Create `js/main.js`**

```javascript
import { api } from "./api.js";
import { state, setNotice } from "./state.js";
import { bindPopstate } from "./router.js";
import { layout, bindLayoutEvents } from "./components/layout.js";

const app = document.querySelector("#app");

function page() {
  if (state.route === "orders") return `<section class="screen"><h1>订单</h1><p>v2 移动端订单流建设中。</p></section>`;
  if (state.route === "plans") return `<section class="screen"><h1>套餐</h1><p>v2 套餐购买流建设中。</p></section>`;
  if (state.route === "links") return `<section class="screen"><h1>订阅</h1><p>v2 订阅中心建设中。</p></section>`;
  if (state.route === "account") return `<section class="screen"><h1>账号</h1><p>v2 账号安全建设中。</p></section>`;
  return `<section class="screen"><h1>首页</h1><p>v2 移动端工作台已启动。</p></section>`;
}

export async function render() {
  app.innerHTML = layout(page());
}

async function boot() {
  try {
    state.shell = await api("/api/app-shell");
  } catch (error) {
    setNotice(error.message, "error");
  }
  bindPopstate();
  bindLayoutEvents(app);
  window.addEventListener("fake-ui:navigate", render);
  await render();
}

boot();
```

- [ ] **Step 9: Create CSS files**

`tokens.css`:

```css
:root {
  --bg: #f6f8fb;
  --surface: #ffffff;
  --ink: #101828;
  --muted: #667085;
  --line: #d8e0ea;
  --primary: #1f5eff;
  --success: #12805c;
  --warning: #b7791f;
  --danger: #c2413b;
  --radius: 8px;
  --tap: 44px;
}
```

`layout.css`:

```css
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.app-shell-v2 { min-height: 100dvh; }
.topbar { position: sticky; top: 0; z-index: 20; background: rgba(255,255,255,.96); border-bottom: 1px solid var(--line); padding: 12px 20px; }
.topbar div { display: flex; flex-direction: column; gap: 2px; }
.topbar span { color: var(--muted); font-size: 13px; }
.main-v2 { width: min(1180px, 100%); margin: 0 auto; padding: 20px; }
.screen { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; }
.bottom-nav { display: none; }
@media (max-width: 767px) {
  .main-v2 { padding: 14px 14px 88px; }
  .topbar { padding: 10px 14px; }
  .bottom-nav { position: fixed; left: 0; right: 0; bottom: 0; z-index: 30; display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 4px; padding: 8px 8px calc(8px + env(safe-area-inset-bottom)); background: var(--surface); border-top: 1px solid var(--line); }
  .nav-item { min-height: 44px; border: 0; border-radius: 8px; background: transparent; color: var(--muted); font-weight: 650; }
  .nav-item.active { background: #e9efff; color: var(--primary); }
}
```

`components.css`:

```css
button, input, select, textarea { font: inherit; }
button { min-height: 44px; cursor: pointer; }
.notice { border: 1px solid var(--line); border-radius: var(--radius); padding: 10px 12px; margin-bottom: 12px; background: var(--surface); }
.notice.error { border-color: #fecaca; color: var(--danger); background: #fff1f1; }
```

- [ ] **Step 10: Run frontend structure tests**

```powershell
python -m pytest tests/test_frontend_v2_structure.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```powershell
git add baseline/frontend/assets/js baseline/frontend/assets/css baseline/frontend/index.html tests/test_frontend_v2_structure.py
git commit -m "feat: add v2 mobile frontend shell"
```

---

## Task 7: User Mobile Flows

**Files:**
- Create: `baseline/frontend/assets/js/pages/user/dashboard.js`
- Create: `baseline/frontend/assets/js/pages/user/orders.js`
- Create: `baseline/frontend/assets/js/pages/user/plans.js`
- Create: `baseline/frontend/assets/js/pages/user/links.js`
- Modify: `baseline/frontend/assets/js/main.js`
- Modify: `tests/test_frontend_v2_structure.py`

- [ ] **Step 1: Add failing source test for user pages**

```python
def test_frontend_v2_user_pages_have_mobile_commercial_flows():
    assets = ASSETS / "js" / "pages" / "user"
    expected = ["dashboard.js", "orders.js", "plans.js", "links.js"]
    for name in expected:
        text = (assets / name).read_text(encoding="utf-8")
        assert "mobile-card" in text
        assert "data-action" in text
    orders = (assets / "orders.js").read_text(encoding="utf-8")
    assert "payment-timeline" in orders
    assert "txid" in orders.lower()
```

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest tests/test_frontend_v2_structure.py::test_frontend_v2_user_pages_have_mobile_commercial_flows -q
```

Expected: FAIL because pages do not exist.

- [ ] **Step 3: Implement user page modules**

Each module exports a `renderUser...` function returning cards with `mobile-card` class and `data-action` buttons. Use existing state data first; API-specific loading can be added later.

Example `orders.js`:

```javascript
export function renderUserOrders(data = {}) {
  const orders = data.orders || [];
  return `
    <section class="screen stack">
      <h1>我的订单</h1>
      <div class="segmented"><button data-action="orders-pending">待付款</button><button data-action="orders-history">历史</button></div>
      ${orders.map((order) => `
        <article class="mobile-card">
          <div><strong>${order.plan_name || order.plan_id || "套餐"}</strong><span>${order.status || ""}</span></div>
          <p>${order.amount || 0} USD · ${order.kind || ""}</p>
          <div class="payment-timeline">created → waiting → detected → confirmed</div>
          <button data-action="payment-refresh" data-payment="${order.payment_id || ""}">检查到账</button>
          <input name="txid" placeholder="需要时填写 TXID">
        </article>
      `).join("") || `<article class="mobile-card empty"><p>暂无订单</p><button data-action="buy-plan">购买套餐</button></article>`}
    </section>
  `;
}
```

- [ ] **Step 4: Wire user routes in `main.js`**

Import page renderers and call them by route.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_frontend_v2_structure.py -q
git add baseline/frontend/assets/js/pages/user baseline/frontend/assets/js/main.js tests/test_frontend_v2_structure.py
git commit -m "feat: add v2 user mobile flows"
```

---

## Task 8: Admin Mobile Flows

**Files:**
- Create: `baseline/frontend/assets/js/pages/admin/overview.js`
- Create: `baseline/frontend/assets/js/pages/admin/users.js`
- Create: `baseline/frontend/assets/js/pages/admin/orders.js`
- Create: `baseline/frontend/assets/js/pages/admin/nodes.js`
- Create: `baseline/frontend/assets/js/pages/admin/settings.js`
- Modify: `baseline/frontend/assets/js/main.js`
- Modify: `tests/test_frontend_v2_structure.py`

- [ ] **Step 1: Add failing admin page test**

```python
def test_frontend_v2_admin_pages_use_task_cards_and_bottom_sheets():
    assets = ASSETS / "js" / "pages" / "admin"
    for name in ["overview.js", "users.js", "orders.js", "nodes.js", "settings.js"]:
        text = (assets / name).read_text(encoding="utf-8")
        assert "admin-card" in text
        assert "data-action" in text
    orders = (assets / "orders.js").read_text(encoding="utf-8")
    assert "bottom-sheet" in orders
    nodes = (assets / "nodes.js").read_text(encoding="utf-8")
    assert "exit quality" in nodes.lower()
```

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest tests/test_frontend_v2_structure.py::test_frontend_v2_admin_pages_use_task_cards_and_bottom_sheets -q
```

Expected: FAIL.

- [ ] **Step 3: Implement admin modules**

Use card-first mobile layout and keep desktop table hooks:

```javascript
export function renderAdminOrders(data = {}) {
  const orders = data.orders || [];
  return `
    <section class="screen stack">
      <h1>订单运营</h1>
      <div class="toolbar"><input placeholder="搜索用户或订单"><button data-action="orders-filter">筛选</button></div>
      ${orders.map((order) => `
        <article class="admin-card">
          <strong>${order.username || ""}</strong>
          <p>${order.plan_name || order.plan_id || ""} · ${order.status || ""}</p>
          <button data-action="order-open-sheet" data-order="${order.id}">处理</button>
        </article>
      `).join("")}
      <div class="bottom-sheet" hidden></div>
    </section>
  `;
}
```

- [ ] **Step 4: Wire admin routes**

Update `main.js` to choose admin pages when `state.shell.role === "admin"`.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_frontend_v2_structure.py -q
git add baseline/frontend/assets/js/pages/admin baseline/frontend/assets/js/main.js tests/test_frontend_v2_structure.py
git commit -m "feat: add v2 admin mobile flows"
```

---

## Task 9: Browser Verification

**Files:**
- Modify if needed: CSS/JS files from Tasks 6-8.

- [ ] **Step 1: Start local server**

Run the panel locally using the repo's existing pattern or Python module entry. If no dev server exists, serve `baseline/frontend` through the panel so API routes work.

- [ ] **Step 2: Open local app at 375px**

Use the in-app browser. Verify:
- Login page does not horizontally scroll.
- Bottom nav appears after login/session bootstrap.
- Touch targets are at least 44px tall.
- Order/payment cards do not overflow.

- [ ] **Step 3: Open local app at 768px and 1440px**

Verify:
- Tablet layout keeps readable gutters.
- Desktop admin retains data density.
- No text overlaps.

- [ ] **Step 4: Capture screenshots**

Save screenshots under `docs/screenshots/v2/`:
- `mobile-user-dashboard.png`
- `mobile-user-orders.png`
- `desktop-admin-overview.png`

- [ ] **Step 5: Commit browser fixes and screenshots**

```powershell
git add baseline/frontend/assets docs/screenshots/v2
git commit -m "test: verify v2 responsive frontend"
```

---

## Task 10: Singapore Destructive Test Deployment

**Files:**
- Create: `scripts/reset-singapore-test-data.sh`
- Modify: `docs/OPERATIONS.md`

- [ ] **Step 1: Add reset script**

Create `scripts/reset-singapore-test-data.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "${FAKE_UI_ALLOW_TEST_RESET:-}" != "singapore" ]; then
  echo "Refusing reset: set FAKE_UI_ALLOW_TEST_RESET=singapore" >&2
  exit 1
fi

root="${1:-/opt/fake-airport}"
ts="$(date +%Y%m%d-%H%M%S)"
mkdir -p /root/fake-airport-backups
tar -czf "/root/fake-airport-backups/fake-airport-test-reset-$ts.tgz" -C "$root" data || true
rm -rf "$root/data/panel" "$root/data/generated"
mkdir -p "$root/data/panel"
echo "Singapore test data reset complete"
```

- [ ] **Step 2: Test script syntax**

```powershell
bash -n scripts/reset-singapore-test-data.sh
```

Expected: exit 0.

- [ ] **Step 3: Deploy to Singapore**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy-compose-windows.ps1 -HostAlias fake-ui-sg -RemoteDir /opt/fake-airport
```

Expected: local tests pass, remote tests pass, panel healthy.

- [ ] **Step 4: Optional destructive reset on Singapore**

Only after confirming target host is Singapore:

```powershell
ssh fake-ui-sg "cd /opt/fake-airport && FAKE_UI_ALLOW_TEST_RESET=singapore bash scripts/reset-singapore-test-data.sh /opt/fake-airport && docker compose restart panel"
```

Expected: backup created and panel restarts.

- [ ] **Step 5: Remote smoke check**

```powershell
ssh fake-ui-sg "cd /opt/fake-airport && docker compose ps && docker exec xray-proxy-panel python3 -m pytest -q"
```

Expected: panel healthy, tests pass.

- [ ] **Step 6: Commit docs/script**

```powershell
git add scripts/reset-singapore-test-data.sh docs/OPERATIONS.md
git commit -m "chore: add singapore v2 reset flow"
```

---

## Final Verification

- [ ] Run full local tests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local.ps1
```

Expected: all tests pass.

- [ ] Verify git history:

```powershell
git status --short
git log --oneline -12
```

Expected: clean tree and v2 task commits present.

- [ ] Push feature branch:

```powershell
git push origin v2-commercial-refactor
```

Expected: branch pushed for review/testing.

---

## Self-Review

| Check | Result |
|---|---|
| Spec coverage | Covers mobile UX, admin UX, frontend modules, SQLite, cache, API, Singapore deployment, and safety boundaries. |
| Placeholder scan | No `TBD`, `TODO`, or unspecified implementation steps. |
| Risk control | Worktree, frequent commits, tests, and Singapore-only destructive reset are required. |
| TDD | Each code task begins with failing tests before implementation. |
