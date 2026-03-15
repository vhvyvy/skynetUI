import calendar
import json
import os
from urllib.parse import urlparse
import streamlit as st
import pandas as pd
import psycopg2


def _parse_database_url(url):
    """Парсит DATABASE_URL / DATABASE_PUBLIC_URL (Railway)."""
    if not url or not url.strip():
        return None
    try:
        p = urlparse(url)
        if p.scheme not in ("postgresql", "postgres"):
            return None
        return {
            "host": p.hostname,
            "port": p.port or 5432,
            "database": (p.path or "").lstrip("/") or "railway",
            "user": p.username or "postgres",
            "password": p.password or "",
        }
    except Exception:
        return None


def _get_db_config():
    """Читает конфиг БД из DATABASE_URL, st.secrets или env (Railway и др.)."""
    db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if db_url:
        parsed = _parse_database_url(db_url)
        if parsed:
            return parsed

    try:
        return {
            "host": st.secrets.get("db_host") or os.getenv("PG_HOST") or os.getenv("PGHOST") or os.getenv("DB_HOST") or "localhost",
            "port": int(st.secrets.get("db_port") or os.getenv("PG_PORT") or os.getenv("DB_PORT") or 5432),
            "database": st.secrets.get("db_name") or os.getenv("PG_DB") or os.getenv("PGDATABASE") or os.getenv("DB_NAME") or "skynet",
            "user": st.secrets.get("db_user") or os.getenv("PG_USER") or os.getenv("DB_USER") or "postgres",
            "password": st.secrets.get("db_password") or os.getenv("PG_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("DB_PASS") or "",
        }
    except Exception:
        return {
            "host": os.getenv("PG_HOST") or os.getenv("PGHOST") or os.getenv("DB_HOST") or "localhost",
            "port": int(os.getenv("PG_PORT") or os.getenv("DB_PORT") or 5432),
            "database": os.getenv("PG_DB") or os.getenv("PGDATABASE") or os.getenv("DB_NAME") or "skynet",
            "user": os.getenv("PG_USER") or os.getenv("DB_USER") or "postgres",
            "password": os.getenv("PG_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("DB_PASS") or "",
        }


# =====================================================
# Подключение
# =====================================================

def get_connection():
    cfg = _get_db_config()
    kwargs = dict(
        host=cfg["host"],
        port=cfg["port"],
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )
    # Neon, Railway и др. облачные БД требуют SSL
    if cfg["host"] and (".neon.tech" in cfg["host"] or "proxy.rlwy.net" in cfg["host"]):
        kwargs["sslmode"] = "require"
    return psycopg2.connect(**kwargs)


# =====================================================
# Транзакции
# =====================================================

@st.cache_data(ttl=300)
def load_transactions(start_date, end_date):
    conn = get_connection()

    if start_date is not None and end_date is not None:
        query = """
            SELECT
                id,
                date,
                model,
                chatter,
                amount,
                month_source,
                synced_at,
                shift_id,
                shift_name
            FROM transactions
            WHERE date IS NOT NULL
            AND date BETWEEN %s AND %s
            ORDER BY date ASC
        """
        df = pd.read_sql(query, conn, params=(start_date, end_date))
    else:
        query = """
            SELECT
                id,
                date,
                model,
                chatter,
                amount,
                month_source,
                synced_at,
                shift_id,
                shift_name
            FROM transactions
            WHERE date IS NOT NULL
            ORDER BY date ASC
        """
        df = pd.read_sql(query, conn)

    conn.close()
    return df


# =====================================================
# Расходы
# =====================================================

@st.cache_data(ttl=300)
def load_expenses(start_date, end_date):
    conn = get_connection()

    if start_date is not None and end_date is not None:
        query = """
            SELECT
                id,
                notion_id,
                date,
                model,
                category,
                vendor,
                payment_method,
                amount
            FROM expenses
            WHERE date IS NOT NULL
            AND date BETWEEN %s AND %s
            ORDER BY date ASC
        """
        df = pd.read_sql(query, conn, params=(start_date, end_date))
    else:
        query = """
            SELECT
                id,
                notion_id,
                date,
                model,
                category,
                vendor,
                payment_method,
                amount
            FROM expenses
            WHERE date IS NOT NULL
            ORDER BY date ASC
        """
        df = pd.read_sql(query, conn)

    conn.close()

    # Убираем дубликаты (могут появиться при повторной синхронизации из Notion)
    if not df.empty and "notion_id" in df.columns:
        has_notion = df["notion_id"].notna()
        df_with_notion = df[has_notion].drop_duplicates(subset=["notion_id"], keep="first")
        df_no_notion = df[~has_notion]
        df = pd.concat([df_with_notion, df_no_notion], ignore_index=True)
    if not df.empty and "id" in df.columns:
        df = df.drop_duplicates(subset=["id"], keep="first")

    # Исправление: Liza с датой февраля ошибочно была в январской таблице Notion.
    # Убираем Liza из февраля, добавляем в январь как KM.
    if start_date is not None and end_date is not None:
        req_month = start_date.month
        req_year = start_date.year
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        is_liza_feb = (df["vendor"].fillna("").str.strip().str.lower() == "liza") & (df["date"].dt.month == 2)
        if req_month == 2:
            df = df[~is_liza_feb]
        elif req_month == 1:
            df = df[~is_liza_feb]
            conn = get_connection()
            feb_start = start_date.replace(month=2, day=1)
            last_day = calendar.monthrange(req_year, 2)[1]
            feb_end = start_date.replace(month=2, day=last_day)
            liza_query = """
                SELECT id, notion_id, date, model, category, vendor, payment_method, amount
                FROM expenses WHERE date IS NOT NULL AND date BETWEEN %s AND %s
                AND LOWER(TRIM(vendor)) = 'liza'
                ORDER BY date ASC
            """
            liza_df = pd.read_sql(liza_query, conn, params=(feb_start, feb_end))
            conn.close()
            if not liza_df.empty:
                liza_df["date"] = pd.to_datetime(liza_df["date"]).apply(lambda d: d.replace(month=1, year=req_year))
                liza_df["vendor"] = "KM"
                df = pd.concat([df, liza_df], ignore_index=True)

    return df


# =====================================================
# Доступные месяцы (из транзакций и расходов)
# =====================================================

@st.cache_data(ttl=300)
def load_shifts():
    """Возвращает dict {shift_id: shift_name} из таблицы shifts."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM shifts")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {str(r[0]): (r[1] or str(r[0])) for r in rows}
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def get_all_available_months():
    """Returns list of (year, month) tuples for months that have data in transactions or expenses."""
    conn = get_connection()

    query = """
        SELECT DISTINCT DATE_TRUNC('month', date)::date AS month_start
        FROM (
            SELECT date FROM transactions WHERE date IS NOT NULL
            UNION
            SELECT date FROM expenses WHERE date IS NOT NULL
        ) AS all_dates
        ORDER BY month_start DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return []

    df = df.dropna(subset=["month_start"])
    return [
        (int(pd.Timestamp(val).year), int(pd.Timestamp(val).month))
        for val in df["month_start"]
    ]


# =====================================================
# Настройки приложения (сохранение между сессиями)
# =====================================================

def _get_app_settings_impl():
    """Возвращает dict {key: value} из таблицы app_settings. Пустой dict при ошибке."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM app_settings")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {str(r[0]): r[1] for r in rows} if rows else {}
    except Exception:
        return {}


# Кэш 2 мин (сброс при сохранении настроек). Опционально — для старых Streamlit без cache_data
_cache_data = getattr(st, "cache_data", None)
get_app_settings = _cache_data(ttl=120)(_get_app_settings_impl) if _cache_data else _get_app_settings_impl


def set_app_settings(settings_dict):
    """Сохраняет настройки в БД (key → value). values приводятся к str."""
    if not settings_dict:
        return
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()
        for k, v in settings_dict.items():
            cur.execute(
                "INSERT INTO app_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (str(k), str(v)),
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


# =====================================================
# Маппинг чаттер ↔ Onlymonster ID (для KPI)
# =====================================================

def get_chatter_onlymonster_mapping():
    """Возвращает dict {onlymonster_id: [display_name, ...]} из БД."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT onlymonster_id, display_names FROM chatter_onlymonster_mapping")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = {}
        for onlymonster_id, display_names in rows or []:
            try:
                names = json.loads(display_names) if isinstance(display_names, str) and display_names.strip().startswith("[") else [display_names]
            except Exception:
                names = [display_names] if display_names else []
            out[str(onlymonster_id)] = names
        return out
    except Exception:
        return {}


def save_chatter_onlymonster_mapping(onlymonster_id, display_names):
    """display_names: список строк или одна строка. Сохраняет в БД."""
    if not onlymonster_id or not str(onlymonster_id).strip():
        return
    names = display_names if isinstance(display_names, list) else [str(display_names).strip()] if display_names else []
    names = [n for n in names if n]
    if not names:
        return
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS chatter_onlymonster_mapping (onlymonster_id TEXT PRIMARY KEY, display_names TEXT NOT NULL)"
        )
        conn.commit()
        cur.execute(
            "INSERT INTO chatter_onlymonster_mapping (onlymonster_id, display_names) VALUES (%s, %s) ON CONFLICT (onlymonster_id) DO UPDATE SET display_names = EXCLUDED.display_names",
            (str(onlymonster_id).strip(), json.dumps(names, ensure_ascii=False)),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def delete_chatter_onlymonster_mapping(onlymonster_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM chatter_onlymonster_mapping WHERE onlymonster_id = %s", (str(onlymonster_id),))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass