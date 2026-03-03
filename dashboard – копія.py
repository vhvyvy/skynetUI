# ==========================================
# SKYNET LEVEL 13.6 – AI BUTTONS EDITION
# Stable OF Strategic Intelligence System
# ==========================================

import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
from dotenv import load_dotenv
from openai import OpenAI

# ------------------------------------------------
# CONFIG
# ------------------------------------------------
st.set_page_config(page_title="Skynet OF Production", layout="wide")
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "ai_memory" not in st.session_state:
    st.session_state.ai_memory = []

# ------------------------------------------------
# DATABASE
# ------------------------------------------------
conn = psycopg2.connect(
    host=os.getenv("PG_HOST"),
    port=os.getenv("PG_PORT"),
    dbname=os.getenv("PG_DB"),
    user=os.getenv("PG_USER"),
    password=os.getenv("PG_PASSWORD"),
)

@st.cache_data
def load_data():
    return pd.read_sql(
        "SELECT date, model, chatter, amount, shift_id FROM transactions",
        conn
    )

df = load_data()

# ------------------------------------------------
# SAFE CLEANING
# ------------------------------------------------
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date"])

df["model"] = df["model"].fillna("Unknown").astype(str).str.strip()
df["chatter"] = df["chatter"].fillna("Unknown").astype(str).str.strip()
df["shift_id"] = df["shift_id"].fillna("No Shift").astype(str).str.strip()

df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.dropna(subset=["amount"])

df["month"] = df["date"].dt.to_period("M").astype(str)

if df.empty:
    st.error("Нет данных после очистки.")
    st.stop()

# ------------------------------------------------
# SIDEBAR
# ------------------------------------------------
st.sidebar.title("⚙ Фильтры")

months = sorted(df["month"].unique())
selected_month = st.sidebar.selectbox("Месяц", sorted(months, reverse=True))

selected_model = st.sidebar.multiselect(
    "Модели",
    sorted(df["model"].unique())
)

selected_shift = st.sidebar.multiselect(
    "Смены",
    sorted(df["shift_id"].unique())
)

current_index = months.index(selected_month)
previous_month = months[current_index - 1] if current_index > 0 else None

current = df[df["month"] == selected_month]
previous = df[df["month"] == previous_month] if previous_month else pd.DataFrame()

if selected_model:
    current = current[current["model"].isin(selected_model)]
    previous = previous[previous["model"].isin(selected_model)]

if selected_shift:
    current = current[current["shift_id"].isin(selected_shift)]
    previous = previous[previous["shift_id"].isin(selected_shift)]

# ------------------------------------------------
# METRICS
# ------------------------------------------------
cur_rev = current["amount"].sum()
cur_trx = len(current)
cur_avg = current["amount"].mean() if cur_trx > 0 else 0
prev_rev = previous["amount"].sum() if not previous.empty else 0

def pct(a, b):
    if b == 0:
        return None
    return ((a - b) / b) * 100

rev_delta = pct(cur_rev, prev_rev)

daily = current.groupby("date")["amount"].sum().reset_index()
volatility = daily["amount"].std() if not daily.empty else 0

# ------------------------------------------------
# KPI TABLES
# ------------------------------------------------
model_kpi = current.groupby("model").agg(
    revenue=("amount", "sum"),
    transactions=("amount", "count"),
    avg_check=("amount", "mean")
).reset_index()

chatter_kpi = current.groupby("chatter").agg(
    revenue=("amount", "sum"),
    transactions=("amount", "count"),
    avg_check=("amount", "mean")
).reset_index()

top_model_share = (
    model_kpi["revenue"].max() / cur_rev * 100
    if not model_kpi.empty and cur_rev > 0 else 0
)

# ------------------------------------------------
# BURNOUT INDEX
# ------------------------------------------------
if previous_month and not previous.empty:
    prev_chatter = previous.groupby("chatter").agg(
        prev_rev=("amount", "sum"),
        prev_trx=("amount", "count")
    ).reset_index()

    chatter_kpi = chatter_kpi.merge(prev_chatter, on="chatter", how="left")

    def safe_pct(a, b):
        if b == 0 or pd.isna(b):
            return 0
        return (a - b) / b

    chatter_kpi["rev_change"] = chatter_kpi.apply(
        lambda x: safe_pct(x["revenue"], x["prev_rev"]), axis=1
    )

    chatter_kpi["trx_change"] = chatter_kpi.apply(
        lambda x: safe_pct(x["transactions"], x["prev_trx"]), axis=1
    )

    chatter_kpi["burnout_score"] = (
        (chatter_kpi["rev_change"] < -0.2).astype(int) +
        (chatter_kpi["trx_change"] < -0.2).astype(int)
    ) * 50
else:
    chatter_kpi["burnout_score"] = 0

# ------------------------------------------------
# SHIFT POWER INDEX
# ------------------------------------------------
shift_stats = current.groupby("shift_id").agg(
    revenue=("amount", "sum"),
    trx=("amount", "count"),
    avg=("amount", "mean")
).reset_index()

if not shift_stats.empty and cur_avg > 0:
    shift_stats["power_index"] = (
        (shift_stats["revenue"] / shift_stats["revenue"].mean()) *
        (shift_stats["avg"] / cur_avg)
    )
