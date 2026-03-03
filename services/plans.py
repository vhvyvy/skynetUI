"""
Планы по моделям. % чаттера зависит от выполнения плана:
50% → 20%, 60% → 21%, 70% → 22%, 80% → 23%, 90% → 24%, 100%+ → 25%
"""
import json
import os

PLANS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "plans.json")

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


def _ensure_data_dir():
    d = os.path.dirname(PLANS_FILE)
    if not os.path.exists(d):
        os.makedirs(d)


def _load_all():
    if not os.path.exists(PLANS_FILE):
        return {}
    try:
        with open(PLANS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_all(data):
    _ensure_data_dir()
    with open(PLANS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_plans(year, month):
    """Возвращает dict {model: plan_amount} для месяца."""
    data = _load_all()
    y = str(year)
    m = str(month)
    if y not in data or m not in data[y]:
        return {}
    return data[y][m]


def save_plan(year, month, model, plan_amount):
    """Сохраняет план для модели."""
    data = _load_all()
    y, m = str(year), str(month)
    if y not in data:
        data[y] = {}
    if m not in data[y]:
        data[y][m] = {}
    data[y][m][model] = float(plan_amount)
    _save_all(data)


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
