"""
Onlymonster API — PPV Open Rate, APV, Total Chats по чаттерам.
API: https://omapi.onlymonster.ai/docs/json
Эндпоинт: GET /api/v0/users/metrics
"""
import json
import streamlit as st
import pandas as pd
import urllib.request
import urllib.error
from urllib.parse import urlencode
from datetime import datetime


def get_api_config():
    """Читает конфиг из secrets."""
    try:
        return {
            "url": st.secrets.get("onlymonster", {}).get("api_url", ""),
            "api_key": st.secrets.get("onlymonster", {}).get("api_key", ""),
        }
    except Exception:
        return {"url": "", "api_key": ""}


def _api_request(url, headers, method="GET"):
    req = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


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

    # Форматируем даты в ISO 8601 Zulu
    def to_iso(d):
        if d is None:
            return None
        if isinstance(d, datetime):
            return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if isinstance(d, str):
            return d if "T" in d else f"{d}T00:00:00.000Z"
        return str(d)

    from_ts = to_iso(start_date)
    to_ts = to_iso(end_date)
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
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ValueError("Неверный API токен Onlymonster")
            raise
        except Exception as e:
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
