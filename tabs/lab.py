import streamlit as st


RETENTION_PCT = 2.5


def _simulate_metrics(revenue, expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention=False):
    """Расчёт метрик при заданной выручке и расходах."""
    chatter = revenue * chatter_pct / 100
    admin = revenue * admin_pct / 100
    model = revenue * model_pct / 100
    withdraw = revenue * withdraw_pct / 100 if use_withdraw else 0
    agency_base = revenue - chatter - admin - model - withdraw
    retention = (model + chatter) * RETENTION_PCT / 100 if use_retention else 0
    agency = agency_base + retention
    net = agency - expenses
    margin = (net / revenue * 100) if revenue > 0 else 0
    return {"revenue": revenue, "expenses": expenses, "net": net, "margin": margin}


def _render_tab_simulation(cur_trx, cur_revenue, cur_avg, cur_expenses, metrics, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention, month_key, widget_suffix):
    """Вкладка: Симуляция транзакций и среднего чека."""
    default_avg = float(round(cur_avg, 2)) if cur_avg else 0.0
    slider_key = f"lab_slider_trx_{month_key}_{widget_suffix}"
    avg_key = f"lab_input_avg_{month_key}_{widget_suffix}"

    st.subheader("Параметры симуляции")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sim_trx = st.slider("Количество транзакций", 0, max(cur_trx * 3, 5000), cur_trx, key=slider_key, help="Сколько платёжей было бы в месяце")
    with col2:
        sim_avg = st.number_input("Средний чек ($)", 0.0, 5000.0, default_avg, 10.0, "%.2f", key=avg_key, help="Средняя сумма одного платежа")
    with col3:
        st.write("")
        st.write("")
        if st.button("Сбросить", key=f"lab_reset_{month_key}_{widget_suffix}", help="Вернуть к фактическим значениям"):
            st.session_state["lab_reset_pending"] = month_key
            st.rerun()

    sim_revenue = sim_trx * sim_avg
    sim_metrics = _simulate_metrics(sim_revenue, cur_expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention)

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Текущие данные (факт)**")
        st.metric("Выручка", f"${cur_revenue:,.2f}", delta=None)
        st.metric("Чистая прибыль", f"${metrics['net']:,.2f}", delta=None)
    with col_b:
        st.markdown("**Симуляция**")
        delta_rev = sim_revenue - cur_revenue if cur_revenue else None
        delta_net = sim_metrics["net"] - metrics["net"] if cur_revenue else None
        st.metric("Выручка", f"${sim_revenue:,.2f}", delta=f"{delta_rev:+,.2f}" if delta_rev is not None else None)
        st.metric("Чистая прибыль", f"${sim_metrics['net']:,.2f}", delta=f"{delta_net:+,.2f}" if delta_net is not None else None)


def _render_tab_goals(cur_revenue, cur_expenses, cur_trx, cur_avg, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention, metrics):
    """Вкладка: Целевая прибыль — сколько выручки нужно?"""
    st.caption("Введите желаемую прибыль — рассчитаем требуемую выручку и количество транзакций.")

    agency_base_pct = 100 - model_pct - chatter_pct - admin_pct - (withdraw_pct if use_withdraw else 0)
    retention_add = (model_pct + chatter_pct) * (RETENTION_PCT / 100) if use_retention else 0
    agency_pct = agency_base_pct + retention_add
    default_target = float(round(metrics.get("net", 0) or cur_revenue * 0.25, 2))
    target_net = st.number_input("Целевая чистая прибыль ($)", 0.0, 10_000_000.0, default_target, 1000.0, "%.2f", key="lab_target_net")

    # net = agency - expenses = revenue * (agency_pct/100) - expenses
    # revenue = (target_net + expenses) / (agency_pct/100)
    if agency_pct <= 0:
        st.warning("Сумма процентов (модель, чаттер, админ, вывод) ≥ 100% — агентству не остаётся доли.")
    else:
        req_revenue = (target_net + cur_expenses) / (agency_pct / 100)
        req_trx_cur_avg = int(req_revenue / cur_avg) if cur_avg > 0 else 0

        st.metric("Требуемая выручка", f"${req_revenue:,.2f}")
        st.metric("Транзакций (при текущем среднем чеке)", f"{req_trx_cur_avg:,}")
        st.info(f"Чтобы выйти на ${target_net:,.2f} прибыли, нужно выручить ${req_revenue:,.2f} или примерно {req_trx_cur_avg:,} транзакций при текущем среднем чеке.")


