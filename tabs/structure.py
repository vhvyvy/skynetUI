import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(transactions_df, expenses_df, metrics, plan_metrics=None):
    st.title("🏗️ Структура")
    st.caption("Модели, чаттеры и связки между ними за выбранный месяц")

    if transactions_df is None or transactions_df.empty:
        st.info("Нет транзакций за выбранный период.")
        return

    df = transactions_df.copy()
    has_model = "model" in df.columns
    has_chatter = "chatter" in df.columns

    if not has_model or not has_chatter:
        st.warning("Для раздела структуры нужны колонки «model» и «chatter».")
        st.caption(f"Выручка: ${metrics['revenue']:,.2f} | Расходы: ${metrics['expenses']:,.2f} | Прибыль: ${metrics['net']:,.2f}")
        return

    df["model"] = df["model"].fillna("— (без модели)").astype(str).str.strip()
    df["chatter"] = df["chatter"].fillna("— (без чаттера)").astype(str).str.strip()
    df.loc[df["model"] == "", "model"] = "— (без модели)"
    df.loc[df["chatter"] == "", "chatter"] = "— (без чаттера)"

    total_revenue = df["amount"].sum()

    # ========== Сводка ==========
    models = df["model"].nunique()
    chatters = df["chatter"].nunique()
    pairs = (
        df.groupby(["model", "chatter"])["amount"]
        .agg(["sum", "count", "mean"])
        .reset_index()
        .rename(columns={"sum": "amount", "count": "transactions", "mean": "avg_check"})
    )
    unique_pairs = len(pairs)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Моделей", models)
    col2.metric("Чаттеров", chatters)
    col3.metric("Связок модель–чаттер", unique_pairs)
    col4.metric("Выручка", f"${total_revenue:,.2f}")
    col5.metric("Ср. выручка на связку", f"${total_revenue / unique_pairs:,.2f}" if unique_pairs else "—")

    st.divider()

    # ========== Концентрация ==========
    st.subheader("Концентрация выручки")
    pairs_sorted = pairs.sort_values("amount", ascending=False).reset_index(drop=True)
    top3_rev = pairs_sorted.head(3)["amount"].sum()
    top5_rev = pairs_sorted.head(5)["amount"].sum()
    top3_pct = (top3_rev / total_revenue * 100) if total_revenue > 0 else 0
    top5_pct = (top5_rev / total_revenue * 100) if total_revenue > 0 else 0

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Топ-3 связки", f"{top3_pct:.1f}% выручки", f"${top3_rev:,.2f}")
    with col_b:
        st.metric("Топ-5 связок", f"{top5_pct:.1f}% выручки", f"${top5_rev:,.2f}")

    # Диаграмма концентрации по моделям
    model_rev = df.groupby("model")["amount"].sum().sort_values(ascending=False)
    top5_models = model_rev.head(5)
    if len(model_rev) > 5:
        rest = pd.Series([model_rev.iloc[5:].sum()], index=["Остальные"])
        conc_data = pd.concat([top5_models, rest])
    else:
        conc_data = top5_models
    fig_conc = px.bar(
        x=conc_data.index.tolist(),
        y=conc_data.values,
        labels={"x": "Модель", "y": "Выручка"},
        text_auto=",.0f",
    )
    fig_conc.update_layout(template="plotly_dark", height=300, showlegend=False)
    st.plotly_chart(fig_conc, use_container_width=True)

    st.divider()

    # ========== Топ пар модель–чаттер (с средним чеком) ==========
    st.subheader("Топ-10 связок модель ↔ чаттер")
    top_pairs = (
        pairs.sort_values("amount", ascending=False)
        .head(10)
        .rename(columns={
            "model": "Модель", "chatter": "Чаттер", "amount": "Выручка",
            "transactions": "Транзакций", "avg_check": "Ср. чек"
        })
    )
    top_pairs["Доля %"] = (top_pairs["Выручка"] / total_revenue * 100).round(1)
    st.dataframe(
        top_pairs[["Модель", "Чаттер", "Выручка", "Транзакций", "Ср. чек", "Доля %"]].style.format({
            "Выручка": "${:,.2f}", "Ср. чек": "${:,.2f}", "Доля %": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ========== Активность ==========
    st.subheader("Активность: транзакции и средний чек")
    by_model = df.groupby("model").agg(
        Выручка=("amount", "sum"),
        Транзакций=("amount", "count"),
    ).reset_index()
    by_model["Ср. чек"] = (by_model["Выручка"] / by_model["Транзакций"]).round(2)
    by_model = by_model.sort_values("Выручка", ascending=False)

    by_chatter = df.groupby("chatter").agg(
        Выручка=("amount", "sum"),
        Транзакций=("amount", "count"),
    ).reset_index()
    by_chatter["Ср. чек"] = (by_chatter["Выручка"] / by_chatter["Транзакций"]).round(2)
    by_chatter = by_chatter.sort_values("Выручка", ascending=False)

    col_m, col_c = st.columns(2)
    with col_m:
        st.caption("По моделям")
        st.dataframe(
            by_model.style.format({"Выручка": "${:,.2f}", "Ср. чек": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )
    with col_c:
        st.caption("По чаттерам")
        st.dataframe(
            by_chatter.style.format({"Выручка": "${:,.2f}", "Ср. чек": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # ========== Чаттер на несколько моделей ==========
    st.subheader("Чаттеры на нескольких моделях")
    chatter_models = df.groupby("chatter")["model"].nunique().sort_values(ascending=False)
    multi_chatters = chatter_models[chatter_models > 1]
    if len(multi_chatters) > 0:
        multi_df = pd.DataFrame({
            "Чаттер": multi_chatters.index,
            "Моделей": multi_chatters.values,
        })
        chatter_totals = df.groupby("chatter")["amount"].sum()
        multi_df["Выручка"] = multi_df["Чаттер"].map(chatter_totals)
        multi_df = multi_df.sort_values("Выручка", ascending=False)
        st.dataframe(
            multi_df.style.format({"Выручка": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Нет чаттеров, работающих с несколькими моделями.")

    st.divider()

    # ========== Модель — много чаттеров ==========
    st.subheader("Модели с наибольшим числом чаттеров")
    model_chatters = df.groupby("model")["chatter"].nunique().sort_values(ascending=False)
    model_rev_map = df.groupby("model")["amount"].sum()
    many_df = pd.DataFrame({
        "Модель": model_chatters.index,
        "Чаттеров": model_chatters.values,
    })
    many_df["Выручка"] = many_df["Модель"].map(model_rev_map)
    many_df = many_df.sort_values("Выручка", ascending=False)
    st.dataframe(
        many_df.style.format({"Выручка": "${:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ========== Матрица модель × чаттер ==========
    st.subheader("Матрица модель × чаттер (выручка)")
    pivot = df.pivot_table(
        index="model",
        columns="chatter",
        values="amount",
        aggfunc="sum",
        fill_value=0,
    )
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    pivot = pivot[pivot.sum().sort_values(ascending=False).index]

    fig_heat = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Blues",
            text=[[f"${v:,.0f}" if v > 0 else "" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            textfont={"size": 9},
            hoverongaps=False,
            hovertemplate="%{x} + %{y}<br>$%{z:,.2f}<extra></extra>",
        )
    )
    fig_heat.update_layout(
        template="plotly_dark",
        xaxis={"tickangle": -45, "tickfont": {"size": 10}},
        yaxis={"tickfont": {"size": 10}},
        height=max(400, len(pivot) * 22 + 80),
        margin=dict(l=120, r=20, t=20, b=150),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # ========== Иерархия: модель → чаттеры ==========
    st.subheader("Иерархия: модель → чаттеры")

    by_model_chatter = (
        df.groupby(["model", "chatter"])["amount"]
        .sum()
        .reset_index()
    )
    models_sorted = (
        by_model_chatter.groupby("model")["amount"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    for model in models_sorted:
        subset = by_model_chatter[by_model_chatter["model"] == model].sort_values("amount", ascending=False)
        model_rev = subset["amount"].sum()
        model_pct = (model_rev / total_revenue * 100) if total_revenue > 0 else 0
        with st.expander(f"**{model}** — ${model_rev:,.2f} ({model_pct:.1f}% выручки)"):
            for _, row in subset.iterrows():
                chatter_rev = row["amount"]
                chatter_pct = (chatter_rev / model_rev * 100) if model_rev > 0 else 0
                st.caption(f"  {row['chatter']}: ${chatter_rev:,.2f} ({chatter_pct:.1f}% от модели)")

    st.divider()

    # ========== Связка с планом ==========
    if plan_metrics and plan_metrics.get("by_model"):
        st.subheader("Выполнение плана по моделям")
        by_model_plan = plan_metrics["by_model"]
        plan_rows = []
        for m, d in by_model_plan.items():
            if d["plan"] > 0:
                plan_rows.append({
                    "Модель": m,
                    "Выручка": d["revenue"],
                    "План": d["plan"],
                    "Выполнение %": d["completion_pct"],
                    "% чаттеру": d["chatter_pct"],
                    "Чаттеру ($)": d["chatter_cut"],
                })
        if plan_rows:
            plan_df = pd.DataFrame(plan_rows)
            st.dataframe(
                plan_df.style.format({
                    "Выручка": "${:,.2f}",
                    "План": "${:,.2f}",
                    "Выполнение %": "{:.1f}%",
                    "Чаттеру ($)": "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )
            avg = plan_metrics.get("plan_completion_avg")
            if avg is not None:
                st.caption(f"Средневзвешенное выполнение плана: **{avg:.1f}%** — чаттер получит % по выполнению каждой модели.")

    st.divider()

    # ========== Treemap ==========
    st.subheader("Визуализация структуры")
    treemap_df = by_model_chatter.copy()

    fig_treemap = px.treemap(
        treemap_df,
        path=["model", "chatter"],
        values="amount",
        color="amount",
        color_continuous_scale="Blues",
        hover_data={"amount": ":$,.2f"},
    )
    fig_treemap.update_layout(template="plotly_dark", height=500)
    fig_treemap.update_traces(textposition="middle center")
    st.plotly_chart(fig_treemap, use_container_width=True)
