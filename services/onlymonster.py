"""
Onlymonster API — метрики чаттеров, аккаунты, trial links, tracking links.
API: https://omapi.onlymonster.ai/docs/json
"""
import json
import os
import streamlit as st
import pandas as pd
from urllib.parse import urlencode
from datetime import datetime

import requests

# User-Agent: некоторые API блокируют запросы без браузерного UA
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SkynetUI/1.0 (Streamlit Dashboard)",
}


def get_api_config():
    """Читает конфиг: secrets.toml или .env (локально)."""
    url, api_key, account_ids = "", "", None
    try:
        om = st.secrets.get("onlymonster", {})
        url = om.get("api_url") or ""
        api_key = om.get("api_key") or ""
        aid = om.get("account_ids")
        if aid is not None:
            if isinstance(aid, list):
                account_ids = {str(x).strip() for x in aid if x}
            else:
                account_ids = {str(x).strip() for x in str(aid).split(",") if str(x).strip()}
    except Exception:
        pass
    if not url or not api_key:
        url = url or os.getenv("ONLYMONSTER_API_URL") or os.getenv("OM_API_URL") or ""
        api_key = api_key or os.getenv("ONLYMONSTER_API_KEY") or os.getenv("OM_API_KEY") or ""
    if account_ids is None:
        env_ids = os.getenv("ONLYMONSTER_ACCOUNT_IDS") or os.getenv("OM_ACCOUNT_IDS") or ""
        account_ids = {x.strip() for x in env_ids.split(",") if x.strip()} or None
    return {"url": url, "api_key": api_key, "account_ids": account_ids}


def _api_request(url, headers, method="GET"):
    """Выполняет запрос; при 403 возвращает тело ответа для диагностики."""
    h = {**DEFAULT_HEADERS, **headers}
    r = requests.request(method, url, headers=h, timeout=30)
    if r.status_code == 403:
        try:
            body = r.json()
            msg = body.get("message") or body.get("error") or r.text[:500]
        except Exception:
            msg = r.text[:500] if r.text else "No response body"
        raise PermissionError(f"403 Forbidden. API ответ: {msg}. Убедись, что API-доступ включён в Onlymonster и у токена есть права.")
    if r.status_code == 401:
        raise ValueError("Неверный API токен Onlymonster")
    r.raise_for_status()
    return r.json()


