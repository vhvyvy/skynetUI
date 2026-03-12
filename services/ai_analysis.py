"""
AI-анализ: сбор полного контекста из всех данных системы.
Кеширование для ускорения вкладки AI.
"""
import json
import pandas as pd
from datetime import datetime
import calendar
import streamlit as st

from services.db import load_transactions, load_expenses, get_all_available_months
from services.plans import get_plans, compute_plan_metrics
from services.chatter_kpi import get_kpi, get_kpi_for_merge
from services.events import get_events_for_context


def _month_summary(transactions_df, expenses_df, metrics, plan_metrics, year, month):
    """Краткая сводка по месяцу."""
    rev = metrics.get("revenue", 0) if metrics else 0
    exp = metrics.get("expenses", 0) if metrics else 0
    net = metrics.get("net", 0) if metrics else 0
    marg = metrics.get("margin", 0) if metrics else 0
    model_cut = metrics.get("model_cut", 0) if metrics else 0
    chatter_cut = metrics.get("chatter_cut", 0) if metrics else 0
    agency = metrics.get("agency_cut", 0) if metrics else 0
    plan_avg = plan_metrics.get("plan_completion_avg") if plan_metrics else None

    s = f"Месяц {year}-{month:02d}: Выручка ${rev:,.2f}, Расходы ${exp:,.2f}, Чистая прибыль ${net:,.2f}, Маржа {marg:.1f}%"
    s += f". Распределение: модели ${model_cut:,.2f}, чаттеры ${chatter_cut:,.2f}, агентство ${agency:,.2f}."
    if plan_avg is not None:
        s += f" План выполнен на {plan_avg:.1f}%."

    if transactions_df is not None and not transactions_df.empty:
        models = transactions_df["model"].nunique() if "model" in transactions_df.columns else 0
        chatters = transactions_df["chatter"].nunique() if "chatter" in transactions_df.columns else 0
        trx_count = len(transactions_df)
        s += f" Моделей: {models}, чаттеров: {chatters}, транзакций: {trx_count}."

    return s


@st.cache_data(ttl=300)
def _get_month_comparison_parts(_month_options: tuple) -> list:
    """
    Кешируемая загрузка сводок по месяцам (самый тяжёлый блок — много запросов к БД).
    _month_options: tuple of (year, month) — до 6 последних месяцев.
    """
    MONTHS_RU = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
        7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }
    parts = []
    for y, m in _month_options[:6]:
        start = datetime(y, m, 1)
        end = datetime(y, m, calendar.monthrange(y, m)[1])
        trx = load_transactions(start, end)
        exp = load_expenses(start, end)
        rev = trx["amount"].sum() if trx is not None and not trx.empty else 0
        exp_sum = exp["amount"].sum() if exp is not None and not exp.empty else 0
        model_rev = trx.groupby("model")["amount"].sum().to_dict() if trx is not None and not trx.empty and "model" in trx.columns else {}
        plans = get_plans(y, m)
        pm = compute_plan_metrics(model_rev, plans) if plans else None
        net = rev - (pm["total_chatter_cut"] if pm else rev * 0.25) - rev * 0.23 - rev * 0.09 - exp_sum
        parts.append(f"{MONTHS_RU.get(m, m)} {y}: выручка ${rev:,.2f}, расходы ${exp_sum:,.2f}, прибыль ~${net:,.2f}")
    return parts


