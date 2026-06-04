# Next Steps

This file tracks public-safe development direction. It intentionally avoids live server details and secrets.

## Workflow

| Step | Rule |
|---|---|
| 1. Plan | Define target, risk, files, and test scope before implementation. |
| 2. Implement | Keep changes small and aligned with current modules. |
| 3. Local test | Run Python compile and pytest before pushing. |
| 4. Remote preflight | Test scripts and APIs on the VPS before restarting live services. |
| 5. Deploy | Back up first, deploy, then verify health. |
| 6. Release | Tag and publish GitHub Release only after tests pass. |

## Suggested Roadmap

| Version | Theme | Candidate Work |
|---|---|---|
| v1.2.1 | Upgrade and install polish | `UPGRADE.md`, `scripts/upgrade.sh`, stronger installer preflight report. |
| v1.3.0 | Node orchestration | Exit quality checks, batch node refresh, per-user node visibility UX. |
| v1.4.0 | Product experience | Dashboard polish, mobile UI improvements, clearer plan/order states. |
| v1.5.0 | Operations | Scheduled backups, restore command, upgrade rollback helper. |
| v2.0.0 | Expansion | Optional multi-server support, optional database, payment integration. |

## Completed in v1.2.0

| Area | Result |
|---|---|
| Crypto payments | USD-priced orders can be paid with USDT, USDC, ETH, BNB, or BTC. |
| Admin setup | Admins can add receive-only payment methods with built-in chain defaults. |
| Verification | EVM/BTC chain verification supports automatic scan, TXID fallback, and order activation. |
| RPC resilience | Public RPC calls have fallback handling, EVM log scans are narrowed by payment time and split on range limits. |
| Order UX | Pending, ambiguous, cancelled, and history states are separated in the frontend. |
| Windows deploy | `scripts/deploy-compose-windows.ps1` packages, uploads, tests, backs up, rebuilds, and health-checks the panel. |

## v1.2.1 Candidate Tasks

| Priority | Task | Acceptance Criteria |
|---|---|---|
| P0 | Add `UPGRADE.md` | Explains safe upgrade from a zip/GitHub release without touching `data/`. |
| P0 | Add `scripts/upgrade.sh` | Backs up current install, syncs code, rebuilds containers, runs health checks, keeps rollback path. |
| P1 | Installer preflight report | Shows DNS, ports, Docker, Nginx, BBR, IPv4 forwarding, cert mode before install. |
| P1 | Node exit quality checks | Measures exit IP, country, latency, and test URL status per node. |
| P2 | README first-screen polish | Makes project value clear in the first 30 seconds. |

## Standard Test Gate

| Environment | Required Checks |
|---|---|
| Local | `python -m py_compile docs/demo_data.py @(rg --files baseline -g "*.py")` on Windows or equivalent; `python -m pytest -q`. |
| Remote preflight | `bash -n scripts/install-fresh-vps.sh`; `python3 -m py_compile ...`; `python3 -m pytest -q`. |
| Live after deploy | Panel container healthy; `/login`, `/assets/app.js`, `/api/session` return 200; Xray config test OK; Hysteria2 running; Nginx active if native mode. |

## Release Checklist

| Step | Command / Action |
|---|---|
| Confirm clean tree | `git status --short` |
| Confirm tests | Run local and remote test gates. |
| Tag | `git tag -a vX.Y.Z -m "fake-ui vX.Y.Z"` |
| Push tag | `git push origin vX.Y.Z` |
| Publish release | Use GitHub Releases with tested changes and test results. |
| Verify release page | Open `/releases/tag/vX.Y.Z`. |
