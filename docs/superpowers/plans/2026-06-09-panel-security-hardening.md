# Panel Security Hardening Implementation Plan

## Goal

Reduce obvious production-facing risk in the current built-in panel while keeping the project lightweight and compatible with the existing deployment.

## Steps

1. Add a small `security.py` helper for headers, cookies, CSRF, and login attempt tracking.
2. Include CSRF material in signed sessions and expose the public CSRF token through session API responses.
3. Require `X-CSRF-Token` on authenticated API POST requests.
4. Set `Secure` on session cookies and add a readable CSRF cookie for browser clients.
5. Add security headers in all Python responses and Nginx template responses.
6. Write audit entries for login success, login failure, and login rate limiting.
7. Add tests for cookie/header behavior, rate limiting, and CSRF enforcement.

## Validation

```bash
python -m pytest -q
```

