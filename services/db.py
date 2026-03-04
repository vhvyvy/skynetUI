import calendar
import streamlit as st
import pandas as pd
import psycopg2


# =====================================================
# Подключение
# =====================================================

@st.cache_resource
def get_connection():
    kwargs = dict(
        host=st.secrets["db_host"],
        port=int(st.secrets.get("db_port", 5432)),
        database=st.secrets["db_name"],
        user=st.secrets["db_user"],
        password=st.secrets["db_password"],
    )
    # Neon и другие облачные БД требуют SSL
    if st.secrets.get("db_host", "").endswith(".neon.tech"):
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