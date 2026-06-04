#!/usr/bin/env bash
set -euo pipefail

if [ "${FAKE_UI_ALLOW_TEST_RESET:-}" != "singapore" ]; then
  echo "Refusing reset: set FAKE_UI_ALLOW_TEST_RESET=singapore" >&2
  exit 1
fi

root="${1:-/opt/fake-airport}"
ts="$(date +%Y%m%d-%H%M%S)"
backup_dir="${FAKE_UI_TEST_BACKUP_DIR:-/root/fake-airport-backups}"

case "$root" in
  /opt/fake-airport|/opt/fake-airport/)
    ;;
  *)
    echo "Refusing reset outside /opt/fake-airport: $root" >&2
    exit 1
    ;;
esac

mkdir -p "$backup_dir"
if [ -d "$root/data" ]; then
  tar -czf "$backup_dir/fake-airport-test-reset-$ts.tgz" -C "$root" data
fi

rm -rf "$root/data/panel" "$root/data/generated"
mkdir -p "$root/data/panel"
echo "Singapore test data reset complete: $root"
