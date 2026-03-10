"""
Проверка Onlymonster API: какие эндпоинты отвечают, что возвращает 403.
Запуск: python scripts/check_onlymonster_api.py
Требует .env с ONLYMONSTER_API_URL и ONLYMONSTER_API_KEY (или .streamlit/secrets.toml)
"""
import os
import json
import sys

# загружаем .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "services", ".env"))
except ImportError:
    pass

import requests

BASE = os.getenv("ONLYMONSTER_API_URL") or os.getenv("OM_API_URL") or ""
TOKEN = os.getenv("ONLYMONSTER_API_KEY") or os.getenv("OM_API_KEY") or ""

# secrets.toml (если .env пуст)
if (not BASE or not TOKEN):
    _p = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
    if os.path.exists(_p):
        try:
            with open(_p, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            m = re.search(r'api_url\s*=\s*["\']([^"\']+)["\']', content)
            if m and not BASE:
                BASE = m.group(1)
            m = re.search(r'api_key\s*=\s*["\']([^"\']+)["\']', content)
            if m and not TOKEN:
                TOKEN = m.group(1)
        except Exception:
            pass

BASE = (BASE or "").rstrip("/")
MODEL_IDS = ["34920", "23676"]  # пара для теста


def test_endpoint(method, url, headers, name):
    """Тестирует endpoint, выводит статус и тело ответа при ошибке."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  {method} {url}")
    print("=" * 60)
    try:
        r = requests.request(method, url, headers=headers, timeout=15)
        print(f"  Статус: {r.status_code}")
        if r.status_code >= 400:
            print(f"  Headers ответа:")
            for k, v in r.headers.items():
                if k.lower() in ("content-type", "x-", "www-authenticate", "retry-after"):
                    print(f"    {k}: {v}")
            print(f"  Тело ответа (первые 1000 символов):")
            try:
                body = r.json()
                print(f"    {json.dumps(body, ensure_ascii=False, indent=2)[:1000]}")
            except Exception:
                print(f"    {r.text[:1000]}")
        else:
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"  Записей: {len(data)}")
                elif isinstance(data, dict):
                    keys = list(data.keys())[:10]
                    print(f"  Ключи: {keys}")
            except Exception:
                print(f"  Ответ: {r.text[:200]}...")
    except Exception as e:
        print(f"  Ошибка: {e}")


def main():
    if not BASE or not TOKEN:
        print("Ошибка: нужны ONLYMONSTER_API_URL и ONLYMONSTER_API_KEY в .env или secrets.toml")
        sys.exit(1)

    print(f"Base URL: {BASE}")
    print(f"Token: {TOKEN[:20]}...{TOKEN[-4:] if len(TOKEN) > 24 else ''}")

    headers = {
        "Accept": "application/json",
        "User-Agent": "SkynetUI-Check/1.0",
        "x-om-auth-token": TOKEN,
    }

    # 1. /api/v0/accounts
    test_endpoint("GET", f"{BASE}/api/v0/accounts?limit=5", headers, "1. GET /api/v0/accounts (список аккаунтов)")

    # 2. /api/v0/users/metrics (тот же что KPI)
    from datetime import datetime
    fmt = "2025-01-01T00:00:00.000Z"
    to_ts = "2025-03-31T23:59:59.999Z"
    test_endpoint("GET", f"{BASE}/api/v0/users/metrics?from={fmt}&to={to_ts}&offset=0&limit=10", headers, "2. GET /api/v0/users/metrics (KPI чаттеров)")

    # Берём реальные данные из /accounts
    acc_data = requests.get(f"{BASE}/api/v0/accounts?limit=2", headers=headers).json()
    accs = acc_data.get("accounts") or []
    if accs:
        acc = accs[0]
        om_id = acc.get("id")
        platform_id = acc.get("platform_account_id")
        print(f"\n  Первый аккаунт: id(OM)={om_id}, platform_account_id={platform_id}")

    # 3. trial-links — пробуем platform_account_id
    if accs:
        platform_id = str(accs[0].get("platform_account_id", ""))
        test_endpoint(
            "GET",
            f"{BASE}/api/v0/platforms/onlyfans/accounts/{platform_id}/trial-links?start={fmt}&end={to_ts}&limit=10",
            headers,
            f"3a. GET .../accounts/{platform_id}/trial-links (platform_account_id)",
        )

        # 3b. trial-links — пробуем id (OM)
        om_id = str(accs[0].get("id", ""))
        test_endpoint(
            "GET",
            f"{BASE}/api/v0/platforms/onlyfans/accounts/{om_id}/trial-links?start={fmt}&end={to_ts}&limit=10",
            headers,
            f"3b. GET .../accounts/{om_id}/trial-links (id OM)",
        )

        # 3c. trial-links — platform_id + organisation_id=12063
        org_id = accs[0].get("organisation_id", "12063")
        test_endpoint(
            "GET",
            f"{BASE}/api/v0/platforms/onlyfans/accounts/{platform_id}/trial-links?start={fmt}&end={to_ts}&limit=10&organisation_id={org_id}",
            headers,
            f"3c. GET trial-links + organisation_id={org_id}",
        )

        # 4. tracking-links — platform_account_id и id
        test_endpoint(
            "GET",
            f"{BASE}/api/v0/platforms/onlyfans/accounts/{platform_id}/tracking-links?start={fmt}&end={to_ts}&limit=10",
            headers,
            f"4a. GET .../accounts/{platform_id}/tracking-links (platform_account_id)",
        )
        test_endpoint(
            "GET",
            f"{BASE}/api/v0/platforms/onlyfans/accounts/{om_id}/tracking-links?start={fmt}&end={to_ts}&limit=10",
            headers,
            f"4b. GET .../accounts/{om_id}/tracking-links (id OM)",
        )
    else:
        pid = MODEL_IDS[0]
        test_endpoint("GET", f"{BASE}/api/v0/platforms/onlyfans/accounts/{pid}/trial-links?start={fmt}&end={to_ts}&limit=10", headers, f"3. trial-links {pid}")
        test_endpoint("GET", f"{BASE}/api/v0/platforms/onlyfans/accounts/{pid}/tracking-links?start={fmt}&end={to_ts}&limit=10", headers, f"4. tracking-links {pid}")

    # 5. Попробуем Authorization: Bearer
    headers_alt = {**headers}
    del headers_alt["x-om-auth-token"]
    headers_alt["Authorization"] = f"Bearer {TOKEN}"
    test_endpoint("GET", f"{BASE}/api/v0/accounts?limit=1", headers_alt, "5. GET /accounts с Authorization: Bearer")

    # 6. Токен без префикса om_token_
    if TOKEN.startswith("om_token_"):
        token_bare = TOKEN.replace("om_token_", "")
        headers_bare = {**headers}
        headers_bare["x-om-auth-token"] = token_bare
        test_endpoint("GET", f"{BASE}/api/v0/accounts?limit=1", headers_bare, "6. GET /accounts (токен без om_token_)")

    print("\n" + "=" * 60)
    print("Проверка завершена. Если все 403 — доступ к API ограничен планом.")
    print("=" * 60)


if __name__ == "__main__":
    main()
