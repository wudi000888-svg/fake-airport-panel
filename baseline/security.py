import secrets
import time
from ipaddress import ip_address, ip_network

from http_utils import api_error
from panel_config import SESSION_TTL


_LOGIN_ATTEMPTS = {}
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 8
CSRF_HEADER = "X-CSRF-Token"
TRUSTED_PROXY_NETWORKS = tuple(
    ip_network(network)
    for network in (
        "127.0.0.0/8",
        "::1/128",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fc00::/7",
    )
)


def security_headers(content_type=""):
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    if "text/html" in str(content_type):
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
    return headers


def session_cookie(token, max_age=SESSION_TTL):
    value = f"panel_session={token}; Path=/; HttpOnly; Secure; SameSite=Lax"
    if max_age is not None:
        value += f"; Max-Age={int(max_age)}"
    return value


def clear_session_cookie():
    return session_cookie("", max_age=0)


def csrf_cookie(token, max_age=SESSION_TTL):
    return f"panel_csrf={token}; Path=/; Secure; SameSite=Lax; Max-Age={int(max_age)}"


def csrf_token_for_session(session):
    if not session:
        return ""
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf"] = token
    return token


def _is_trusted_proxy_ip(ip):
    try:
        parsed = ip_address(str(ip or "").strip())
    except ValueError:
        return False
    return any(parsed in network for network in TRUSTED_PROXY_NETWORKS)


def _forwarded_ip_chain(forwarded_for=""):
    return [part.strip() for part in str(forwarded_for or "").split(",") if part.strip()]


def client_ip_from_request(remote_ip="", forwarded_for=""):
    remote = str(remote_ip or "").strip()
    forwarded = _forwarded_ip_chain(forwarded_for)
    if forwarded and _is_trusted_proxy_ip(remote):
        for ip in reversed(forwarded):
            if not _is_trusted_proxy_ip(ip):
                return ip
        return forwarded[-1]
    return remote


def login_key(handler, username):
    forwarded = handler.headers.get("X-Forwarded-For", "")
    return login_key_from_request(username, remote_ip=getattr(handler, "client_address", [""])[0], forwarded_for=forwarded)


def login_key_from_request(username, remote_ip="", forwarded_for=""):
    ip = client_ip_from_request(remote_ip, forwarded_for)
    return f"{ip}:{str(username or '').lower()}"


def login_error_message():
    return "too many login attempts; please try again later"


def login_limited(key, now=None):
    now = int(now or time.time())
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
    _LOGIN_ATTEMPTS[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def record_login_failure(key, now=None):
    now = int(now or time.time())
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
    attempts.append(now)
    _LOGIN_ATTEMPTS[key] = attempts


def clear_login_failures(key):
    _LOGIN_ATTEMPTS.pop(key, None)


def csrf_error_for(handler, session):
    if not session:
        return None
    role = session.get("role") or session.get("r")
    if not role:
        return None
    expected = session.get("csrf", "")
    supplied = handler.headers.get(CSRF_HEADER, "")
    if not expected or not secrets.compare_digest(str(expected), str(supplied)):
        return api_error("csrf validation failed", 403)
    return None
