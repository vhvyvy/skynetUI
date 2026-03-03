import streamlit as st


def calculate_metrics(transactions_df, expenses_df):
    revenue = transactions_df["amount"].sum() if not transactions_df.empty else 0
    expenses = expenses_df["amount"].sum() if not expenses_df.empty else 0

    # Берем проценты из session_state
    chatter_percent = st.session_state.get("chatter_percent", 0)
    admin_percent = st.session_state.get("admin_percent", 0)
    model_percent = st.session_state.get("model_percent", 0)
    withdraw_percent = st.session_state.get("withdraw_percent", 0)
    use_withdraw = st.session_state.get("use_withdraw", False)

    # Расчёт удержаний
    chatter_cut = revenue * chatter_percent / 100
    admin_cut = revenue * admin_percent / 100
    model_cut = revenue * model_percent / 100

    withdraw_cut = 0
    if use_withdraw:
        withdraw_cut = revenue * withdraw_percent / 100

    # Чистая прибыль агентства
    net = (
        revenue
        - chatter_cut
        - admin_cut
        - model_cut
        - withdraw_cut
        - expenses
    )

    margin = (net / revenue * 100) if revenue > 0 else 0

    return {
        "revenue": revenue,
        "expenses": expenses,
        "net": net,
        "margin": margin,
        "chatter_cut": chatter_cut,
        "admin_cut": admin_cut,
        "model_cut": model_cut,
        "withdraw_cut": withdraw_cut,
    }