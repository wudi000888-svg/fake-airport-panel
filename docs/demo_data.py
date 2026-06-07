#!/usr/bin/env python3
import json
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))

os.environ.setdefault("PANEL_DIR", str(ROOT / ".demo-runtime" / "panel"))
os.environ.setdefault("PUBLIC_BASE_URL", "https://panel.example.com")
os.environ.setdefault("PANEL_DOMAIN", "panel.example.com")
os.environ.setdefault("HY2_DOMAIN", "hy.example.com")
os.environ.setdefault("DEFAULT_VLESS_ADDRESS", "vless.example.com")
os.environ.setdefault("XRAY_CONFIG", str(ROOT / ".demo-runtime" / "xray" / "config.json"))
os.environ.setdefault("HY2_ENV_FILE", str(ROOT / ".demo-runtime" / "hysteria2" / ".env"))
os.environ.setdefault("HY2_CONFIG_FILE", str(ROOT / ".demo-runtime" / "hysteria2" / "server.yaml"))

import auth_store
import admin_profile
import node_catalog
import orders_store
import payments_store
import plans_store
import registration_store
import store_facade
import user_store
from json_store import save_json
from panel_config import (
    AUDIT_LOG_FILE,
    AUTH_FILE,
    HY2_CONFIG_FILE,
    HY2_ENV_FILE,
    PANEL_DIR,
    SUB_ACCESS_LOG_FILE,
    XRAY_CONFIG,
)
from repositories.sqlite_settings import SQLiteSettingsRepository


