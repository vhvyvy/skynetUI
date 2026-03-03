import streamlit as st
import plotly.express as px
from datetime import datetime
import calendar


def render(transactions_df, expenses_df, metrics, selected_year=None, selected_month=None):
    st.title("Общий финансовый обзор")

    today = datetime.today()
    is_current_month = (
        selected_year == today.year
        and selected_month == today.month
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Выручка", f"${metrics['revenue']:,.2f}")
    col2.metric("Расходы", f"${metrics['expenses']:,.2f}")
    col3.metric("Чистая прибыль", f"${metrics['net']:,.2f}")
    col4.metric("Маржинальность", f"{metrics['margin']:.2f}%")

    # Прогноз на конец месяца — только для текущего месяца
    if is_current_month and selected_year and selected_month:
        days_in_month = calendar.monthrange(selected_year, selected_month)[1]
        days_elapsed = min(today.day, days_in_month)
        if days_elapsed >= 1:
            factor = days_in_month / days_elapsed
            f_rev = metrics["revenue"] * factor
            f_exp = metrics["expenses"] * factor
            f_net = metrics["net"] * factor
            f_margin = (f_net / f_rev * 100) if f_rev > 0 else 0
            st.caption(f"📅 Прогноз на конец месяца (на текущем темпе за {days_elapsed} дн.)")
            st.markdown(
                f"""
                <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.5rem;">
                    <span style="background: rgba(151, 166, 195, 0.25); padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.95rem;">💰 Выручка ~${f_rev:,.0f}</span>
                    <span style="background: rgba(151, 166, 195, 0.25); padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.95rem;">📤 Расходы ~${f_exp:,.0f}</span>
                    <span style="background: rgba(151, 166, 195, 0.25); padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.95rem;">💵 Прибыль ~${f_net:,.0f}</span>
                    <span style="background: rgba(151, 166, 195, 0.25); padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.95rem;">📊 Маржа ~{f_margin:.1f}%</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    retention = metrics.get("retention_income", 0)
    plan_avg = metrics.get("plan_completion_avg")
    if retention > 0:
        st.caption(f"💰 Retention 2.5% (с model+chatter): +${retention:,.2f} к прибыли агентства. Выключите в Настройках, чтобы увидеть разницу.")
    if plan_avg is not None:
        st.caption(f"📋 Чаттер выполнил план на **{plan_avg:.1f}%** — % чаттера рассчитан по выполнению плана по моделям.")

    st.divider()

    revenue = metrics["revenue"]

    if revenue <= 0:
        st.warning("Нет данных по выручке.")
        return

    agency_base = metrics.get("agency_base", revenue - metrics["model_cut"] - metrics["chatter_cut"] - metrics["admin_cut"] - metrics["withdraw_cut"])
    retention = metrics.get("retention_income", 0)

    st.subheader("Распределение выручки")

    cat_names = ["Модель", "Чаттер", "Админы", "Вывод"]
    cat_values = [metrics["model_cut"], metrics["chatter_cut"], metrics["admin_cut"], metrics["withdraw_cut"]]
    if retention > 0:
        cat_names.extend(["Retention 2.5%", "Агентство (база)"])
        cat_values.extend([retention, agency_base])
    else:
        cat_names.append("Агентство (до расходов)")
        cat_values.append(agency_base + retention)

    data = {"Категория": cat_names, "Сумма": cat_values}

    fig = px.pie(
        data,
        names="Категория",
        values="Сумма",
        hole=0.6
    )

    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)