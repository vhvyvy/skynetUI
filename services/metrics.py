import pandas as pd


RETENTION_PCT = 2.5  # % от model+chatter, который забирает агентство (с января)


def calculate_metrics(
    transactions_df,
    expenses_df,
    chatter_percent,
    admin_percent,
    model_percent,
    withdraw_percent,
    use_withdraw,
    use_retention=False,
    plan_metrics=None
):
    # Ensure DataFrames are not None and contain 'amount' column
    total_revenue = 0
    if transactions_df is not None and not transactions_df.empty and 'amount' in transactions_df.columns:
        total_revenue = transactions_df["amount"].sum()

    total_expenses = 0
    if expenses_df is not None and not expenses_df.empty and 'amount' in expenses_df.columns:
        total_expenses = expenses_df["amount"].sum()

    # Validate percent inputs (to prevent crashes)
    try:
        chatter_percent = float(chatter_percent)
    except (ValueError, TypeError):
        chatter_percent = 0.0
    try:
        admin_percent = float(admin_percent)
    except (ValueError, TypeError):
        admin_percent = 0.0
    try:
        model_percent = float(model_percent)
    except (ValueError, TypeError):
        model_percent = 0.0
    try:
        withdraw_percent = float(withdraw_percent)
    except (ValueError, TypeError):
        withdraw_percent = 0.0

    # Чаттер: из планов (если есть) или фикс %
    if plan_metrics and plan_metrics.get("by_model"):
        chatter_amount = plan_metrics["total_chatter_cut"]
    else:
        chatter_amount = total_revenue * chatter_percent / 100
    admin_amount = total_revenue * admin_percent / 100
    model_amount = total_revenue * model_percent / 100
    withdraw_amount = (
        total_revenue * withdraw_percent / 100
        if use_withdraw
        else 0
    )

    agency_base = (
        total_revenue
        - chatter_amount
        - admin_amount
        - model_amount
        - withdraw_amount
    )

    # 2.5% от model+chatter забирает агентство (с января)
    retention_income = 0.0
    if use_retention and (model_amount + chatter_amount) > 0:
        retention_income = (model_amount + chatter_amount) * RETENTION_PCT / 100
    agency_amount = agency_base + retention_income

    net_profit = agency_amount - total_expenses

    margin = (
        (net_profit / total_revenue) * 100
        if total_revenue > 0
        else 0
    )

    return {
        # Старые ключи (для overview)
        "revenue": total_revenue,
        "expenses": total_expenses,
        "net": net_profit,
        "net_profit": net_profit,
        "margin": margin,

        # Вот эти ключи тебе сейчас нужны:
        "model_cut": model_amount,
        "chatter_cut": chatter_amount,
        "admin_cut": admin_amount,
        "withdraw_cut": withdraw_amount,
        "agency_cut": agency_amount,

        # Для круговой диаграммы
        "distribution": {
            "agency": agency_amount,
            "chatter": chatter_amount,
            "model": model_amount,
            "admin": admin_amount,
            "withdraw": withdraw_amount,
        },
        "retention_income": retention_income,
        "agency_base": agency_base,
        "plan_metrics": plan_metrics,
        "plan_completion_avg": plan_metrics.get("plan_completion_avg") if plan_metrics else None,
    }