# =====================================================
# SKYNET OF STRATEGIC CENTER — LEVEL 26
# FULL STABLE BUILD (NOT BROKEN THIS TIME)
# =====================================================

import streamlit as st
import psycopg2
import pandas as pd
import plotly.graph_objects as go
import calendar
import os
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------------------------------
# CONFIG
# -----------------------------------------------------

st.set_page_config(page_title="Skynet OF Strategic Center", layout="wide")
load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

# -----------------------------------------------------
# DB CONNECTION
# -----------------------------------------------------

@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )

conn = get_connection()

# -----------------------------------------------------
# LOAD TRANSACTIONS
# -----------------------------------------------------

@st.cache_data
def load_transactions():
    df = pd.read_sql(
        "SELECT date, model, chatter, amount, shift_id FROM transactions WHERE date IS NOT NULL",
        conn
    )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    df["model"] = df["model"].fillna("Неизвестно")
    df["chatter"] = df["chatter"].fillna("Неизвестно")
    df["shift_id"] = df["shift_id"].fillna("Без смены")

    df["month_label"] = df["date"].apply(
        lambda x: f"{calendar.month_name[int(x.month)]} {int(x.year)}"
    )

    return df

df = load_transactions()

# -----------------------------------------------------
# SIDEBAR FILTERS
# -----------------------------------------------------

st.sidebar.title("⚙ Фильтры")

month_options = sorted(df["month_label"].unique(), reverse=True)
selected_month = st.sidebar.selectbox("Месяц", month_options)

selected_models = st.sidebar.multiselect("Модели", sorted(df["model"].unique()))
selected_shifts = st.sidebar.multiselect("Смены", sorted(df["shift_id"].unique()))

retention_toggle = st.sidebar.toggle("Включить удержание 2.5%", value=True)

current = df[df["month_label"] == selected_month]

if selected_models:
    current = current[current["model"].isin(selected_models)]

if selected_shifts:
    current = current[current["shift_id"].isin(selected_shifts)]

cur_rev = float(current["amount"].sum())
cur_trx = int(len(current))
cur_avg = float(current["amount"].mean()) if cur_trx > 0 else 0

# -----------------------------------------------------
# PNL ENGINE
# -----------------------------------------------------

@st.cache_data
def load_pnl(month_label, retention_active):

    month_name, year = month_label.split(" ")
    month_number = list(calendar.month_name).index(month_name)
    year = int(year)

    revenue_query = """
    SELECT model, SUM(amount)::numeric AS revenue
    FROM transactions
    WHERE EXTRACT(MONTH FROM date) = %s
      AND EXTRACT(YEAR FROM date) = %s
    GROUP BY model
    """

    expense_query = """
    SELECT model, SUM(amount)::numeric AS direct_expenses
    FROM expenses
    WHERE EXTRACT(MONTH FROM date) = %s
      AND EXTRACT(YEAR FROM date) = %s
    GROUP BY model
    """

    revenue = pd.read_sql(revenue_query, conn, params=(month_number, year))
    expenses = pd.read_sql(expense_query, conn, params=(month_number, year))

    pnl = revenue.merge(expenses, on="model", how="left")
    pnl["direct_expenses"] = pnl["direct_expenses"].fillna(0)

    pnl["chatter_salary"] = pnl["revenue"] * 0.25
    pnl["model_salary"] = pnl["revenue"] * 0.23
    pnl["admin_salary"] = pnl["revenue"] * 0.09
    pnl["withdrawal_fee"] = pnl["revenue"] * 0.06
    pnl["retention_income"] = pnl["revenue"] * 0.012 if retention_active else 0

    pnl["net_profit"] = (
        pnl["revenue"]
        - pnl["chatter_salary"]
        - pnl["model_salary"]
        - pnl["admin_salary"]
        - pnl["withdrawal_fee"]
        - pnl["direct_expenses"]
        + pnl["retention_income"]
    )

    return pnl

pnl = load_pnl(selected_month, retention_toggle)

# -----------------------------------------------------
# TABS
# -----------------------------------------------------