else:
    shift_stats["power_index"] = 0

# ------------------------------------------------
# TABS
# ------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Обзор", "🏆 KPI", "⚠ Риски", "🔮 Лаборатория", "🧠 AI Центр"]
)

# =================================================
# OVERVIEW
# =================================================
with tab1:
    st.title("👑 Skynet OF Strategic Center")

    col1, col2, col3 = st.columns(3)
    col1.metric("Выручка", f"${cur_rev:,.2f}",
                f"{rev_delta:.2f}%" if rev_delta else None)
    col2.metric("Транзакции", cur_trx)
    col3.metric("Средний чек", f"${cur_avg:,.2f}")

    st.metric("🔥 Зависимость от топ-модели", f"{top_model_share:.2f}%")

    if not daily.empty:
        fig = px.line(daily, x="date", y="amount")
        st.plotly_chart(fig, use_container_width=True)

# =================================================
# KPI
# =================================================
with tab2:
    st.subheader("🏆 KPI – Модели")
    st.dataframe(model_kpi.sort_values("revenue", ascending=False))

    st.subheader("💬 KPI – Чаттеры")
    st.dataframe(chatter_kpi.sort_values("revenue", ascending=False))

    st.subheader("🔥 Burnout индекс")
    st.dataframe(
        chatter_kpi[["chatter", "revenue", "burnout_score"]]
        .sort_values("burnout_score", ascending=False)
    )

# =================================================
# RISKS
# =================================================
with tab3:
    st.metric("⚠ Волатильность", f"${volatility:,.2f}")

    st.subheader("⚡ Shift Power Index")
    st.dataframe(
        shift_stats.sort_values("power_index", ascending=False)
    )

# =================================================
# LAB
# =================================================
with tab4:
    st.subheader("🔮 Лаборатория")

    col1, col2 = st.columns(2)

    new_avg = col1.slider("Средний чек ($)", 10.0, 300.0,
                          float(cur_avg), 1.0)

    new_trx = col2.slider("Транзакции",
                          1,
                          int(cur_trx * 2 + 50) if cur_trx > 0 else 50,
                          int(cur_trx) if cur_trx > 0 else 1)

    simulated = new_avg * new_trx
    delta_sim = pct(simulated, cur_rev)

    st.metric("Смоделированная выручка",
              f"${simulated:,.2f}",
              f"{delta_sim:.2f}%" if delta_sim else None)

    st.subheader("🧨 Стресс-тест топ-модели")
    drop = st.slider("Падение топ-модели (%)", 0, 100, 30)

    if not model_kpi.empty:
        top_rev = model_kpi["revenue"].max()
        loss = top_rev * (drop / 100)
        st.metric("Выручка при падении",
                  f"${cur_rev - loss:,.2f}",
                  f"-${loss:,.2f}")

    st.subheader("💰 Стоимость роста среднего чека")
    col1, col2, col3 = st.columns(3)
    col1.metric("+1$", f"+${cur_trx * 1:,.2f}")
    col2.metric("+5$", f"+${cur_trx * 5:,.2f}")
    col3.metric("+10$", f"+${cur_trx * 10:,.2f}")

# =================================================
# AI CENTER WITH BUTTONS
# =================================================
with tab5:
    st.subheader("🧠 AI Центр – OF Strategic Mode")

    col1, col2, col3 = st.columns(3)
    col4, col5 = st.columns(2)

    btn_models = col1.button("📊 Анализ моделей")
    btn_chatters = col2.button("💬 Анализ чаттеров")
    btn_risk = col3.button("⚠ Поиск рисков")
    btn_burnout = col4.button("🔥 Кто выгорает?")
    btn_ppv = col5.button("💰 Как поднять PPV?")

    question = st.text_input("Задай стратегический вопрос")

    if btn_models:
        question = "Проанализируй модели как владелец OF агентства"
    if btn_chatters:
        question = "Проанализируй чаттеров, кто растёт и кто проседает"
    if btn_risk:
        question = "Определи главные риски агентства"
    if btn_burnout:
        question = "Есть ли признаки выгорания?"
    if btn_ppv:
        question = "Как увеличить средний чек и PPV?"

    if question:
        st.session_state.ai_memory.append(
            {"role": "user", "content": question}
        )

        context = f"""
OnlyFans агентство.

Выручка: {cur_rev}
Средний чек: {cur_avg}
Транзакции: {cur_trx}
Волатильность: {volatility}
Зависимость от топ модели: {top_model_share}%

МОДЕЛИ:
{model_kpi.to_string(index=False)}

ЧАТТЕРЫ:
{chatter_kpi.to_string(index=False)}
"""

        messages = [
            {
                "role": "system",
                "content": """
Ты стратег OnlyFans агентства.
Говори конкретно.
Анализируй LTV, PPV, удержание, смены, выгорание.
"""
            },
            {"role": "user", "content": context}
        ] + st.session_state.ai_memory

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.25
        )

        reply = response.choices[0].message.content

        st.session_state.ai_memory.append(
            {"role": "assistant", "content": reply}
        )

        st.markdown("### 🔎 Стратегический анализ")
        st.write(reply)

st.success("🚀 LEVEL 13.6 – AI BUTTONS EDITION АКТИВИРОВАН")