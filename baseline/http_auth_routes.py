import auth_store
import audit_log
import security
import simple_pages


def handle_logout(handler):
    handler.send_response(302)
    handler.send_header("Set-Cookie", security.clear_session_cookie())
    handler.send_header("Set-Cookie", "panel_csrf=; Path=/; Max-Age=0; Secure; SameSite=Lax")
    handler.send_header("Location", "/login")
    handler.end_headers()


def handle_login_post(handler):
    data = handler.read_post()
    username = data.get("username", [""])[0].strip()
    password = data.get("password", [""])[0]
    key = security.login_key(handler, username)
    if security.login_limited(key):
        audit_log.write(username or "anonymous", "auth.login_rate_limited", ip=getattr(handler, "client_address", [""])[0])
        handler.respond(simple_pages.login(error="登录尝试过多，请稍后再试。"), 429)
        return
    role = auth_store.authenticate_user(username, password)
    if role:
        security.clear_login_failures(key)
        token = auth_store.make_session(username, role)
        session = auth_store.session_payload(token) or {}
        csrf = security.csrf_token_for_session(session)
        audit_log.write(username, "auth.login_success", ip=getattr(handler, "client_address", [""])[0])
        handler.send_response(302)
        handler.send_header("Set-Cookie", security.session_cookie(token))
        handler.send_header("Set-Cookie", security.csrf_cookie(csrf))
        handler.send_header("Location", "/" if role == "admin" else "/links")
        handler.end_headers()
        return
    security.record_login_failure(key)
    audit_log.write(username or "anonymous", "auth.login_failed", ip=getattr(handler, "client_address", [""])[0])
    handler.respond(simple_pages.login(error="账号或密码错误。"))


def forbidden(handler):
    handler.respond(simple_pages.forbidden(), 403)
