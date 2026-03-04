"""
Планы по моделям. % чаттера зависит от выполнения плана:
50% → 20%, 60% → 21%, 70% → 22%, 80% → 23%, 90% → 24%, 100%+ → 25%
"""
import streamlit as st

from services.db import get_connection

# (min_completion_pct, chatter_pct)
PLAN_TIERS = [
    (100, 25),
    (90, 24),
    (80, 23),
    (70, 22),
    (60, 21),
    (50, 20),
]
DEFAULT_CHATTER_PCT = 20  # при <50% плана


def get_plans(year, month):
    """Возвращает dict {model: plan_amount} для месяца."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT model, plan_amount FROM plans WHERE year = %s AND month = %s",
            (year, month),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {r[0]: float(r[1]) for r in rows}
    except Exception:
        return {}


def save_plan(year, month, model, plan_amount):
    """Сохраняет план для модели."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO plans (year, month, model, plan_amount)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (year, month, model) DO UPDATE SET plan_amount = EXCLUDED.plan_amount
        """,
        (year, month, model.strip(), float(plan_amount)),
    )
    conn.commit()
    cur.close()
    conn.close()


def completion_to_chatter_pct(completion_pct):
    """Возвращает % чаттера по проценту выполнения плана."""
    if completion_pct is None or completion_pct < 0:
        return DEFAULT_CHATTER_PCT
    for min_pct, chatter_pct in PLAN_TIERS:
        if completion_pct >= min_pct:
            return chatter_pct
    return DEFAULT_CHATTER_PCT


def compute_plan_metrics(model_revenues, model_plans):
    """
    model_revenues: dict {model: revenue}
    model_plans: dict {model: plan_amount}
    Returns: {
        model: {
            revenue, plan, completion_pct, chatter_pct, chatter_cut
        },
        total_chatter_cut,
        plan_completion_summary  # для отображения "план выполнен на X%"
    }
    """
    result = {}
    total_chatter_cut = 0.0
    total_revenue = 0.0
    total_planned_revenue = 0.0
    total_weighted_completion = 0.0

    for model, revenue in model_revenues.items():
        plan = model_plans.get(model) or 0
        completion = (revenue / plan * 100) if plan > 0 else None
        chatter_pct = completion_to_chatter_pct(completion) if plan > 0 else 25  # без плана — 25%
        chatter_cut = revenue * chatter_pct / 100

        result[model] = {
            "revenue": revenue,
            "plan": plan,
            "completion_pct": completion,
            "chatter_pct": chatter_pct,
            "chatter_cut": chatter_cut,
        }
        total_chatter_cut += chatter_cut
        total_revenue += revenue
        if plan > 0:
            total_planned_revenue += plan
            total_weighted_completion += revenue  # для средневзвешенного

    # Средневзвешенное выполнение плана (по моделям с планом)
    plan_completion_avg = None
    if total_planned_revenue > 0 and total_revenue > 0:
        models_with_plan = [m for m in model_revenues if model_plans.get(m, 0) > 0]
        if models_with_plan:
            completions = [result[m]["completion_pct"] for m in models_with_plan]
            revenues = [result[m]["revenue"] for m in models_with_plan]
            plan_completion_avg = sum(c * r for c, r in zip(completions, revenues) if c is not None) / sum(revenues)

    return {
        "by_model": result,
        "total_chatter_cut": total_chatter_cut,
        "plan_completion_avg": plan_completion_avg,
    }
