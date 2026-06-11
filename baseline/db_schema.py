import db


SCHEMA_VERSION = 2


DDL = [
    """
    create table if not exists schema_migrations (
        version integer primary key,
        applied_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists users (
        username text primary key,
        data_json text not null,
        enabled integer not null default 1,
        plan_id text not null default '',
        expires_at text not null default '',
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists plans (
        id text primary key,
        name text not null default '',
        days integer not null default 0,
        traffic_gb real not null default 0,
        price text not null default '0',
        data_json text not null,
        enabled integer not null default 1,
        sort_order integer not null default 100,
        created_at text not null default '',
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists orders (
        id text primary key,
        username text not null,
        status text not null,
        kind text not null default '',
        plan_id text not null default '',
        plan_name text not null default '',
        amount text not null default '0',
        days integer not null default 0,
        traffic_gb real not null default 0,
        payment_status text not null default '',
        payment_id text not null default '',
        data_json text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists payment_methods (
        id text primary key,
        asset text not null,
        chain text not null,
        enabled integer not null default 1,
        sort_order integer not null default 100,
        data_json text not null,
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists payments (
        id text primary key,
        order_id text not null default '',
        username text not null default '',
        status text not null,
        asset text not null default '',
        chain text not null default '',
        txid text not null default '',
        data_json text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists nodes (
        id text primary key,
        kind text not null,
        enabled integer not null default 1,
        sort_order integer not null default 100,
        data_json text not null,
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists registrations (
        id text primary key,
        username text not null default '',
        status text not null default '',
        data_json text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists password_resets (
        id text primary key,
        username text not null default '',
        status text not null default '',
        data_json text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists audit_logs (
        id integer primary key autoincrement,
        actor text not null default '',
        action text not null default '',
        data_json text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists subscription_access (
        id integer primary key autoincrement,
        username text not null default '',
        ip text not null default '',
        data_json text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists traffic_samples (
        id integer primary key autoincrement,
        username text not null default '',
        source text not null default '',
        node_id text not null default '',
        uplink_bytes integer not null default 0,
        downlink_bytes integer not null default 0,
        total_bytes integer not null default 0,
        sampled_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    create table if not exists settings (
        key text primary key,
        value_json text not null,
        updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    "create index if not exists idx_orders_user_status on orders(username, status, created_at)",
    "create index if not exists idx_payments_order_status on payments(order_id, status, created_at)",
    "create index if not exists idx_nodes_kind_enabled on nodes(kind, enabled, sort_order)",
    "create index if not exists idx_traffic_samples_time_user on traffic_samples(sampled_at, username)",
    "create index if not exists idx_traffic_samples_node on traffic_samples(node_id, source, sampled_at)",
]


def migrate(path=None):
    with db.transaction(path) as conn:
        for statement in DDL:
            conn.execute(statement)
        conn.execute(
            "insert or ignore into schema_migrations(version) values (?)",
            (SCHEMA_VERSION,),
        )
