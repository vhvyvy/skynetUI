"""
KPI админов — по сменам. 3 админа = 3 смены.
Метрики: выручка под сменой, транзакции, средний чек, расчётная оплата (admin %), продуктивность.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from services.db import load_shifts


def render(transactions_df, metrics, selected_year=None, selected_month=None):
    st.title("👥 KPI админов")
    st.caption("Админы = смены. Каждая смена ведётся одним админом. Метрики по выручке под сменой.")

    if transactions_df is None or transactions_df.empty:
        st.info("Нет транзакций за выбранный период.")
        return

    df = transactions_df.copy()
    shift_names = load_shifts()

    # Группируем по смене: shift_id или shift_name
    df["shift"] = df["shift_id"].fillna(df.get("shift_name", pd.NA))
    df["shift"] = df["shift"].fillna("— Без смены").astype(str).str.strip()
    df.loc[df["shift"] == "", "shift"] = "— Без смены"
    # Если shift_id — UUID, резолвим имя из shifts
    df["shift_display"] = df["shift"].map(lambda x: shift_names.get(str(x), x) if str(x) != "— Без смены" else x)

    admin_pct = st.session_state.get("admin_percent", 9) / 100
    total_revenue = df["amount"].sum()

    # Агрегация по смене
    by_shift = (
        df.groupby("shift_display", dropna=False)
        .agg(
            Выручка=("amount", "sum"),
            Транзакций=("amount", "count"),
            Уникальных_дат=("date", "nunique"),
        )
        .reset_index()
    )
    by_shift["Средний чек"] = (by_shift["Выручка"] / by_shift["Транзакций"]).round(2)
    by_shift["Расчётная оплата (admin %)"] = (by_shift["Выручка"] * admin_pct).round(2)
    by_shift["Доля выручки %"] = (by_shift["Выручка"] / total_revenue * 100).round(1) if total_revenue > 0 else 0
    # Продуктивность: выручка на активный день (сколько $ в среднем за смену)
    by_shift["Продуктивность $/день"] = (by_shift["Выручка"] / by_shift["Уникальных_дат"]).round(2)
    by_shift = by_shift.sort_values("Выручка", ascending=False)

    # Сводка
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Смен с данными", len(by_shift))
    col2.metric("Общая выручка", f"${total_revenue:,.2f}")
    col3.metric("Admin %", f"{admin_pct*100:.0f}%")
    col4.metric("Итого админам", f"${by_shift['Расчётная оплата (admin %)'].sum():,.2f}")

    st.divider()

    # Таблица
    display_df = by_shift.rename(columns={
        "shift_display": "Смена / Админ",
        "Выручка": "Выручка",
        "Транзакций": "Транзакций",
        "Средний чек": "Ср. чек",
        "Расчётная оплата (admin %)": "Расчётная оплата",
        "Доля выручки %": "Доля %",
        "Уникальных_дат": "Активных дней",
        "Продуктивность $/день": "Продуктивность $/день",
    })[["Смена / Админ", "Выручка", "Транзакций", "Ср. чек", "Активных дней", "Продуктивность $/день", "Доля %", "Расчётная оплата"]]
    st.dataframe(
        display_df.style.format({
            "Выручка": "${:,.2f}",
            "Ср. чек": "${:,.2f}",
            "Продуктивность $/день": "${:,.2f}",
            "Доля %": "{:.1f}%",
            "Расчётная оплата": "${:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Выручка по сменам")
    fig = px.bar(
        by_shift,
        x="shift_display",
        y="Выручка",
        text_auto=",.0f",
        labels={"shift_display": "Смена / Админ", "Выручка": "Выручка ($)"},
    )
    fig.update_layout(template="plotly_dark", xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Продуктивность $/день — средняя выручка за день, когда админ работал. Выше = больше объём за смену.")
