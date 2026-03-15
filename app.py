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
import tabs.admin_kpi as admin_kpi
import tabs.models_detail as models_detail
import tabs.ai as ai
import tabs.events as events_tab
import tabs.settings as settings

# --- СЕРВИСЫ ---
from services.db import load_transactions, load_expenses, get_all_available_months, get_app_settings
from services.metrics import calculate_metrics
from services.plans import get_plans, compute_plan_metrics
from components.styling import inject_premium_css
from streamlit_extras.metric_cards import style_metric_cards

st.set_page_config(layout="wide", page_icon="📊", initial_sidebar_state="expanded")
inject_premium_css()
style_metric_cards(
    background_color="rgba(30, 41, 59, 0.7)",
    border_size_px=1,
    border_color="rgba(255, 255, 255, 0.08)",
    border_radius_px=12,
    border_left_color="#00d4aa",
    box_shadow=True,
)

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

# Загружаем сохранённые настройки из БД (перезаписывают дефолты)
_saved = get_app_settings()
if _saved:
    for k, v in _saved.items():
        try:
            if k in ("model_percent", "chatter_percent", "admin_percent", "withdraw_percent"):
                st.session_state[k] = int(v)
            elif k in ("use_withdraw", "use_retention", "use_plans"):
                st.session_state[k] = str(v).lower() in ("1", "true", "yes", "on")
        except (ValueError, TypeError):
            pass

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


def _is_client_mode():
    v = (_os.getenv("CLIENT_MODE") or _os.getenv("SKYNET_CLIENT") or "").lower().strip()
    return v in ("1", "true", "yes", "on")


_is_client = _is_client_mode()
if _is_client:
    st.session_state.use_retention = False  # Клиентская версия — без retention
else:
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
# ЗАГРУЗКА ДАННЫХ (кэш в session_state — без повторных запросов при смене ползунков/табов)
# ==================================================

_cached_month = st.session_state.get("_data_month")
_use_cache = _cached_month == (selected_year, selected_month) and "_transactions_df" in st.session_state

if _use_cache:
    transactions_df = st.session_state["_transactions_df"]
    expenses_df = st.session_state["_expenses_df"]
else:
    try:
        with st.spinner("Загрузка данных…"):
            transactions_df = load_transactions(start_date, end_date)
            expenses_df = load_expenses(start_date, end_date)
        st.session_state["_data_month"] = (selected_year, selected_month)
        st.session_state["_transactions_df"] = transactions_df
        st.session_state["_expenses_df"] = expenses_df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        st.stop()

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

# Сохраняем в session_state для фрагмента (год/месяц и month_options для AI)
st.session_state["_selected_year"] = selected_year
st.session_state["_selected_month"] = selected_month
st.session_state["_month_options"] = month_options


def _render_tabs():
    """Рендер табов во фрагменте: при действиях внутри табов перезапускается только он — без загрузки данных и сайдбара."""
    tx = st.session_state.get("_transactions_df")
    ex = st.session_state.get("_expenses_df")
    sy = st.session_state.get("_selected_year")
    sm = st.session_state.get("_selected_month")
    mo = st.session_state.get("_month_options", [])
    if tx is None or ex is None:
        st.info("Выберите месяц в сайдбаре.")
        return
    model_rev = (
        tx.groupby("model", dropna=False)["amount"].sum().to_dict()
        if tx is not None and not tx.empty and "model" in tx.columns
        else {}
    )
    model_rev = {str(k).strip() if k is not None else "—": v for k, v in model_rev.items()}
    model_plans = get_plans(sy, sm)
    use_p = st.session_state.get("use_plans", True) and bool(model_plans)
    plan_m = compute_plan_metrics(model_rev, model_plans) if use_p and model_plans else None
    met = calculate_metrics(
        tx, ex,
        chatter_percent=st.session_state.chatter_percent,
        admin_percent=st.session_state.admin_percent,
        model_percent=st.session_state.model_percent,
        withdraw_percent=st.session_state.withdraw_percent,
        use_withdraw=st.session_state.use_withdraw,
        use_retention=st.session_state.use_retention,
        plan_metrics=plan_m,
    )
    tabs_list = st.tabs(["Обзор", "Финансы", "Модели", "Чаттеры", "KPI", "Админы", "Планы", "Лаборатория", "Структура", "События", "AI", "Настройки"])
    with tabs_list[0]:
        overview.render(tx, ex, met, sy, sm)
    with tabs_list[1]:
        finance.render(tx, ex, met)
    with tabs_list[2]:
        models_detail.render(tx, ex, met, plan_m, sy, sm)
    with tabs_list[3]:
        chatters.render(tx, ex, met, plan_m, sy, sm)
    with tabs_list[4]:
        kpi_chatters.render(tx, ex, met, plan_m, sy, sm)
    with tabs_list[5]:
        admin_kpi.render(tx, met, plan_m, sy, sm)
    with tabs_list[6]:
        plans.render(tx, ex, met, sy, sm)
    with tabs_list[7]:
        lab.render(tx, ex, met, sy, sm)
    with tabs_list[8]:
        structure.render(tx, ex, met, plan_m)
    with tabs_list[9]:
        events_tab.render(tx, ex, met)
    with tabs_list[10]:
        ai.render(tx, ex, met, plan_m, sy, sm, mo)
    with tabs_list[11]:
        settings.render(tx, ex, met)


# Фрагмент: при действиях внутри табов перезапускается только _render_tabs, без загрузки данных (Streamlit 1.33+)
if getattr(st, "fragment", None):
    _render_tabs = st.fragment(_render_tabs)
_render_tabs()