def _render_tab_sensitivity(cur_revenue, cur_expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention):
    """Вкладка: Чувствительность к процентам."""
    st.caption("Измените проценты и посмотрите, как изменится прибыль (для текущей выручки и расходов).")

    base_model = st.session_state.get("model_percent", 23)
    base_chatter = st.session_state.get("chatter_percent", 25)
    base_admin = st.session_state.get("admin_percent", 9)
    base_withdraw = st.session_state.get("withdraw_percent", 6)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sim_model = st.slider("Модель %", 0, 50, base_model, 1, key="lab_sens_model")
    with c2:
        sim_chatter = st.slider("Чаттер %", 0, 50, base_chatter, 1, key="lab_sens_chatter")
    with c3:
        sim_admin = st.slider("Админы %", 0, 50, base_admin, 1, key="lab_sens_admin")
    with c4:
        sim_withdraw = st.slider("Вывод %", 0, 50, base_withdraw, 1, key="lab_sens_withdraw")

    sim_metrics = _simulate_metrics(cur_revenue, cur_expenses, sim_model, sim_chatter, sim_admin, sim_withdraw, use_withdraw, use_retention)
    base_metrics = _simulate_metrics(cur_revenue, cur_expenses, base_model, base_chatter, base_admin, base_withdraw, use_withdraw, use_retention)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**При текущих % (из Настроек)**")
        st.metric("Чистая прибыль", f"${base_metrics['net']:,.2f}")
        st.metric("Маржа", f"{base_metrics['margin']:.1f}%")
    with col2:
        st.markdown("**При новых %**")
        delta = sim_metrics["net"] - base_metrics["net"]
        st.metric("Чистая прибыль", f"${sim_metrics['net']:,.2f}", delta=f"{delta:+,.2f}")
        st.metric("Маржа", f"{sim_metrics['margin']:.1f}%")


def _render_tab_scenarios(cur_trx, cur_avg, cur_revenue, cur_expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention, base_net):
    """Вкладка: Быстрые сценарии."""
    st.caption("Выберите сценарий — сразу увидите результат.")

    scenarios = [
        ("+10% транзакций", 1.10, 1.0),
        ("+20% транзакций", 1.20, 1.0),
        ("+10% средний чек", 1.0, 1.10),
        ("+20% средний чек", 1.0, 1.20),
        ("+10% оба", 1.10, 1.10),
        ("+20% оба", 1.20, 1.20),
        ("−10% транзакций", 0.90, 1.0),
        ("−15% оба", 0.85, 0.85),
    ]

    cols = st.columns(4)
    for i, (name, mult_trx, mult_avg) in enumerate(scenarios):
        with cols[i % 4]:
            sim_trx = int(cur_trx * mult_trx)
            sim_avg = round(cur_avg * mult_avg, 2) if cur_avg else 0
            sim_rev = sim_trx * sim_avg
            m = _simulate_metrics(sim_rev, cur_expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention)
            delta_net = m["net"] - base_net
            delta_str = f"{delta_net:+,.0f}" if base_net != 0 else None
            st.metric(name, f"${m['net']:,.0f}", delta=delta_str)


def render(transactions_df, expenses_df, metrics, selected_year=None, selected_month=None):
    st.title("🧪 Лаборатория")
    st.caption("Эксперименты с цифрами — симуляции, цели, сценарии.")

    cur_trx = len(transactions_df) if transactions_df is not None and not transactions_df.empty else 0
    cur_revenue = metrics["revenue"]
    cur_avg = (cur_revenue / cur_trx) if cur_trx > 0 else 0
    cur_expenses = metrics["expenses"]

    model_pct = st.session_state.get("model_percent", 23)
    chatter_pct = st.session_state.get("chatter_percent", 25)
    admin_pct = st.session_state.get("admin_percent", 9)
    withdraw_pct = st.session_state.get("withdraw_percent", 6)
    use_withdraw = st.session_state.get("use_withdraw", True)
    use_retention = st.session_state.get("use_retention", True)

    month_key = f"{selected_year or 0}_{selected_month or 0}"
    reset_counter_key = f"lab_reset_counter_{month_key}"
    if st.session_state.pop("lab_reset_pending", None) == month_key:
        st.session_state[reset_counter_key] = st.session_state.get(reset_counter_key, 0) + 1
        st.rerun()
    widget_suffix = st.session_state.get(reset_counter_key, 0)

    tab_sim, tab_goals, tab_sens, tab_scen = st.tabs([
        "📊 Симуляция",
        "🎯 Цели",
        "📐 Чувствительность %",
        "⚡ Сценарии",
    ])

    with tab_sim:
        _render_tab_simulation(
            cur_trx, cur_revenue, cur_avg, cur_expenses, metrics,
            model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention,
            month_key, widget_suffix
        )

    with tab_goals:
        _render_tab_goals(cur_revenue, cur_expenses, cur_trx, cur_avg, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention, metrics)

    with tab_sens:
        _render_tab_sensitivity(cur_revenue, cur_expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention)

    with tab_scen:
        _render_tab_scenarios(cur_trx, cur_avg, cur_revenue, cur_expenses, model_pct, chatter_pct, admin_pct, withdraw_pct, use_withdraw, use_retention, metrics["net"])