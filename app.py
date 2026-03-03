import streamlit as st
from datetime import datetime
import calendar
import os as _os
from dotenv import load_dotenv

load_dotenv()
# Поддержка .env в services/ (OPENAI_API_KEY)
_ep = _os.path.join(_os.path.dirname(__file__), "services", ".env")
if _os.path.exists(_ep):
    load_dotenv(_ep)

# --- ТАБЫ (как у тебя было) ---
import tabs.overview as overview
import tabs.finance as finance
import tabs.chatters as chatters
import tabs.kpi_chatters as kpi_chatters
import tabs.plans as plans
import tabs.lab as lab
import tabs.structure as structure
import tabs.ai as ai
import tabs.events as events_tab
import tabs.settings as settings

# --- СЕРВИСЫ ---
from services.db import load_transactions, load_expenses, get_all_available_months
from services.metrics import calculate_metrics
from services.plans import get_plans, compute_plan_metrics

st.set_page_config(layout="wide")

# ==================================================
# ДЕФОЛТНЫЕ ПРОЦЕНТЫ (инициализация)
# ==================================================

defaults = {
    "model_percent": 23,
    "chatter_percent": 25,
    "admin_percent": 9,
    "withdraw_percent": 6,
    "use_withdraw": True,
    "use_retention": True,  # 2.5% с model+chatter (с января)
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================================================
# ВЫБОР МЕСЯЦА (все месяцы с данными из transactions и expenses)
# ==================================================

_today = datetime.today()
month_options = get_all_available_months()

if not month_options:
    month_options = [(_today.year, _today.month)]
else:
    # Всегда добавляем текущий месяц, если его ещё нет
    _current = (_today.year, _today.month)
    if _current not in month_options:
        month_options = [_current] + month_options

# Русские названия
MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

labels = [
    f"{MONTHS_RU[m]} {y} (текущий)" if (y, m) == (_today.year, _today.month) else f"{MONTHS_RU[m]} {y}"
    for y, m in month_options
]

selected_label = st.sidebar.selectbox("Выберите месяц", labels)

st.sidebar.divider()
st.sidebar.caption("Экономическая модель")
st.session_state.use_retention = st.sidebar.toggle(
    "Retention 2.5% (с model+chatter)",
    value=st.session_state.get("use_retention", True),
    help="Включить/выключить, чтобы увидеть влияние на прибыль"
)
st.session_state.use_plans = st.sidebar.toggle(
    "Планы по моделям (гибкий % чаттера)",
    value=st.session_state.get("use_plans", True),
    help="% чаттера зависит от выполнения плана (50%→20%, 100%→25%)"
)

index = labels.index(selected_label)
selected_year, selected_month = month_options[index]

start_date = datetime(selected_year, selected_month, 1)
last_day = calendar.monthrange(selected_year, selected_month)[1]
end_date = datetime(selected_year, selected_month, last_day)

# ==================================================
# ЗАГРУЗКА ДАННЫХ
# ==================================================

transactions_df = load_transactions(start_date, end_date)
expenses_df = load_expenses(start_date, end_date)

# Планы по моделям (влияют на % чаттера)
model_revenues = (
    transactions_df.groupby("model", dropna=False)["amount"].sum().to_dict()
    if transactions_df is not None and not transactions_df.empty and "model" in transactions_df.columns
    else {}
)
model_revenues = {str(k).strip() if k is not None else "—": v for k, v in model_revenues.items()}
model_plans = get_plans(selected_year, selected_month)
use_plans = st.session_state.get("use_plans", True) and bool(model_plans)
plan_metrics = compute_plan_metrics(model_revenues, model_plans) if use_plans and model_plans else None

# ==================================================
# РАСЧЁТ МЕТРИК
# ==================================================

metrics = calculate_metrics(
    transactions_df,
    expenses_df,
    chatter_percent=st.session_state.chatter_percent,
    admin_percent=st.session_state.admin_percent,
    model_percent=st.session_state.model_percent,
    withdraw_percent=st.session_state.withdraw_percent,
    use_withdraw=st.session_state.use_withdraw,
    use_retention=st.session_state.use_retention,
    plan_metrics=plan_metrics,
)

# ==================================================
# ТАБЫ
# ==================================================

tabs_list = st.tabs(["Обзор", "Финансы", "Чаттеры", "KPI", "Планы", "Лаборатория", "Структура", "События", "AI", "Настройки"])

with tabs_list[0]:
    overview.render(transactions_df, expenses_df, metrics, selected_year, selected_month)

with tabs_list[1]:
    finance.render(transactions_df, expenses_df, metrics)

with tabs_list[2]:
    chatters.render(transactions_df, expenses_df, metrics, plan_metrics, selected_year, selected_month)

with tabs_list[3]:
    kpi_chatters.render(transactions_df, expenses_df, metrics, plan_metrics, selected_year, selected_month)

with tabs_list[4]:
    plans.render(transactions_df, expenses_df, metrics, selected_year, selected_month)

with tabs_list[5]:
    lab.render(transactions_df, expenses_df, metrics, selected_year, selected_month)

with tabs_list[6]:
    structure.render(transactions_df, expenses_df, metrics, plan_metrics)

with tabs_list[7]:
    events_tab.render(transactions_df, expenses_df, metrics)

with tabs_list[8]:
    ai.render(transactions_df, expenses_df, metrics, plan_metrics, selected_year, selected_month, month_options)

with tabs_list[9]:
    settings.render(transactions_df, expenses_df, metrics)