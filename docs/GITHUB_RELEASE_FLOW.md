# GitHub Release Flow

This document describes the public-safe flow for publishing fake-ui updates to GitHub.

## 1. Prepare

| Check | Command |
|---|---|
| Current branch and status | `git status --short` |
| Latest commit | `git log -1 --oneline` |
| Remote | `git remote -v` |
| Existing tags | `git tag --list "v*"` |

Do not continue if unrelated local changes exist.
The Windows Compose deploy script archives `HEAD`, so the default path refuses to deploy when `git status --porcelain` is not empty. Commit or stash first; use `-AllowDirtyHead` only when you deliberately want to deploy the committed `HEAD` while local changes remain.

## 2. Local Test

Windows PowerShell:

```powershell
python -m py_compile docs\demo_data.py @(rg --files baseline -g "*.py")
python -m pytest -q
git diff --check
```

Linux/macOS:

```bash
python3 -m py_compile docs/demo_data.py $(find baseline -name '*.py' -type f | sort)
python3 -m pytest -q
git diff --check
```

## 3. Remote Preflight

Before changing live services, test in a temporary directory on the VPS:

```bash
verify="/opt/fake-ui-verify-$(date +%Y%m%d%H%M%S)"
git clone --depth 1 https://github.com/wudi000888-svg/fake-ui.git "$verify"
cd "$verify"
bash -n scripts/install-fresh-vps.sh
python3 -m py_compile docs/demo_data.py $(find baseline -name '*.py' -type f | sort)
python3 -m pytest -q
```

If pytest is not installed on the VPS, install test-only packages or use an isolated virtual environment. Do not modify runtime `data/` during preflight.

## 4. Back Up Live Install

```bash
cd /opt
tar -czf "/opt/fake-ui.backup.$(date +%Y%m%d%H%M%S).tar.gz" fake-airport
```

Adjust the directory name if your install path is different.

## 5. Deploy Code Without Runtime Data

Example when the verified source is in `$verify` and the live install is `/opt/fake-airport`:

```bash
src="$verify"
dst="/opt/fake-airport"

cd "$src"
python3 scripts/package-code.py /tmp/fake-ui-code.tar

cd "$dst"
tar -xf /tmp/fake-ui-code.tar
rm -f /tmp/fake-ui-code.tar
```

This preserves `.env`, `data/`, generated certs, users, tokens, node settings, and runtime secrets.
When packaging from macOS, prefer `scripts/package-code.py` over direct `tar` so Finder metadata and extended attributes are not written into the archive.

## 6. Rebuild and Restart

```bash
cd /opt/fake-airport
bash -n scripts/install-fresh-vps.sh
python3 -m py_compile docs/demo_data.py $(find baseline -name '*.py' -type f | sort)
python3 -m pytest -q

docker compose build panel xray
docker compose up -d xray panel hysteria2
```

If the deployment uses container Nginx, include `nginx` in the `up -d` command. If it uses native Nginx, do not replace the native Nginx config unless the release specifically requires it.

## 7. Live Health Checks

| Check | Command |
|---|---|
| Containers | `docker compose ps` |
| Panel health | `docker inspect -f '{{.State.Health.Status}}' xray-proxy-panel` |
| Login page | `curl -k -fsS https://PANEL_DOMAIN/login >/dev/null` |
| Frontend JS | `curl -k -fsS https://PANEL_DOMAIN/assets/js/main.js >/dev/null` |
| Session API | `curl -k -fsS https://PANEL_DOMAIN/api/session` |
| Xray config | `docker exec xray xray run -test -config /etc/xray/config.json` |
| User sync | `docker exec xray-proxy-panel python3 /app/enforce_users.py` |
| Hysteria2 logs | `docker logs --tail=50 hysteria2` |

## 8. Rollback

If health checks fail:

```bash
cd /opt
mv fake-airport "fake-airport.failed.$(date +%Y%m%d%H%M%S)"
tar -xzf /opt/fake-ui.backup.YYYYMMDDHHMMSS.tar.gz
cd /opt/fake-airport
docker compose up -d xray panel hysteria2
```

Include `nginx` if the install uses container Nginx.

## 9. Publish GitHub Release

After live tests pass:

```bash
git tag -a vX.Y.Z -m "fake-ui vX.Y.Z"
git push origin vX.Y.Z
```

Pushing the tag starts `.github/workflows/release.yml`. The workflow creates the GitHub Release, uploads a public source archive, and reads `docs/releases/vX.Y.Z.md` when it exists.

Release notes should include:

| Section | Content |
|---|---|
| Summary | One short paragraph about why the release exists. |
| Updates | Bullet list of user-visible changes. |
| Tests | Local and VPS test results. |
| Upgrade notes | Any special action required by existing users. |
| Safety note | Remind users that runtime secrets are not included in the repo. |

## 10. New Conversation Handoff

When moving to a new Codex conversation, paste the public handoff prompt from `PROJECT_MEMORY.md`, then ask the agent to read:

```text
PROJECT_MEMORY.md
NEXT_STEPS.md
docs/GITHUB_RELEASE_FLOW.md
```

Keep private VPS details, passwords, tokens, and private keys outside Git.