def _to_iso(d):
    """Форматирует дату в ISO 8601 Zulu."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if isinstance(d, str):
        return d if "T" in d else f"{d}T00:00:00.000Z"
    return str(d)


def fetch_accounts(with_expired=False):
    """
    GET /api/v0/accounts — список аккаунтов OnlyFans.
    Возвращает list of {id, platform_account_id, platform, name, username, subscribe_price, subscription_expiration_date, ...}.
    """
    config = get_api_config()
    if not config["url"] or not config["api_key"]:
        return None
    base = config["url"].rstrip("/")
    headers = {"x-om-auth-token": config["api_key"], "Accept": "application/json"}
    all_accounts = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        if with_expired:
            params["withExpiredSubscriptions"] = "true"
        qs = urlencode(params)
        url = f"{base}/api/v0/accounts?{qs}"
        try:
            data = _api_request(url, headers)
        except (PermissionError, ValueError):
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка Onlymonster API: {e}") from e
        accounts = data.get("accounts") or []
        all_accounts.extend(accounts)
        cursor = data.get("nextCursor")
        if not cursor or not accounts:
            break
    return all_accounts


def fetch_trial_links(platform_account_id, start_date=None, end_date=None, all_links=False):
    """
    GET /api/v0/platforms/onlyfans/accounts/{platform_account_id}/trial-links
    Возвращает list of {id, name, claims, claims_limit, url, duration_days, expires_at, is_active, clicks, created_at}.
    API фильтрует по дате создания ссылки. При all_links=True берётся широкий диапазон (2020–сейчас),
    чтобы подтянуть все ссылки и отфильтровать активные на клиенте.
    """
    config = get_api_config()
    if not config["url"] or not config["api_key"]:
        return None
    base = config["url"].rstrip("/")
    headers = {"x-om-auth-token": config["api_key"], "Accept": "application/json"}
    if all_links:
        from_ts = "2020-01-01T00:00:00.000Z"
        to_ts = datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z")
    else:
        from_ts = _to_iso(start_date) or "2020-01-01T00:00:00.000Z"
        to_ts = _to_iso(end_date) or datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z")
    all_items = []
    cursor = None
    while True:
        params = {"start": from_ts, "end": to_ts, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        qs = urlencode(params)
        url = f"{base}/api/v0/platforms/onlyfans/accounts/{platform_account_id}/trial-links?{qs}"
        try:
            data = _api_request(url, headers)
        except (PermissionError, ValueError):
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка Onlymonster API: {e}") from e
        items = data.get("items") or []
        all_items.extend(items)
        cursor = data.get("cursor")
        if not cursor or len(items) < 100:
            break
    return all_items


def fetch_tracking_links(platform_account_id, start_date=None, end_date=None, all_links=False):
    """
    GET /api/v0/platforms/onlyfans/accounts/{platform_account_id}/tracking-links
    Возвращает list of {id, name, subscribers, url, is_active, clicks, created_at}.
    При all_links=True — широкий диапазон (2020–сейчас), чтобы подтянуть все ссылки.
    """
    config = get_api_config()
    if not config["url"] or not config["api_key"]:
        return None
    base = config["url"].rstrip("/")
    headers = {"x-om-auth-token": config["api_key"], "Accept": "application/json"}
    if all_links:
        from_ts = "2020-01-01T00:00:00.000Z"
        to_ts = datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z")
    else:
        from_ts = _to_iso(start_date) or "2020-01-01T00:00:00.000Z"
        to_ts = _to_iso(end_date) or datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z")
    all_items = []
    cursor = None
    while True:
        params = {"start": from_ts, "end": to_ts, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        qs = urlencode(params)
        url = f"{base}/api/v0/platforms/onlyfans/accounts/{platform_account_id}/tracking-links?{qs}"
        try:
            data = _api_request(url, headers)
        except (PermissionError, ValueError):
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка Onlymonster API: {e}") from e
        items = data.get("items") or []
        all_items.extend(items)
        cursor = data.get("cursor")
        if not cursor or len(items) < 100:
            break
    return all_items


def fetch_transactions(platform_account_id, start_date=None, end_date=None):
    """
    GET /api/v0/platforms/onlyfans/accounts/{platform_account_id}/transactions
    Возвращает list of {id, amount, fan, type, status, timestamp}.
    type: Tip from, Payment for message, recurring subscription, post purchase, live stream, unknown.
    """
    config = get_api_config()
    if not config["url"] or not config["api_key"]:
        return None
    base = config["url"].rstrip("/")
    headers = {"x-om-auth-token": config["api_key"], "Accept": "application/json"}
    from_ts = _to_iso(start_date) or "2020-01-01T00:00:00.000Z"
    to_ts = _to_iso(end_date) or datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z")
    all_items = []
    cursor = None
    while True:
        params = {"start": from_ts, "end": to_ts, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        qs = urlencode(params)
        url = f"{base}/api/v0/platforms/onlyfans/accounts/{platform_account_id}/transactions?{qs}"
        try:
            data = _api_request(url, headers)
        except (PermissionError, ValueError):
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка Onlymonster API: {e}") from e
        items = data.get("items") or []
        all_items.extend(items)
        cursor = data.get("cursor")
        if not cursor or len(items) < 1000:
            break
    return all_items


def fetch_chatter_metrics(creator_ids=None, user_ids=None, start_date=None, end_date=None):
    """
    Запрос метрик из Onlymonster API (GET /api/v0/users/metrics).
    https://omapi.onlymonster.ai/docs/json

    creator_ids: list of creator IDs (опционально)
    user_ids: list of user IDs / chatter IDs (опционально)
    start_date, end_date: строки или datetime в формате ISO 8601

    Возвращает list of {chatter, ppv_open_rate, apv, total_chats, user_id, creator_ids}.
    chatter = str(user_id) — для сопоставления может потребоваться маппинг user_id → имя.
    """
    config = get_api_config()
    if not config["url"] or not config["api_key"]:
        return None

    base = config["url"].rstrip("/")
    if not base:
        return None

    from_ts = _to_iso(start_date)
    to_ts = _to_iso(end_date)
    if not from_ts or not to_ts:
        return None

    headers = {"x-om-auth-token": config["api_key"], "Accept": "application/json"}
    records = []
    offset = 0
    limit = 100

    while True:
        params = [
            ("from", from_ts),
            ("to", to_ts),
            ("offset", offset),
            ("limit", limit),
        ]
        if creator_ids:
            for cid in creator_ids[:100]:
                params.append(("creator_ids", cid))
        if user_ids:
            for uid in user_ids[:100]:
                params.append(("user_ids", uid))
        qs = urlencode(params)
        url = f"{base}/api/v0/users/metrics?{qs}"

        try:
            data = _api_request(url, headers)
        except (PermissionError, ValueError):
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка Onlymonster API: {e}") from e

        items = data.get("items") or []
        if not items:
            break

        for item in items:
            user_id = item.get("user_id")
            if user_id is None:
                continue
            paid = item.get("paid_messages_count") or 0
            sold = item.get("sold_messages_count") or 0
            sold_sum = item.get("sold_messages_price_sum") or 0
            messages = item.get("messages_count") or 0

            ppv_open_rate = (sold / paid * 100) if paid > 0 else None
            apv = (sold_sum / sold) if sold > 0 else None

            rec = {
                "chatter": str(user_id),
                "user_id": user_id,
                "ppv_open_rate": round(ppv_open_rate, 1) if ppv_open_rate is not None else None,
                "apv": round(apv, 2) if apv is not None else None,
                "total_chats": messages if messages else None,
                "creator_ids": item.get("creator_ids") or [],
                "source": "api",
            }
            records.append(rec)

        if len(items) < limit:
            break
        offset += limit

    return records


def parse_kpi_csv(uploaded_file):
    """
    Парсит CSV/XLSX экспорт из Onlymonster Chatter Metrics.
    Ожидаемые колонки (названия могут варьироваться):
    - Member / Chatter / Member ID / Member Name
    - PPV Open Rate / PPV Open Rate %
    - APV / Avg. Price of Sold PPV / Avg Payment Value
    - Total Chats
    - Creator / Model (опционально)
    """
    if uploaded_file is None:
        return []
    name = (uploaded_file.name or "").lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8")
        elif name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(uploaded_file)
        else:
            return []
    except Exception:
        return []

    if df.empty:
        return []

    # Нормализуем названия колонок
    cols = {c.lower().strip(): c for c in df.columns}
    chatter_col = None
    for k in ["member", "chatter", "member id", "member name", "member_id", "member_name"]:
        if k in cols:
            chatter_col = cols[k]
            break
    ppv_col = None
    for k in ["ppv open rate", "ppv open rate %", "ppv_open_rate"]:
        if k in cols:
            ppv_col = cols[k]
            break
    apv_col = None
    for k in ["apv", "avg. price of sold ppv", "avg price of sold ppv", "avg payment value"]:
        if k in cols:
            apv_col = cols[k]
            break
    chats_col = None
    for k in ["total chats", "total_chats"]:
        if k in cols:
            chats_col = cols[k]
            break
    creator_col = None
    for k in ["creator", "creator id", "model"]:
        if k in cols:
            creator_col = cols[k]
            break

    records = []
    for _, row in df.iterrows():
        chatter = row.get(chatter_col) if chatter_col else None
        if pd.isna(chatter) or str(chatter).strip() == "":
            continue
        rec = {"chatter": str(chatter).strip()}
        if ppv_col and not pd.isna(row.get(ppv_col)):
            try:
                v = row[ppv_col]
                if isinstance(v, str) and "%" in v:
                    v = v.replace("%", "").strip()
                rec["ppv_open_rate"] = float(v)
            except (ValueError, TypeError):
                pass
        if apv_col and not pd.isna(row.get(apv_col)):
            try:
                v = row[apv_col]
                if isinstance(v, str):
                    v = v.replace("$", "").replace(",", "").strip()
                rec["apv"] = float(v)
            except (ValueError, TypeError):
                pass
        if chats_col and not pd.isna(row.get(chats_col)):
            try:
                rec["total_chats"] = int(float(row[chats_col]))
            except (ValueError, TypeError):
                pass
        if creator_col and not pd.isna(row.get(creator_col)):
            rec["model"] = str(row[creator_col]).strip()
        rec["source"] = "csv"
        records.append(rec)
    return records
