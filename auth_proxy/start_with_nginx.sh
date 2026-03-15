#!/bin/sh
set -e
# PORT задаёт Railway; подставляем в конфиг nginx
export PORT=${PORT:-8080}
envsubst '${PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Сервис входа (только /login, /logout, /auth/verify)
python -m uvicorn auth_proxy.auth_only:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# Streamlit на внутреннем порту
sleep 2
python -m streamlit run app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true &
STREAMLIT_PID=$!

# Ждём готовности Streamlit
python -c "
import time, urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2)
        break
    except Exception:
        time.sleep(1)
"

# Nginx в foreground — слушает PORT и проксирует
exec nginx -g 'daemon off;'
