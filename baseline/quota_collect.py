#!/usr/bin/env python3
import os
from datetime import datetime, timedelta, timezone

import node_catalog
import traffic_store
from traffic_stats import query_hy2_stats, query_xray_stats, to_int
import user_store


RETENTION_DAYS = int(os.getenv("TRAFFIC_SAMPLE_RETENTION_DAYS", "90") or "90")


def has_stat(stats, key):
    return key in (stats or {})


def xray_totals_for_user(stats, username, user):
    uplink = 0
    downlink = 0
    seen = False
    for node in node_catalog.nodes_for_user(user, kind="vless", include_disabled=True):
        email = node_catalog.vless_node_email(username, node.get("id", ""))
        up_key = f"user>>>{email}>>>traffic>>>uplink"
        down_key = f"user>>>{email}>>>traffic>>>downlink"
        if has_stat(stats, up_key) or has_stat(stats, down_key):
            seen = True
            uplink += to_int(stats.get(up_key, 0))
            downlink += to_int(stats.get(down_key, 0))
    return uplink, downlink, seen


def xray_node_deltas(stats, username, user):
    samples = []
    for node in node_catalog.nodes_for_user(user, kind="vless", include_disabled=True):
        node_id = node.get("id", "")
        email = node_catalog.vless_node_email(username, node_id)
        up_key = f"user>>>{email}>>>traffic>>>uplink"
        down_key = f"user>>>{email}>>>traffic>>>downlink"
        if not has_stat(stats, up_key) and not has_stat(stats, down_key):
            continue
        up_now = to_int(stats.get(up_key, 0))
        down_now = to_int(stats.get(down_key, 0))
        key = f"xray:{node_id}"
        node_stats = user.setdefault("last_node_stats", {})
        last = node_stats.setdefault(key, {})
        if "uplink" not in last and "downlink" not in last:
            last["uplink"] = up_now
            last["downlink"] = down_now
            continue
        up_last = to_int(last.get("uplink", 0))
        down_last = to_int(last.get("downlink", 0))
        up_delta = up_now - up_last if up_now >= up_last else up_now
        down_delta = down_now - down_last if down_now >= down_last else down_now
        if max(0, up_delta) or max(0, down_delta):
            samples.append(
                {
                    "username": username,
                    "source": "xray",
                    "node_id": node_id,
                    "uplink_bytes": max(0, up_delta),
                    "downlink_bytes": max(0, down_delta),
                }
            )
        if last.get("uplink") != up_now or last.get("downlink") != down_now:
            last["uplink"] = up_now
            last["downlink"] = down_now
    return samples


def main():
    data = user_store.load_users()
    users = data.setdefault("users", {})
    stats = query_xray_stats()
    hy2_stats = query_hy2_stats()
    sampled_at = datetime.now(timezone.utc).isoformat()
    if RETENTION_DAYS > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
        traffic_store.delete_before(cutoff)

    changed = False

    for username, u in users.items():
        for sample in xray_node_deltas(stats, username, u):
            sample["sampled_at"] = sampled_at
            traffic_store.add_sample(sample)
            changed = True

        up_now, down_now, has_xray = xray_totals_for_user(stats, username, u)

        last = u.setdefault("last_xray_stats", {})
        if has_xray:
            up_last = to_int(last.get("uplink", 0))
            down_last = to_int(last.get("downlink", 0))

            up_delta = up_now - up_last if up_now >= up_last else up_now
            down_delta = down_now - down_last if down_now >= down_last else down_now
            delta = max(0, up_delta) + max(0, down_delta)

            if delta > 0:
                u["used_bytes"] = to_int(u.get("used_bytes", 0)) + delta
                u["last_traffic_update"] = datetime.now(timezone.utc).isoformat()
                changed = True

            if last.get("uplink") != up_now or last.get("downlink") != down_now:
                last["uplink"] = up_now
                last["downlink"] = down_now
                changed = True

        hy_user = u.get("hy2_username") or username
        if hy_user in hy2_stats:
            hy_now = hy2_stats.get(hy_user, {})
            hy_tx_now = to_int(hy_now.get("tx", 0))
            hy_rx_now = to_int(hy_now.get("rx", 0))

            hy_last = u.setdefault("last_hy2_stats", {})
            hy_tx_last = to_int(hy_last.get("tx", 0))
            hy_rx_last = to_int(hy_last.get("rx", 0))

            hy_tx_delta = hy_tx_now - hy_tx_last if hy_tx_now >= hy_tx_last else hy_tx_now
            hy_rx_delta = hy_rx_now - hy_rx_last if hy_rx_now >= hy_rx_last else hy_rx_now
            hy_delta = max(0, hy_tx_delta) + max(0, hy_rx_delta)

            if hy_delta > 0:
                u["used_bytes"] = to_int(u.get("used_bytes", 0)) + hy_delta
                u["last_traffic_update"] = datetime.now(timezone.utc).isoformat()
                traffic_store.add_sample(
                    {
                        "username": username,
                        "source": "hy2",
                        "node_id": "hy2-main",
                        "uplink_bytes": max(0, hy_tx_delta),
                        "downlink_bytes": max(0, hy_rx_delta),
                        "sampled_at": sampled_at,
                    }
                )
                changed = True

            if hy_last.get("tx") != hy_tx_now or hy_last.get("rx") != hy_rx_now:
                hy_last["tx"] = hy_tx_now
                hy_last["rx"] = hy_rx_now
                changed = True

        quota = to_int(u.get("quota_bytes", 0))
        used = to_int(u.get("used_bytes", 0))
        over = quota > 0 and used >= quota

        if u.get("quota_exceeded") != over:
            u["quota_exceeded"] = over
            changed = True

    if changed:
        user_store.save_users(data)

    print("quota collect ok")


if __name__ == "__main__":
    main()
