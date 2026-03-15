# Вход по паролю + cookie: nginx (auth_request) + сервис входа + Streamlit
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    gettext-base \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY auth_proxy/requirements.txt auth_proxy/
RUN pip install --no-cache-dir -r auth_proxy/requirements.txt

COPY . .

COPY auth_proxy/nginx.conf.template /etc/nginx/conf.d/default.conf.template
RUN rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

COPY auth_proxy/start_with_nginx.sh /app/start_with_nginx.sh
RUN chmod +x /app/start_with_nginx.sh

ENV AUTH_PROXY=1
EXPOSE 8080
CMD ["/app/start_with_nginx.sh"]
