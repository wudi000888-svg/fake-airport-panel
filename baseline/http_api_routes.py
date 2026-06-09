import api
import security


def handle_get(handler):
    try:
        status, payload = api.handle_get(handler.path, handler.current_session())
    except Exception as exc:
        status, payload = api.api_error(str(exc), 400)
    if status == 200 and isinstance(payload, dict) and isinstance(payload.get("content"), (bytes, bytearray)):
        filename = payload.get("filename") or "fake-ui-backup.tgz"
        handler.respond_bytes(
            payload.get("content"),
            payload.get("content_type") or "application/octet-stream",
            {"Content-Disposition": f'attachment; filename="{filename}"'},
        )
        return
    handler.respond_json(payload, status)


def handle_post(handler):
    try:
        session = handler.current_session()
        csrf_error = None
        if handler.path != "/api/login":
            csrf_error = security.csrf_error_for(handler, session)
        if csrf_error is not None:
            status, payload = csrf_error
        else:
            status, payload = api.handle_post(handler.path, handler.read_json_or_form(), session)
    except Exception as exc:
        status, payload = api.api_error(str(exc), 400)
    handler.respond_json(payload, status)
