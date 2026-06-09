# Panel Security Hardening Design

## Goal

Harden the built-in fake-ui panel for small production deployments without changing the runtime architecture or introducing a web framework.

## Scope

- Add security response headers from the Python server.
- Mark session cookies `Secure` in addition to `HttpOnly` and `SameSite=Lax`.
- Add CSRF validation for authenticated API write requests.
- Add lightweight login rate limiting keyed by client IP and username.
- Add login success, failure, and rate-limit audit events.
- Add reverse-proxy security headers to the Nginx template.

## Non-goals

- Replacing the built-in HTTP server with a framework.
- Implementing distributed rate limiting.
- Encrypting backups in this patch.
- Changing Xray, Hysteria2, subscription, or payment protocol behavior.

## Compatibility

Existing signed sessions before this change may not contain a `csrf` field. Those sessions are invalid after this hardening patch, and users must log in again to obtain a CSRF-bound session.
