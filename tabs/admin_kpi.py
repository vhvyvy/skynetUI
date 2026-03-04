"""
KPI админов — по сменам. 3 админа = 3 смены.
Метрики: выручка, транзакции, чаттеры, модели, KPI чаттеров смены, выполнение плана.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from services.db import load_shifts
from services.chatter_kpi import get_kpi_for_merge


def render(transactions_df, metrics, plan_metrics=None, selected_year=None, selected_month=None):
    st.title("👥 KPI админов")
    st.caption("Админы = смены. Каждая смена ведётся одним админом. Транзакции без смены не учитываются.")

    if transactions_df is None or transactions_df.empty:
        st.info("Нет транзакций за выбранный период.")
        return

    df = transactions_df.copy()
    shift_names = load_shifts()

    # Группируем по смене: shift_id или shift_name
    df["shift"] = df["shift_id"].fillna(df.get("shift_name", pd.NA))
    df["shift"] = df["shift"].fillna("").astype(str).str.strip()

    # Исключаем транзакции без смены
    df = df[df["shift"] != ""].copy()
    if df.empty:
        st.info("Нет транзакций с указанной сменой. Убедитесь, что в Notion заполнено поле «Смена».")
        return

    df["shift_display"] = df["shift"].map(lambda x: shift_names.get(str(x), x))

    admin_pct = st.session_state.get("admin_percent", 9) / 100
    total_revenue = df["amount"].sum()

    # Базовая агрегация по смене
    by_shift = (
        df.groupby("shift_display", dropna=False)
        .agg(
            Выручка=("amount", "sum"),
            Транзакций=("amount", "count"),
            Уникальных_дат=("date", "nunique"),
            Моделей=("model", "nunique"),
            Чаттеров=("chatter", "nunique"),
        )
        .reset_index()
    )
    by_shift["Средний чек"] = (by_shift["Выручка"] / by_shift["Транзакций"]).round(2)
    by_shift["Расчётная оплата"] = (by_shift["Выручка"] * admin_pct).round(2)
    by_shift["Доля %"] = (by_shift["Выручка"] / total_revenue * 100).round(1) if total_revenue > 0 else 0
    by_shift["Продуктивность $/день"] = by_shift.apply(
        lambda r: round(r["Выручка"] / r["Уникальных_дат"], 2) if r["Уникальных_дат"] > 0 else None, axis=1
    )
    by_shift["Выручка / чаттер"] = by_shift.apply(
        lambda r: round(r["Выручка"] / r["Чаттеров"], 2) if r["Чаттеров"] > 0 else None, axis=1
    )
    by_shift["Выручка / модель"] = by_shift.apply(
        lambda r: round(r["Выручка"] / r["Моделей"], 2) if r["Моделей"] > 0 else None, axis=1
    )

    # KPI чаттеров смены (PPV Open Rate, APV, Total Chats)
    kpi_by_id, name_to_id = get_kpi_for_merge(selected_year or 2025, selected_month or 1) if selected_year and selected_month else ({}, {})
    by_shift["Ср. PPV Open Rate %"] = None
    by_shift["Ср. APV"] = None
    by_shift["Total Chats (сумма)"] = None

    for idx, row in by_shift.iterrows():
        shift_name = row["shift_display"]
        shift_df = df[df["shift_display"] == shift_name]
        chatters = shift_df["chatter"].dropna().astype(str).str.strip().unique().tolist()
        ppv_vals, apv_vals, chats_vals = [], [], []
        for c in chatters:
            uid = name_to_id.get(c) or c
            k = kpi_by_id.get(uid) or kpi_by_id.get(c)
            if k:
                if k.get("ppv_open_rate") is not None:
                    ppv_vals.append(k["ppv_open_rate"])
                if k.get("apv") is not None:
                    apv_vals.append(k["apv"])
                if k.get("total_chats") is not None:
                    chats_vals.append(k["total_chats"])
        if ppv_vals:
            by_shift.at[idx, "Ср. PPV Open Rate %"] = round(sum(ppv_vals) / len(ppv_vals), 1)
        if apv_vals:
            by_shift.at[idx, "Ср. APV"] = round(sum(apv_vals) / len(apv_vals), 2)
        if chats_vals:
            by_shift.at[idx, "Total Chats (сумма)"] = int(sum(chats_vals))

    # Выполнение плана по моделям смены (средневзвешенное по выручке)
    if plan_metrics and plan_metrics.get("by_model"):
        by_model_plan = plan_metrics["by_model"]
        by_shift["Выполнение плана %"] = None
        for idx, row in by_shift.iterrows():
            shift_name = row["shift_display"]
            shift_df = df[df["shift_display"] == shift_name]
            models_rev = shift_df.groupby("model")["amount"].sum()
            total_shift = models_rev.sum()
            if total_shift <= 0:
                continue
            weighted = 0
            for m, rev in models_rev.items():
                m = str(m).strip()
                d = by_model_plan.get(m, {})
                comp = d.get("completion_pct")
                if comp is not None and rev > 0:
                    weighted += comp * rev
            if weighted > 0:
                by_shift.at[idx, "Выполнение плана %"] = round(weighted / total_shift, 1)

    by_shift = by_shift.sort_values("Выручка", ascending=False)

    # Сводка
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Смен с данными", len(by_shift))
    col2.metric("Общая выручка", f"${total_revenue:,.2f}")
    col3.metric("Admin %", f"{admin_pct*100:.0f}%")
    col4.metric("Итого админам", f"${by_shift['Расчётная оплата'].sum():,.2f}")

    st.divider()

    # Таблица
    display_cols = ["shift_display", "Выручка", "Транзакций", "Чаттеров", "Моделей", "Ср. чек",
                   "Выручка / чаттер", "Выручка / модель", "Активных дней", "Продуктивность $/день"]
    optional = ["Ср. PPV Open Rate %", "Ср. APV", "Total Chats (сумма)", "Выполнение плана %"]
    for c in optional:
        if c in by_shift.columns and by_shift[c].notna().any():
            display_cols.append(c)
    display_cols.extend(["Доля %", "Расчётная оплата"])

    by_shift["Активных дней"] = by_shift["Уникальных_дат"]
    display_df = by_shift[[c for c in display_cols if c in by_shift.columns]].copy()
    display_df = display_df.rename(columns={"shift_display": "Смена / Админ"})

    fmt = {
        "Выручка": "${:,.2f}", "Ср. чек": "${:,.2f}", "Продуктивность $/день": "${:,.2f}",
        "Выручка / чаттер": "${:,.2f}", "Выручка / модель": "${:,.2f}",
        "Расчётная оплата": "${:,.2f}", "Доля %": "{:.1f}%",
    }
    if "Ср. APV" in display_df.columns:
        fmt["Ср. APV"] = "${:,.2f}"
    if "Ср. PPV Open Rate %" in display_df.columns:
        fmt["Ср. PPV Open Rate %"] = "{:.1f}%"
    if "Выполнение плана %" in display_df.columns:
        fmt["Выполнение плана %"] = lambda x: f"{x:.1f}%" if pd.notna(x) else "—"

    st.dataframe(
        display_df.style.format({k: v for k, v in fmt.items() if k in display_df.columns}, na_rep="—"),
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

    st.caption(
        "💡 Продуктивность $/день — выручка на активный день. Выручка/чаттер — эффективность команды. "
        "Ср. PPV Open Rate и APV — средние KPI чаттеров смены (если синхронизированы с Onlymonster)."
    )
