"""
Детальная аналитика по моделям: выручка, расходы, план, связки.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(transactions_df, expenses_df, metrics, plan_metrics=None, selected_year=None, selected_month=None):
    st.title("📊 Модели")
    st.caption("Детальная аналитика по каждой модели: выручка, расходы, план, чаттеры.")

    if transactions_df is None or transactions_df.empty:
        st.info("Нет транзакций за выбранный период.")
        return

    df = transactions_df.copy()
    df["model"] = df["model"].fillna("— (без модели)").astype(str).str.strip()
    df.loc[df["model"] == "", "model"] = "— (без модели)"

    total_revenue = df["amount"].sum()
    model_pct = st.session_state.get("model_percent", 23) / 100

    # Выручка по моделям
    by_model = (
        df.groupby("model", dropna=False)
        .agg(
            Выручка=("amount", "sum"),
            Транзакций=("amount", "count"),
        )
        .reset_index()
    )
    by_model["Средний чек"] = (by_model["Выручка"] / by_model["Транзакций"]).round(2)
    by_model["Доля выручки %"] = (by_model["Выручка"] / total_revenue * 100).round(1) if total_revenue > 0 else 0
    by_model["Model cut"] = (by_model["Выручка"] * model_pct).round(2)
    by_model = by_model.sort_values("Выручка", ascending=False)

    # Расходы по моделям
    if expenses_df is not None and not expenses_df.empty and "model" in expenses_df.columns:
        exp_df = expenses_df.copy()
        exp_df["model"] = exp_df["model"].fillna("— (без модели)").astype(str).str.strip()
        exp_by_model = exp_df.groupby("model")["amount"].sum().to_dict()
    else:
        exp_by_model = {}
    by_model["Расходы"] = by_model["model"].map(lambda m: exp_by_model.get(m, 0))
    by_model["Чистая (выручка − расходы)"] = (by_model["Выручка"] - by_model["Расходы"]).round(2)

    # План и % чаттера
    plan_data = (plan_metrics or {}).get("by_model") or {}
    by_model["План"] = by_model["model"].map(lambda m: plan_data.get(m, {}).get("plan", 0))
    by_model["Выполнение плана %"] = by_model.apply(
        lambda r: (r["Выручка"] / r["План"] * 100) if r["План"] and r["План"] > 0 else None,
        axis=1,
    )
    by_model["Чаттеру ($)"] = by_model["model"].map(lambda m: plan_data.get(m, {}).get("chatter_cut", 0))
    by_model["Чаттеров"] = by_model["model"].map(
        lambda m: df[df["model"] == m]["chatter"].nunique() if "chatter" in df.columns else 0
    )

    st.subheader("Сводная таблица по моделям")
    display_cols = ["model", "Выручка", "Расходы", "Чистая (выручка − расходы)", "Транзакций", "Средний чек", "Доля выручки %"]
    if plan_data:
        display_cols.extend(["План", "Выполнение плана %", "Чаттеру ($)"])
    display_cols.append("Чаттеров")
    display_cols = [c for c in display_cols if c in by_model.columns]
    display_df = by_model[display_cols].rename(columns={"model": "Модель"})
    fmt_dict = {"Выручка": "${:,.2f}", "Расходы": "${:,.2f}", "Чистая (выручка − расходы)": "${:,.2f}", "Средний чек": "${:,.2f}", "Чаттеру ($)": "${:,.2f}", "План": "${:,.2f}"}
    fmt_dict = {k: v for k, v in fmt_dict.items() if k in display_df.columns}
    fmt_dict["Доля выручки %"] = "{:.1f}%"
    if "Выполнение плана %" in display_df.columns:
        fmt_dict["Выполнение плана %"] = lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
    st.dataframe(
        display_df.style.format(fmt_dict, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # Графики
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Выручка по моделям")
        fig1 = px.bar(
            by_model.head(15),
            x="model",
            y="Выручка",
            text_auto=",.0f",
            labels={"model": "Модель"},
        )
        fig1.update_layout(template="plotly_dark", xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.subheader("Выручка vs Расходы")
        comp = by_model[by_model["Расходы"] > 0].head(10)
        if not comp.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(name="Выручка", x=comp["model"], y=comp["Выручка"], marker_color="steelblue"))
            fig2.add_trace(go.Bar(name="Расходы", x=comp["model"], y=comp["Расходы"], marker_color="coral"))
            fig2.update_layout(barmode="group", template="plotly_dark", xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.caption("Нет моделей с расходами для сравнения.")

    st.divider()

    # Drill-down: выбор модели
    st.subheader("Детали по модели")
    model_options = ["—"] + by_model["model"].tolist()
    chosen = st.selectbox("Выберите модель", model_options, key="models_detail_select")
    if chosen and chosen != "—":
        row = by_model[by_model["model"] == chosen].iloc[0]
        sub = df[df["model"] == chosen]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Выручка", f"${row['Выручка']:,.2f}")
        c2.metric("Расходы", f"${row['Расходы']:,.2f}")
        c3.metric("Чистая", f"${row['Чистая (выручка − расходы)']:,.2f}")
        c4.metric("Транзакций", int(row["Транзакций"]))
        c5.metric("Ср. чек", f"${row['Средний чек']:,.2f}")

        # Чаттеры модели
        if "chatter" in sub.columns and not sub["chatter"].fillna("").eq("").all():
            chatter_rev = sub.groupby("chatter")["amount"].sum().sort_values(ascending=False)
            st.caption("Чаттеры этой модели")
            chatter_df = pd.DataFrame({
                "Чаттер": chatter_rev.index,
                "Выручка": chatter_rev.values,
                "Доля %": (chatter_rev / chatter_rev.sum() * 100).round(1),
            })
            st.dataframe(
                chatter_df.style.format({"Выручка": "${:,.2f}", "Доля %": "{:.1f}%"}),
                use_container_width=True,
                hide_index=True,
            )
        # Расходы по категориям для модели
        if expenses_df is not None and not expenses_df.empty and "model" in expenses_df.columns:
            exp_model = expenses_df[expenses_df["model"].fillna("").astype(str).str.strip() == chosen]
            if not exp_model.empty:
                st.caption("Расходы по категориям")
                exp_cat = exp_model.groupby("category")["amount"].sum().sort_values(ascending=False)
                st.dataframe(
                    pd.DataFrame({"Категория": exp_cat.index, "Сумма": exp_cat.values}).style.format({"Сумма": "${:,.2f}"}),
                    use_container_width=True,
                    hide_index=True,
                )
