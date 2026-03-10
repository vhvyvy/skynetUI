import streamlit as st
import pandas as pd
import plotly.express as px


def render(transactions_df, expenses_df, metrics):
    st.title("💰 Финансовый отчет")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Выручка", f"${metrics['revenue']:,.2f}")
    col2.metric("Расходы", f"${metrics['expenses']:,.2f}")
    col3.metric("Чистая прибыль", f"${metrics['net']:,.2f}")
    col4.metric("Маржинальность", f"{metrics['margin']:.2f}%")

    plan_avg = metrics.get("plan_completion_avg")
    if plan_avg is not None:
        st.caption(f"📋 Чаттер выполнил план на **{plan_avg:.1f}%** — % чаттера по выполнению плана по моделям.")

    st.divider()

    # ======================
    # P&L
    # ======================

    st.subheader("P&L отчет")

    pnl_df = pd.DataFrame({
        "Статья": ["Выручка", "Расходы", "Чистая прибыль"],
        "Сумма": [
            metrics["revenue"],
            -metrics["expenses"],
            metrics["net"]
        ]
    })

    st.dataframe(
        pnl_df,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # ======================
    # Обязательные расходы (% от выручки: модели, чаттеры, админы, вывод)
    # ======================

    st.subheader("Обязательные расходы")

    model_pct = st.session_state.get("model_percent", 23)
    chatter_pct = st.session_state.get("chatter_percent", 25)
    admin_pct = st.session_state.get("admin_percent", 9)
    withdraw_pct = st.session_state.get("withdraw_percent", 6)

    plan_avg = metrics.get("plan_completion_avg")
    chatter_label = f"Чаттеры (план {plan_avg:.0f}%)" if plan_avg is not None else "Чаттеры"
    mandatory_rows = ["Модели", chatter_label, "Админы", "Вывод"]
    chatter_pct_display = f"по плану" if plan_avg is not None else f"{chatter_pct}%"
    mandatory_pcts = [f"{model_pct}%", chatter_pct_display, f"{admin_pct}%", f"{withdraw_pct}%"]
    mandatory_vals = [metrics["model_cut"], metrics["chatter_cut"], metrics["admin_cut"], metrics["withdraw_cut"]]
    retention = metrics.get("retention_income", 0)
    if retention > 0:
        mandatory_rows.append("→ Retention 2.5% (агентству)")
        mandatory_pcts.append("")
        mandatory_vals.append(retention)
    mandatory_df = pd.DataFrame({"Статья": mandatory_rows, "%": mandatory_pcts, "Сумма": mandatory_vals})

    mandatory_total = (
        metrics["model_cut"] + metrics["chatter_cut"]
        + metrics["admin_cut"] + metrics["withdraw_cut"]
    )
    st.metric("Итого обязательные расходы", f"${mandatory_total:,.2f}")
    st.dataframe(
        mandatory_df.style.format({"Сумма": "${:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ======================
    # Расходы (из базы — вручную внесённые)
    # ======================

    if not expenses_df.empty:
        st.subheader("Расходы (из базы)")

        col_a, col_b = st.columns(2)
        with col_a:
            category_df = (
                expenses_df
                .groupby("category")["amount"]
                .sum()
                .reset_index()
                .sort_values("amount", ascending=False)
            )
            fig = px.pie(
                category_df,
                names="category",
                values="amount",
                hole=0.6,
                title="По категориям"
            )
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            model_df = (
                expenses_df
                .groupby("model")["amount"]
                .sum()
                .reset_index()
                .sort_values("amount", ascending=False)
            )
            fig2 = px.bar(
                model_df,
                x="model",
                y="amount",
                text_auto=True,
                title="По моделям"
            )
            fig2.update_layout(template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)

        # Вкладки по категориям
        df_cat = expenses_df.copy()
        df_cat["category"] = df_cat["category"].fillna("— (без категории)")
        categories = (
            df_cat.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        tab_names = ["Все"] + [str(c) for c in categories]
        expense_tabs = st.tabs(tab_names)

        for tab_idx, tab in enumerate(expense_tabs):
            with tab:
                if tab_idx == 0:
                    df_tab = df_cat.copy()
                    tab_title = "Все расходы"
                else:
                    cat = categories[tab_idx - 1]
                    df_tab = df_cat[df_cat["category"] == cat].copy()
                    tab_title = str(cat)

                st.subheader(tab_title)

                # Разбивка по моделям
                df_group = df_tab.copy()
                df_group["model"] = df_group["model"].fillna("— (без модели)")
                by_model = (
                    df_group.groupby("model")["amount"]
                    .agg(["sum", "count"])
                    .reset_index()
                )
                by_model.columns = ["Модель", "Сумма", "Записей"]
                by_model = by_model.sort_values("Сумма", ascending=False)

                st.caption("По моделям")
                try:
                    from st_aggrid import AgGrid, GridOptionsBuilder
                    gb = GridOptionsBuilder.from_dataframe(by_model)
                    gb.configure_default_column(sortable=True, filterable=True)
                    AgGrid(by_model, gridOptions=gb.build(), theme="streamlit", height=200, fit_columns_on_grid_load=True, key=f"expense_model_{tab_idx}")
                except ImportError:
                    st.dataframe(by_model.style.format({"Сумма": "${:,.2f}"}), use_container_width=True, hide_index=True)

                st.divider()

                # Детализация: таблица расходов, сгруппирована по модели
                st.caption("Детализация")
                display_cols = ["date", "model", "category", "vendor", "amount"]
                display_cols = [c for c in display_cols if c in df_tab.columns]
                df_display = df_tab[display_cols].copy()
                df_display["model"] = df_display["model"].fillna("—")
                df_display = df_display.sort_values(["model", "date"], ascending=[True, False])
                df_display["date"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d")
                try:
                    from st_aggrid import AgGrid, GridOptionsBuilder
                    gb = GridOptionsBuilder.from_dataframe(df_display)
                    gb.configure_default_column(sortable=True, filterable=True)
                    AgGrid(df_display, gridOptions=gb.build(), theme="streamlit", height=300, fit_columns_on_grid_load=True, key=f"expense_detail_{tab_idx}")
                except ImportError:
                    st.dataframe(df_display.style.format({"amount": "${:,.2f}"}), use_container_width=True, hide_index=True)

    else:
        st.info("Расходов в выбранном периоде нет.")