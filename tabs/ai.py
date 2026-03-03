"""
Вкладка AI — чат с полным контекстом данных, кнопки готовых запросов.
"""
import streamlit as st

from services.ai_analysis import build_full_context
from services.ai_service import chat_with_context
from tabs.kpi_chatters import _build_kpi_df


# Готовые запросы для быстрого анализа
QUICK_PROMPTS = [
    {
        "label": "Оценка состояния агентства",
        "prompt": "Дай оценку общего состояния агентства за текущий месяц. Что хорошо, что вызывает опасения? Ключевые метрики, риски, рекомендации.",
    },
    {
        "label": "Сравнение месяцев",
        "prompt": "Сравни текущий месяц с предыдущими. Динамика выручки, расходов, прибыли. Тренды, сезонность, что изменилось.",
    },
    {
        "label": "Сравнение чаттеров",
        "prompt": "Сравни чаттеров между собой по выручке, KPI (PPV Open Rate, RPC, Conversion Score). Кто сильнее, у кого потенциал роста, кому нужна помощь.",
    },
    {
        "label": "Анализ моделей",
        "prompt": "Проанализируй модели: какие приносят больше всего, как выполнен план, где концентрация выручки. Рекомендации по приоритетам.",
    },
    {
        "label": "Расходы и эффективность",
        "prompt": "Разбери расходы: структура, категории, по моделям. Как соотносятся с выручкой? Где можно оптимизировать?",
    },
    {
        "label": "Структура и связки",
        "prompt": "Оцени структуру: модель×чаттер. Какие связки самые прибыльные? Есть ли перекосы, зависимости, риски концентрации?",
    },
    {
        "label": "KPI и точки роста",
        "prompt": "По KPI чаттеров: где точки роста? Кто прокачивается, кто отстаёт? Какие метрики улучшать в первую очередь?",
    },
    {
        "label": "Планы и выполнение",
        "prompt": "Как выполняются планы по моделям? Кто перевыполняет, кто не дотягивает? Влияние на % чаттеру, рекомендации.",
    },
]


def render(
    transactions_df,
    expenses_df,
    metrics,
    plan_metrics=None,
    selected_year=None,
    selected_month=None,
    month_options=None,
):
    st.title("AI")
    st.caption("AI-аналитик с полным доступом к данным агентства. GPT-4o.")

    # KPI датафрейм для контекста
    kpi_df = None
    if transactions_df is not None and not transactions_df.empty and metrics:
        kpi_df = _build_kpi_df(transactions_df, metrics, plan_metrics, selected_year, selected_month)

    context = build_full_context(
        transactions_df,
        expenses_df,
        metrics,
        plan_metrics,
        selected_year or 2025,
        selected_month or 1,
        kpi_df=kpi_df,
        month_options=month_options or [],
    )

    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    # Кнопки готовых запросов
    st.subheader("Быстрые запросы")
    cols = st.columns(2)
    for i, qp in enumerate(QUICK_PROMPTS):
        with cols[i % 2]:
            if st.button(qp["label"], key=f"ai_quick_{i}"):
                st.session_state.ai_quick_prompt = qp["prompt"]
                st.rerun()

    if "ai_quick_prompt" in st.session_state:
        prompt = st.session_state.pop("ai_quick_prompt")
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        with st.spinner("Анализирую…"):
            reply = chat_with_context(context, prompt, messages_history=st.session_state.ai_messages[:-1])
        st.session_state.ai_messages.append({"role": "assistant", "content": reply})
        st.rerun()

    st.divider()
    st.subheader("Чат")

    # Отображение истории
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Поле ввода
    user_input = st.chat_input("Задай вопрос по данным агентства…")
    if user_input:
        st.session_state.ai_messages.append({"role": "user", "content": user_input})
        with st.spinner("Думаю…"):
            reply = chat_with_context(context, user_input, messages_history=st.session_state.ai_messages[:-1])
        st.session_state.ai_messages.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.button("Очистить чат", key="ai_clear"):
        st.session_state.ai_messages = []
        st.rerun()