def iso_days(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def gb(value):
    return int(float(value) * 1024 * 1024 * 1024)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def user(name, plan, days, used, quota, note, node_ids=None):
    primary_uuid = str(uuid.uuid4())
    vless_nodes = ["vless-main", "vless-proxy-1", "vless-proxy-2", "vless-proxy-3"]
    return {
        "enabled": True,
        "expires_at": iso_days(days),
        "note": note,
        "quota_bytes": gb(quota),
        "used_bytes": gb(used),
        "plan_id": plan,
        "node_groups": ["default"],
        "node_ids": node_ids or [],
        "sub_token": secrets.token_urlsafe(18),
        "vless_uuid": primary_uuid,
        "vless_node_uuids": {node_id: (primary_uuid if node_id == "vless-main" else str(uuid.uuid4())) for node_id in vless_nodes},
        "hy2_username": name,
        "hy2_password": secrets.token_urlsafe(18),
        "panel_password": auth_store.make_password_hash("demo123456"),
        "last_hy2_stats": {"tx": 0, "rx": 0},
    }


def main():
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    store_facade.ensure_sqlite()

    save_json(
        AUTH_FILE,
        {
            "session_secret": secrets.token_urlsafe(32),
            "users": {
                "admin": {"role": "admin", "password": auth_store.make_password_hash("adminpass")},
                "viewer": {"role": "user", "password": auth_store.make_password_hash("viewerpass")},
            },
        },
    )

    plans_store.save_plans(
        {
            "version": 2,
            "plans": [
                {"id": "starter", "name": "入门套餐", "days": 30, "traffic_gb": 100, "price": 19, "node_groups": ["default"], "enabled": True, "sort": 10},
                {"id": "standard", "name": "标准套餐", "days": 30, "traffic_gb": 300, "price": 39, "node_groups": ["default"], "enabled": True, "sort": 20},
                {"id": "pro", "name": "进阶套餐", "days": 30, "traffic_gb": 800, "price": 89, "node_groups": ["default"], "enabled": True, "sort": 30},
            ],
        }
    )

    node_catalog.save_catalog(
        {
            "version": 2,
            "vless_defaults_initialized": True,
            "nodes": [
                {"id": "vless-main", "name": "VLESS 直连", "kind": "vless", "group": "default", "region": "", "multiplier": 1, "status": "online", "enabled": True, "sort": 10, "outbound_mode": "direct", "exit_ip": "203.0.113.10", "country_code": "SG", "country": "Singapore", "city": "Singapore"},
                {"id": "vless-proxy-1", "name": "VLESS HTTP 出口", "kind": "vless", "group": "default", "region": "", "multiplier": 1, "status": "online", "enabled": True, "sort": 11, "outbound_mode": "http", "proxy_addr": "198.51.100.20", "proxy_port": "51000", "proxy_user": "demo-user", "proxy_password": "demo-password", "proxy_test_ip": "198.51.100.21", "exit_ip": "198.51.100.21", "country_code": "JP", "country": "Japan", "city": "Tokyo"},
                {"id": "vless-proxy-2", "name": "VLESS SOCKS5 出口", "kind": "vless", "group": "default", "region": "", "multiplier": 1, "status": "online", "enabled": True, "sort": 12, "outbound_mode": "socks5", "proxy_addr": "198.51.100.30", "proxy_port": "51001", "proxy_user": "demo-user", "proxy_password": "demo-password", "proxy_test_ip": "198.51.100.31", "exit_ip": "198.51.100.31", "country_code": "US", "country": "United States", "city": "Los Angeles"},
                {"id": "vless-proxy-3", "name": "VLESS 备用出口", "kind": "vless", "group": "default", "region": "", "multiplier": 1, "status": "maintenance", "enabled": False, "sort": 13, "outbound_mode": "direct", "exit_ip": "203.0.113.40", "country_code": "HK", "country": "Hong Kong", "city": "Hong Kong"},
                {"id": "hy2-main", "name": "Hysteria2", "kind": "hy2", "group": "default", "region": "", "multiplier": 1, "status": "online", "enabled": True, "sort": 20, "exit_ip": "203.0.113.10", "country_code": "SG", "country": "Singapore", "city": "Singapore"},
            ],
        }
    )

    user_store.save_users(
        {
            "version": 2,
            "users": {
                "viewer": user("viewer", "standard", 21, 42, 300, "本地演示登录用户"),
                "alice": user("alice", "standard", 18, 126, 300, "标准套餐用户"),
                "bob": user("bob", "starter", 6, 88, 100, "只开放直连节点", ["vless-main", "hy2-main"]),
                "carol": user("carol", "pro", 43, 215, 800, "测试多出口节点"),
            },
        }
    )

    orders_store.save_orders(
        {
            "version": 2,
            "orders": [
                {"id": "ord_demo_viewer_waiting", "username": "viewer", "kind": "renew", "plan_id": "standard", "plan_name": "标准套餐", "days": 30, "traffic_gb": 300, "amount": 39, "status": "pending", "payment_status": "awaiting_payment", "payment_id": "pay_demo_viewer", "note": "链上付款演示", "operator": "user", "created_at": iso_days(-1)},
                {"id": "ord_demo_viewer_done", "username": "viewer", "kind": "create", "plan_id": "starter", "plan_name": "入门套餐", "days": 30, "traffic_gb": 100, "amount": 19, "status": "completed", "payment_status": "confirmed", "note": "历史订单演示", "operator": "system", "created_at": iso_days(-7)},
                {"id": "ord_demo_pending", "username": "alice", "kind": "renew", "plan_id": "standard", "plan_name": "标准套餐", "days": 30, "traffic_gb": 300, "amount": 39, "status": "pending", "note": "线下付款待确认", "operator": "user", "created_at": iso_days(-1)},
                {"id": "ord_demo_done", "username": "carol", "kind": "create", "plan_id": "pro", "plan_name": "进阶套餐", "days": 30, "traffic_gb": 800, "amount": 89, "status": "completed", "note": "演示订单", "operator": "admin", "created_at": iso_days(-5)},
            ],
        }
    )

    payments_store.save_payments(
        {
            "version": 2,
            "methods": [
                {
                    "id": "usdt-bsc-demo",
                    "label": "USDT / BSC",
                    "asset": "USDT",
                    "chain": "bsc",
                    "address": "0x15878544950c5391fdc43be8c84d0c822bda85db",
                    "decimals": 6,
                    "confirmations_required": 3,
                    "enabled": True,
                    "sort": 100,
                    "created_at": iso_days(-10),
                    "updated_at": iso_days(-1),
                }
            ],
            "payments": [
                {
                    "id": "pay_demo_viewer",
                    "order_id": "ord_demo_viewer_waiting",
                    "username": "viewer",
                    "method_id": "usdt-bsc-demo",
                    "asset": "USDT",
                    "chain": "bsc",
                    "address": "0x15878544950c5391fdc43be8c84d0c822bda85db",
                    "amount_usd": "39",
                    "crypto_amount": "39.000000",
                    "status": "awaiting_payment",
                    "confirmations": 0,
                    "qr_payload": "0x15878544950c5391fdc43be8c84d0c822bda85db",
                    "created_at": iso_days(-1),
                    "updated_at": iso_days(-1),
                }
            ],
            "rates": {"overrides": {"USDT": "1"}, "cache": {}},
        }
    )

    registration_store.save_data({"version": 2, "pending": [], "resets": []})
    admin_profile.save_profile(
        {
            "version": 2,
            "user": {
                "enabled": True,
                "expires_at": iso_days(365),
                "sub_token": secrets.token_urlsafe(18),
                "vless_uuid": str(uuid.uuid4()),
                "vless_node_uuids": {
                    "vless-main": str(uuid.uuid4()),
                    "vless-proxy-1": str(uuid.uuid4()),
                    "vless-proxy-2": str(uuid.uuid4()),
                    "vless-proxy-3": str(uuid.uuid4()),
                },
                "hy2_username": "demo-admin",
                "hy2_password": secrets.token_urlsafe(18),
                "node_groups": ["default"],
                "quota_bytes": 0,
                "used_bytes": 0,
            },
        }
    )
    SQLiteSettingsRepository().set(
        "link_settings",
        {
            "vless_address": "vless.example.com",
            "vless_port": 443,
            "vless_name": "VLESS_Reality_vless.example.com",
            "hy2_name": "HY2_hy.example.com",
        },
    )

    write_text(AUDIT_LOG_FILE, "[demo] admin node.refresh vless-main\n[demo] admin user.create alice\n")
    write_text(SUB_ACCESS_LOG_FILE, '{"ts":"demo","username":"alice","ip":"198.51.100.8","status":"ok","path":"/sub/demo/raw","ua":"Mihomo"}\n')
    write_text(
        XRAY_CONFIG,
        json.dumps(
            {
                "inbounds": [
                    {
                        "tag": "vless-reality-in",
                        "listen": "127.0.0.1",
                        "port": 8443,
                        "protocol": "vless",
                        "settings": {"clients": [{"id": str(uuid.uuid4()), "flow": "xtls-rprx-vision"}]},
                        "streamSettings": {
                            "network": "tcp",
                            "security": "reality",
                            "realitySettings": {
                                "serverNames": ["www.cloudflare.com"],
                                "shortIds": ["0123456789abcdef"],
                                "privateKey": "demo-private-key",
                            },
                        },
                    }
                ],
                "outbounds": [{"tag": "direct", "protocol": "freedom"}],
                "routing": {"rules": []},
            },
            indent=2,
        ),
    )
    write_text(HY2_ENV_FILE, "HY_DOMAIN=hy.example.com\nHY_PASSWORD=demo-hy2-password\nHY_PORT=443\n")
    write_text(
        HY2_CONFIG_FILE,
        "listen: :443\nauth:\n  type: password\n  password: demo-hy2-password\noutbounds:\n  - name: direct\n    type: direct\n",
    )
    print(PANEL_DIR)


if __name__ == "__main__":
    main()
