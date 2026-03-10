import streamlit as st
import pandas as pd
from services.plans import get_plans, save_plan, compute_plan_metrics, PLAN_TIERS


def render(transactions_df, expenses_df, metrics, selected_year, selected_month):
    st.title("📋 Планы по моделям")
    st.caption("План влияет на % чаттера: 50%→20%, 60%→21%, 70%→22%, 80%→23%, 90%→24%, 100%→25%")

    if transactions_df is None or transactions_df.empty:
        st.info("Нет транзакций за выбранный период.")
        return

    if "model" not in transactions_df.columns:
        st.warning("В данных нет колонки «model».")
        return

    model_revenues = (
        transactions_df.groupby("model", dropna=False)["amount"]
        .sum()
        .to_dict()
    )
    model_revenues = {str(k).strip() if pd.notna(k) else "—": v for k, v in model_revenues.items()}

    current_plans = get_plans(selected_year, selected_month)

    st.subheader("Планы на выбранный месяц")
    st.caption("Укажите целевой план (выручка) для каждой модели. Сохраняется автоматически.")

    all_models = sorted(set(model_revenues.keys()) | set(current_plans.keys()))
    if not all_models:
        st.info("Нет моделей с данными.")
        return

    new_plans = {}
    for model in all_models:
        rev = model_revenues.get(model, 0)
        current = current_plans.get(model, 0)
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.write(f"**{model}**")
        with col2:
            val = st.number_input(
                "План ($)",
                min_value=0.0,
                value=float(current) if current else 0.0,
                step=500.0,
                key=f"plan_{selected_year}_{selected_month}_{model}".replace(" ", "_"),
                label_visibility="collapsed",
            )
            new_plans[model] = val
        with col3:
            if val > 0:
                pct = (rev / val * 100) if val else 0
                chatter_pct = next((p for m, p in PLAN_TIERS if pct >= m), 20)
                st.caption(f"Выполнено {pct:.1f}% → {chatter_pct}% чаттеру")
            else:
                st.caption("—")

    if st.button("💾 Сохранить планы"):
        for model, val in new_plans.items():
            save_plan(selected_year, selected_month, model, val)
        st.toast("Планы сохранены", icon="✅")
        st.rerun()

    st.divider()

    plan_metrics = compute_plan_metrics(
        {m: model_revenues.get(m, 0) for m in all_models},
        {m: v for m, v in new_plans.items() if v > 0} or current_plans
    )

    st.subheader("Сводка по выполнению плана")
    df = pd.DataFrame([
        {
            "Модель": m,
            "Выручка": plan_metrics["by_model"][m]["revenue"],
            "План": plan_metrics["by_model"][m]["plan"],
            "Выполнение %": plan_metrics["by_model"][m]["completion_pct"],
            "% чаттеру": plan_metrics["by_model"][m]["chatter_pct"],
            "Чаттеру ($)": plan_metrics["by_model"][m]["chatter_cut"],
        }
        for m in plan_metrics["by_model"]
        if plan_metrics["by_model"][m]["plan"] > 0
    ])
    if not df.empty:
        avg = plan_metrics.get("plan_completion_avg")
        if avg is not None:
            st.info(f"Средневзвешенное выполнение плана: **{avg:.1f}%**")
        st.dataframe(
            df.style.format({
                "Выручка": "${:,.2f}",
                "План": "${:,.2f}",
                "Выполнение %": lambda x: f"{x:.1f}%" if pd.notna(x) else "—",
                "Чаттеру ($)": "${:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Добавьте планы выше и сохраните.")
