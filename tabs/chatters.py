import streamlit as st
import pandas as pd
import plotly.express as px



def render(transactions_df, expenses_df, metrics, plan_metrics=None, selected_year=None, selected_month=None):
    st.title("💬 Чаттеры")
    st.caption("КПИ чаттеров за выбранный месяц")

    if transactions_df is None or transactions_df.empty:
        st.info("Нет транзакций за выбранный период.")
        return

    if "chatter" not in transactions_df.columns:
        st.warning("В данных нет колонки «chatter».")
        return

    df = transactions_df.copy()
    df["chatter"] = df["chatter"].fillna("— (без чаттера)").astype(str).str.strip()
    df.loc[df["chatter"] == "", "chatter"] = "— (без чаттера)"

    chatter_pct = st.session_state.get("chatter_percent", 25)
    total_revenue = metrics["revenue"]
    use_plans = plan_metrics and plan_metrics.get("by_model")
    by_model = plan_metrics.get("by_model", {}) if plan_metrics else {}

    # Расчётная оплата: при планах — по % выполнения плана модели; иначе — фикс %
    if use_plans and "model" in df.columns:
        df = df.copy()
        df["_model"] = df["model"].fillna("—").astype(str).str.strip()
        df["_chatter_pct"] = df["_model"].map(
            lambda m: by_model.get(m, {}).get("chatter_pct", chatter_pct)
        )
        df["_chatter_cut"] = df["amount"] * df["_chatter_pct"] / 100
        chatter_by_chatter = df.groupby("chatter", dropna=False)["_chatter_cut"].sum()
    else:
        chatter_by_chatter = df.groupby("chatter", dropna=False)["amount"].sum() * chatter_pct / 100

    # KPI по чаттерам
    kpi = (
        df.groupby("chatter", dropna=False)
        .agg(
            Выручка=("amount", "sum"),
            Транзакций=("amount", "count"),
        )
        .reset_index()
    )
    kpi["Средний чек"] = (kpi["Выручка"] / kpi["Транзакций"]).round(2)
    kpi["Доля выручки %"] = (kpi["Выручка"] / total_revenue * 100).round(1) if total_revenue > 0 else 0
    kpi["Расчётная оплата"] = kpi["chatter"].map(chatter_by_chatter).fillna(0).round(2)
    kpi = kpi.sort_values("Выручка", ascending=False)

    # Сводка
    plan_info = ""
    if use_plans and plan_metrics and plan_metrics.get("plan_completion_avg") is not None:
        plan_info = f" Чаттер выполнил план на **{plan_metrics['plan_completion_avg']:.1f}%**."
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Чаттеров", len(kpi))
    col2.metric("Выручка чаттеров", f"${kpi['Выручка'].sum():,.2f}")
    col3.metric("Транзакций (выходы)", int(kpi["Транзакций"].sum()))
    col4.metric("Средний чек (средний выход)", f"${kpi['Выручка'].sum() / kpi['Транзакций'].sum():,.2f}" if kpi["Транзакций"].sum() > 0 else "—")
    if plan_info:
        st.caption(plan_info)

    st.divider()

    # Графики
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Выручка по чаттерам")
        fig_bar = px.bar(
            kpi,
            x="chatter",
            y="Выручка",
            text_auto=",.0f",
        )
        fig_bar.update_layout(template="plotly_dark", xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        st.subheader("Доля выручки")
        fig_pie = px.pie(
            kpi,
            names="chatter",
            values="Выручка",
            hole=0.5,
        )
        fig_pie.update_layout(template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

    st.caption("Подробные KPI — вкладка **KPI**.")

    st.divider()

    # Таблица выручки и оплаты
    st.subheader("Выручка и расчётная оплата")
    if use_plans:
        st.caption("Расчётная оплата — по выполнению плана по моделям (50%→20%, …, 100%→25%)")
    else:
        st.caption(f"Расчётная оплата — {chatter_pct}% от выручки чаттера (из Настроек)")
    pay_cols = ["chatter", "Выручка", "Транзакций", "Средний чек", "Доля выручки %", "Расчётная оплата"]
    pay_cols = [c for c in pay_cols if c in kpi.columns]
    pay_display = kpi[pay_cols].rename(columns={
        "chatter": "Чаттер",
        "Транзакций": "Транзакций (выходы)",
        "Средний чек": "Средний чек (средний выход)",
    })
    st.dataframe(
        pay_display.style.format({
            "Выручка": "${:,.2f}", "Средний чек (средний выход)": "${:,.2f}",
            "Доля выручки %": "{:.1f}%", "Расчётная оплата": "${:,.2f}",
        }, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )
