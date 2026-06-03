import node_catalog
import operations_service as ops


def main():
    store = node_catalog.load_catalog()
    updated = []
    for node in list(store.get("nodes", [])):
        try:
            refreshed = ops.apply_node_exit_info(dict(node))
            node_catalog.upsert_node(refreshed)
            updated.append(f"{refreshed.get('id')} => {refreshed.get('name')}")
        except Exception as exc:
            updated.append(f"{node.get('id')} => 检测失败: {exc}")
    print("\n".join(updated))


if __name__ == "__main__":
    main()
