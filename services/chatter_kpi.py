"""
KPI чаттеров: PPV Open Rate, APV, Total Chats.
Источники: Onlymonster API, Notion, ручной ввод.
"""
import json
import os

import streamlit as st

from services.db import get_connection

MAPPING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chatter_id_to_name.json")

CHATTER_KPI_SCHEMA = """
CREATE TABLE IF NOT EXISTS chatter_kpi (
  year INT NOT NULL,
  month INT NOT NULL,
  chatter TEXT NOT NULL,
  ppv_open_rate NUMERIC,
  apv NUMERIC,
  total_chats NUMERIC,
  model TEXT,
  source TEXT DEFAULT 'manual',
  PRIMARY KEY (year, month, chatter)
);
"""


def _ensure_chatter_kpi_table():
    """Создаёт таблицу chatter_kpi, если её нет."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(CHATTER_KPI_SCHEMA)
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def get_chatter_id_to_name_mapping():
    """
    Маппинг user_id (Onlymonster) → имя или [имена].
    Файл data/chatter_id_to_name.json (в git).
    """
    if not os.path.exists(MAPPING_FILE):
        return {}
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def get_name_to_chatter_id_reverse_mapping():
    """Обратный маппинг: любой алиас → user_id."""
    mapping = get_chatter_id_to_name_mapping()
    reverse = {}
    for uid, names in mapping.items():
        for name in (names if isinstance(names, list) else [names]):
            n = str(name).strip()
            if n:
                reverse[n] = str(uid)
    return reverse


@st.cache_data(ttl=120)
def _load_kpi_from_db(year, month):
    """Загружает KPI из БД. Возвращает dict {chatter: {ppv_open_rate, apv, total_chats, model, source}}."""
    _ensure_chatter_kpi_table()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT chatter, ppv_open_rate, apv, total_chats, model, source FROM chatter_kpi WHERE year = %s AND month = %s",
            (year, month),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = {}
        for r in rows:
            chatter, ppv, apv, chats, model, src = r
            result[str(chatter)] = {
                "ppv_open_rate": float(ppv) if ppv is not None else None,
                "apv": float(apv) if apv is not None else None,
                "total_chats": int(chats) if chats is not None else None,
                "model": model,
                "source": src or "manual",
            }
        return result
    except Exception:
        return {}


def get_kpi(year, month, apply_id_mapping=True):
    """
    Возвращает dict {chatter: {ppv_open_rate, apv, total_chats, model?, source}}.
    """
    kpi = _load_kpi_from_db(year, month)
    if not apply_id_mapping:
        return kpi
    mapping = get_chatter_id_to_name_mapping()
    if not mapping:
        return kpi
    result = {}
    for uid, val in kpi.items():
        names = mapping.get(str(uid), uid)
        display = names[0] if isinstance(names, list) and names else (names if names else uid)
        result[str(display).strip()] = val
    return result


def get_unmapped_user_ids(year, month):
    """user_id из KPI, для которых нет записи в маппинге."""
    kpi_by_id, _ = get_kpi_for_merge(year, month)
    mapping = get_chatter_id_to_name_mapping()
    return [uid for uid in kpi_by_id if str(uid) not in mapping]


def get_kpi_for_merge(year, month):
    """
    Возвращает (kpi_by_id, name_to_id).
    """
    kpi = _load_kpi_from_db(year, month)
    mapping = get_chatter_id_to_name_mapping()
    name_to_id = {}
    for uid, names in mapping.items():
        for n in (names if isinstance(names, list) else [names]):
            if n:
                name_to_id[str(n).strip()] = str(uid)
    return kpi, name_to_id


def save_kpi(year, month, chatter, ppv_open_rate=None, apv=None, total_chats=None, model=None, source="manual"):
    """Сохраняет KPI для чаттера."""
    _ensure_chatter_kpi_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chatter_kpi (year, month, chatter, ppv_open_rate, apv, total_chats, model, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (year, month, chatter) DO UPDATE SET
            ppv_open_rate = COALESCE(EXCLUDED.ppv_open_rate, chatter_kpi.ppv_open_rate),
            apv = COALESCE(EXCLUDED.apv, chatter_kpi.apv),
            total_chats = COALESCE(EXCLUDED.total_chats, chatter_kpi.total_chats),
            model = COALESCE(EXCLUDED.model, chatter_kpi.model),
            source = COALESCE(EXCLUDED.source, chatter_kpi.source)
        """,
        (year, month, str(chatter).strip(), ppv_open_rate, apv, total_chats, model, source),
    )
    conn.commit()
    cur.close()
    conn.close()


def save_kpi_batch(year, month, records):
    """Сохраняет batch KPI из API/CSV."""
    _ensure_chatter_kpi_table()
    conn = get_connection()
    cur = conn.cursor()
    for r in records:
        chatter = r.get("chatter") or r.get("member") or r.get("member_name")
        if not chatter:
            continue
        ppv = r.get("ppv_open_rate")
        apv = r.get("apv")
        chats = r.get("total_chats")
        model = r.get("model") or r.get("creator")
        src = r.get("source", "api")
        cur.execute(
            """
            INSERT INTO chatter_kpi (year, month, chatter, ppv_open_rate, apv, total_chats, model, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (year, month, chatter) DO UPDATE SET
                ppv_open_rate = COALESCE(EXCLUDED.ppv_open_rate, chatter_kpi.ppv_open_rate),
                apv = COALESCE(EXCLUDED.apv, chatter_kpi.apv),
                total_chats = COALESCE(EXCLUDED.total_chats, chatter_kpi.total_chats),
                model = COALESCE(EXCLUDED.model, chatter_kpi.model),
                source = EXCLUDED.source
            """,
            (year, month, str(chatter).strip(), ppv, apv, chats, model, src),
        )
    conn.commit()
    cur.close()
    conn.close()
