"""
Прокси с нормальным входом по HTTP-only cookie.
Запускай так: сначала Streamlit (port 8501), затем этот сервис (port 8000).
Пользователь заходит на 8000 → форма входа → cookie → прокси к Streamlit.
"""
import base64
import hmac
import hashlib
import os
import time
from fastapi import FastAPI, Request, Response, Cookie, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Пароль из env (тот же APP_PASSWORD или ADMIN_PASSWORD)
APP_PASSWORD = (os.getenv("APP_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://127.0.0.1:8501")
COOKIE_NAME = "skynet_auth"
AUTH_DAYS = 7


def make_token():
    expiry = int(time.time()) + AUTH_DAYS * 24 * 3600
    sig = hmac.new(APP_PASSWORD.encode(), str(expiry).encode(), hashlib.sha256).digest()
    b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{b64}.{expiry}"


def check_token(token: str) -> bool:
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


app = FastAPI(title="Skynet Auth Proxy")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)

LOGIN_HTML = """
<!DOCTYPE html>
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
</html>
"""


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=AUTH_DAYS * 24 * 3600,
        path="/",
        httponly=True,
        secure=os.getenv("AUTH_PROXY_SECURE", "false").lower() in ("1", "true"),
        samesite="lax",
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
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
    token = make_token()
    response = RedirectResponse(url="/", status_code=302)
    set_auth_cookie(response, token)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/auth/verify")
async def auth_verify(session: str | None = Cookie(None, alias=COOKIE_NAME)):
    """Для nginx auth_request: 200 = пустить, 401 = редирект на логин."""
    if not APP_PASSWORD:
        return {"ok": True}
    if session and check_token(session):
        return {"ok": True}
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=401, content={"error": "unauthorized"})


# Прокси к Streamlit
FORWARD_HEADERS = {"accept", "accept-encoding", "user-agent", "content-type", "cookie", "origin", "referer"}


async def proxy_request(request: Request, path: str) -> Response:
    url = f"{STREAMLIT_URL.rstrip('/')}/{path}" if path else STREAMLIT_URL.rstrip("/") + "/"
    if request.url.query:
        url += "?" + request.url.query
    headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARD_HEADERS}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if request.method == "GET":
                r = await client.get(url, headers=headers)
            elif request.method == "POST":
                body = await request.body()
                r = await client.post(url, content=body, headers=headers)
            else:
                r = await client.request(request.method, url, headers=headers)
        return Response(
            content=r.content,
            status_code=r.status_code,
            headers={k: v for k, v in r.headers.items() if k.lower() not in ("transfer-encoding", "connection", "content-encoding")},
        )
    except Exception as e:
        return Response(content=f"Proxy error: {e}", status_code=502)


@app.websocket("/_stcore/stream")
async def streamlit_websocket(websocket: WebSocket, session: str | None = Cookie(None, alias=COOKIE_NAME)):
    if APP_PASSWORD and (not session or not check_token(session)):
        await websocket.close(code=4001)
        return
    await websocket.accept()
    q = str(websocket.scope.get("query_string", "") or "")
    ws_url = STREAMLIT_URL.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + "/_stcore/stream" + ("?" + q if q else "")
    try:
        import websockets
        async with websockets.connect(ws_url) as backend:
            async def from_backend():
                try:
                    while True:
                        msg = await backend.recv()
                        await (websocket.send_bytes(msg) if isinstance(msg, bytes) else websocket.send_text(msg))
                except Exception:
                    pass
            async def from_client():
                try:
                    while True:
                        msg = await websocket.receive()
                        if "bytes" in msg:
                            await backend.send(msg["bytes"])
                        elif "text" in msg:
                            await backend.send(msg["text"])
                except WebSocketDisconnect:
                    pass
            import asyncio
            await asyncio.gather(from_backend(), from_client())
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request, response: Response, session: str | None = Cookie(None, alias=COOKIE_NAME)):
    if not APP_PASSWORD:
        return await proxy_request(request, path)
    if path.strip("/") in ("login", "logout", "auth"):
        return await proxy_request(request, path)
    if not session or not check_token(session):
        return RedirectResponse(url="/login", status_code=302)
    return await proxy_request(request, path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