@st.cache_data(ttl=300)
def build_full_context(
    transactions_df,
    expenses_df,
    metrics,
    plan_metrics,
    selected_year,
    selected_month,
    kpi_df=None,
    _month_options_tuple=None,
):
    """
    Собирает полный контекст для AI из всех данных.
    Возвращает строку с полным дампом для промпта.
    Кеш 5 мин — при смене месяца или данных получим свежий контекст.
    """
    MONTHS_RU = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
        7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    parts = []

    # 1. Текущий месяц — общая сводка
    parts.append("=== ТЕКУЩИЙ МЕСЯЦ ===")
    parts.append(_month_summary(transactions_df, expenses_df, metrics, plan_metrics, selected_year, selected_month))
    parts.append("")

    # 2. Метрики (распределение)
    if metrics:
        parts.append("--- Метрики ---")
        parts.append(f"Выручка: ${metrics.get('revenue', 0):,.2f}")
        parts.append(f"Расходы: ${metrics.get('expenses', 0):,.2f}")
        parts.append(f"Чистая прибыль: ${metrics.get('net', 0):,.2f}")
        parts.append(f"Маржа: {metrics.get('margin', 0):.1f}%")
        parts.append(f"Модели: ${metrics.get('model_cut', 0):,.2f} ({metrics.get('model_percent', 0)}%)")
        parts.append(f"Чаттеры: ${metrics.get('chatter_cut', 0):,.2f} (по плану или {metrics.get('chatter_percent', 0)}%)")
        parts.append(f"Админы: ${metrics.get('admin_cut', 0):,.2f}")
        parts.append(f"Вывод: ${metrics.get('withdraw_cut', 0):,.2f}")
        parts.append(f"Агентство: ${metrics.get('agency_cut', 0):,.2f}")
        if metrics.get("retention_income"):
            parts.append(f"Retention 2.5%: +${metrics['retention_income']:,.2f}")
        parts.append("")

    # 3. Планы по моделям
    if plan_metrics and plan_metrics.get("by_model"):
        parts.append("--- Планы по моделям (выполнение → % чаттеру) ---")
        for m, d in plan_metrics["by_model"].items():
            if d.get("plan", 0) > 0:
                pct = d.get("completion_pct") or 0
                chatter_pct = d.get("chatter_pct") or 0
                parts.append(f"{m}: выручка ${d['revenue']:,.2f}, план ${d['plan']:,.2f}, выполнение {pct:.1f}% → {chatter_pct}% чаттеру")
        parts.append("")

    # 4. Транзакции — по моделям и чаттерам
    if transactions_df is not None and not transactions_df.empty:
        parts.append("--- Выручка по моделям ---")
        if "model" in transactions_df.columns:
            by_model = transactions_df.groupby("model")["amount"].sum().sort_values(ascending=False)
            for model, amt in by_model.items():
                pct = amt / transactions_df["amount"].sum() * 100 if transactions_df["amount"].sum() > 0 else 0
                parts.append(f"  {model}: ${amt:,.2f} ({pct:.1f}%)")
        parts.append("")
        parts.append("--- Выручка по чаттерам ---")
        if "chatter" in transactions_df.columns:
            by_chatter = transactions_df.groupby("chatter")["amount"].sum().sort_values(ascending=False)
            for ch, amt in by_chatter.items():
                pct = amt / transactions_df["amount"].sum() * 100 if transactions_df["amount"].sum() > 0 else 0
                parts.append(f"  {ch}: ${amt:,.2f} ({pct:.1f}%)")
        parts.append("")
        parts.append("--- Структура (модель → чаттеры) ---")
        if "model" in transactions_df.columns and "chatter" in transactions_df.columns:
            pairs = transactions_df.groupby(["model", "chatter"])["amount"].sum().reset_index()
            for model in pairs["model"].unique():
                sub = pairs[pairs["model"] == model].sort_values("amount", ascending=False)
                chatters = ", ".join(f"{r['chatter']} (${r['amount']:,.0f})" for _, r in sub.head(5).iterrows())
                parts.append(f"  {model}: {chatters}")
        parts.append("")

    # 5. Расходы
    if expenses_df is not None and not expenses_df.empty:
        parts.append("--- Расходы ---")
        total_exp = expenses_df["amount"].sum()
        parts.append(f"Итого: ${total_exp:,.2f}")
        if "category" in expenses_df.columns:
            by_cat = expenses_df.groupby("category")["amount"].sum().sort_values(ascending=False)
            for cat, amt in by_cat.items():
                parts.append(f"  {cat}: ${amt:,.2f}")
        if "model" in expenses_df.columns:
            by_mod = expenses_df.groupby("model")["amount"].sum().sort_values(ascending=False)
            parts.append("По моделям:")
            for m, amt in by_mod.items():
                parts.append(f"  {m}: ${amt:,.2f}")
        parts.append("")

    # 6. События агентства (вкладка «События»)
    events = get_events_for_context(selected_year, selected_month)
    if events:
        parts.append("--- События агентства (новая модель, ушёл чаттер, смена админов и т.д.) ---")
        for e in events:
            parts.append(f"  {e.get('date', '—')}: {e.get('description', '')}")
        parts.append("")

    # 7. KPI чаттеров
    if kpi_df is not None and not kpi_df.empty:
        parts.append("--- KPI чаттеров (PPV Open Rate, APV, Total Chats, RPC, Conversion Score и др.) ---")
        cols = [c for c in ["chatter", "Выручка", "Транзакций", "PPV Open Rate %", "APV", "Total Chats", "RPC", "Conversion Score"] if c in kpi_df.columns]
        if cols:
            parts.append(kpi_df[cols].head(30).to_string(index=False))
        parts.append("")

    # 8. Сравнение месяцев (кешируется — самый тяжёлый блок)
    if _month_options_tuple:
        parts.append("--- Доступные месяцы для сравнения ---")
        for line in _get_month_comparison_parts(_month_options_tuple):
            parts.append(line)
        parts.append("")

    return "\n".join(parts)