tab_overview, tab_finance, tab_lab, tab_structure, tab_ai = st.tabs(
    ["📊 Обзор", "💰 Финансы", "🧪 Лаборатория", "📈 Структура", "🧠 AI"]
)

# =====================================================
# OVERVIEW
# =====================================================

with tab_overview:

    st.title("👑 Skynet OF Strategic Center")

    col1, col2, col3 = st.columns(3)
    col1.metric("Выручка", f"${cur_rev:,.2f}")
    col2.metric("Транзакции", cur_trx)
    col3.metric("Средний чек", f"${cur_avg:,.2f}")

    if not current.empty:
        daily = current.groupby("date")["amount"].sum()
        st.line_chart(daily)

# =====================================================
# FINANCE
# =====================================================

with tab_finance:

    total_rev = float(pnl["revenue"].sum())
    total_net = float(pnl["net_profit"].sum())
    margin = (total_net / total_rev * 100) if total_rev > 0 else 0

    st.metric("Фулл выручка", f"${total_rev:,.2f}")
    st.metric("Чистая прибыль", f"${total_net:,.2f}")
    st.metric("Маржа", f"{margin:.2f}%")

    st.dataframe(pnl, use_container_width=True)
    st.bar_chart(pnl.set_index("model")["net_profit"])

# =====================================================
# LAB
# =====================================================

with tab_lab:

    lab1, lab2 = st.tabs(["⚙ Экономика %", "📊 Операционные параметры"])

    base_revenue = float(pnl["revenue"].sum())
    base_net = float(pnl["net_profit"].sum())
    direct_total = float(pnl["direct_expenses"].sum())

    with lab1:

        chatter_pct = st.slider("Чаттер %", 0.0, 50.0, 25.0)
        model_pct = st.slider("Модель %", 0.0, 50.0, 23.0)

        new_net = (
            base_revenue
            - base_revenue * chatter_pct/100
            - base_revenue * model_pct/100
            - base_revenue * 0.09
            - base_revenue * 0.06
            - direct_total
            + (base_revenue * 0.012 if retention_toggle else 0)
        )

        st.metric("Базовая прибыль", f"${base_net:,.2f}")
        st.metric("Новая прибыль", f"${new_net:,.2f}")

    with lab2:

        trx_slider = st.slider("Количество транзакций", 0, 5000, cur_trx)
        avg_slider = st.slider("Средний чек", 0.0, 1000.0, cur_avg)

        sim_revenue = trx_slider * avg_slider

        sim_net = (
            sim_revenue
            - sim_revenue * 0.25
            - sim_revenue * 0.23
            - sim_revenue * 0.09
            - sim_revenue * 0.06
            - direct_total
            + (sim_revenue * 0.012 if retention_toggle else 0)
        )

        st.metric("Симулированная прибыль", f"${sim_net:,.2f}")

# =====================================================
# STRUCTURE
# =====================================================

with tab_structure:

    fig = go.Figure(go.Waterfall(
        measure=["absolute","relative","relative","relative","relative","relative","total"],
        x=["Выручка","Чаттеры","Модели","Админы","Вывод","Direct","Чистая прибыль"],
        y=[
            total_rev,
            -float(pnl["chatter_salary"].sum()),
            -float(pnl["model_salary"].sum()),
            -float(pnl["admin_salary"].sum()),
            -float(pnl["withdrawal_fee"].sum()),
            -float(pnl["direct_expenses"].sum()),
            total_net
        ]
    ))

    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# AI — STABLE OF VERSION
# =====================================================

with tab_ai:

    st.title("🧠 AI Финансовый директор OF")

    if not client:
        st.error("OPENAI_API_KEY не найден")
    else:

        if st.button("📉 Где слабые места в OF модели"):
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role":"system","content":"Ты управляешь OnlyFans агентством."},
                    {"role":"user","content":f"""
                    Выручка: {total_rev}
                    Прибыль: {total_net}
                    Маржа: {margin:.2f}%
                    Чаттеры 25%, Модели 23%, Админы 9%, Вывод 6%, Retention 2.5%.
                    Где слабые места?
                    """}
                ]
            )
            st.write(response.choices[0].message.content)

st.success("🚀 LEVEL 26 — FULL STABLE BUILD АКТИВИРОВАН")