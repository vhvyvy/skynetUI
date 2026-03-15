"""
Минимальный сервис только для входа и проверки cookie.
Используется вместе с nginx: nginx делает auth_request на /auth/verify и проксирует в Streamlit.
Запуск: uvicorn auth_proxy.auth_only:app --host 127.0.0.1 --port 8000
"""
import base64
import hmac
import hashlib
import os
import time

from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

APP_PASSWORD = (os.getenv("APP_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
COOKIE_NAME = "skynet_auth"
AUTH_DAYS = 7

app = FastAPI(title="Skynet Auth")

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Вход</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; background: #1e293b; color: #e2e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }
    .card { background: #334155; padding: 2rem; border-radius: 12px; width: 100%; max-width: 360px; }
    h1 { margin: 0 0 0.5rem 0; font-size: 1.5rem; }
    .hint { color: #94a3b8; font-size: 0.875rem; margin-bottom: 1.25rem; }
    input { width: 100%; padding: 0.75rem; border-radius: 8px; border: 1px solid #475569; background: #1e293b; color: #e2e8f0; font-size: 1rem; margin-bottom: 1rem; }
    input:focus { outline: none; border-color: #00d4aa; }
    button { width: 100%; padding: 0.75rem; border-radius: 8px; border: none; background: #00d4aa; color: #0f172a; font-weight: 600; font-size: 1rem; cursor: pointer; }
    button:hover { background: #00f5c4; }
    .err { color: #f87171; font-size: 0.875rem; margin-top: 0.5rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🔐 Вход в панель</h1>
    <p class="hint">Введите пароль. Сессия сохранится на 7 дней.</p>
    <form method="post" action="/login">
      <input type="password" name="password" placeholder="Пароль" required autofocus>
      <button type="submit">Войти</button>
    </form>
    <p class="err">{{ error }}</p>
  </div>
</body>
</html>"""


def _make_token():
    expiry = int(time.time()) + AUTH_DAYS * 24 * 3600
    sig = hmac.new(APP_PASSWORD.encode(), str(expiry).encode(), hashlib.sha256).digest()
    b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{b64}.{expiry}"


def _check_token(token: str) -> bool:
    if not token or "." not in token:
        return False
    parts = token.split(".", 1)
    try:
        expiry = int(parts[1])
        if expiry <= time.time():
            return False
        raw = parts[0]
        pad = (4 - len(raw) % 4) % 4
        sig = base64.urlsafe_b64decode(raw + "=" * pad)
        expected = hmac.new(APP_PASSWORD.encode(), str(expiry).encode(), hashlib.sha256).digest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _is_secure(request: Request) -> bool:
    if os.getenv("AUTH_PROXY_SECURE", "").lower() in ("1", "true"):
        return True
    return (request.headers.get("x-forwarded-proto") or "").lower() == "https"


@app.get("/login", response_class=HTMLResponse)
async def login_page(error: str = ""):
    if not APP_PASSWORD:
        return RedirectResponse(url="/", status_code=302)
    return HTMLResponse(LOGIN_HTML.replace("{{ error }}", error))


@app.post("/login")
async def login_post(request: Request):
    if not APP_PASSWORD:
        return RedirectResponse(url="/", status_code=302)
    form = await request.form()
    pwd = (form.get("password") or "").strip()
    if pwd != APP_PASSWORD:
        return HTMLResponse(LOGIN_HTML.replace("{{ error }}", "Неверный пароль"))
    token = _make_token()
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=AUTH_DAYS * 24 * 3600,
        path="/",
        httponly=True,
        secure=_is_secure(request),
        samesite="lax",
    )
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@app.get("/auth/verify")
async def auth_verify(session: str | None = Cookie(None, alias=COOKIE_NAME)):
    """nginx auth_request: 200 = пустить, 401 = редирект на /login."""
    if not APP_PASSWORD:
        return JSONResponse(content={"ok": True})
    if session and _check_token(session):
        return JSONResponse(content={"ok": True})
    return JSONResponse(status_code=401, content={"error": "unauthorized"})
