"""
Вкладка События — добавляем события для контекста AI.
Например: новая модель, ушёл чаттер, сменились админы.
"""
import streamlit as st
from datetime import date

from services.events import get_all_events, add_event, delete_event


def render(transactions_df, expenses_df, metrics):
    st.title("События")
    st.caption("События агентства используются как контекст для AI. Добавляй: новые модели, ушедших чаттеров, смену админов и т.д.")

    events = get_all_events()

    # Форма добавления
    with st.expander("➕ Добавить событие", expanded=not events):
        col1, col2 = st.columns([1, 3])
        with col1:
            ev_date = st.date_input("Дата", value=date.today(), key="ev_date")
        with col2:
            ev_desc = st.text_input(
                "Описание",
                placeholder="Например: Добавили новую модель X, ушёл чаттер Y, сменили админов",
                key="ev_desc",
            )
        if st.button("Добавить", key="ev_add") and ev_desc.strip():
            add_event(ev_date.strftime("%Y-%m-%d"), ev_desc.strip())
            st.toast("Событие добавлено", icon="✅")
            st.rerun()

    st.divider()

    # Список событий
    if not events:
        st.info("Пока нет событий. Добавь первое — оно попадёт в контекст AI.")
        return

    st.subheader("Список событий")
    for i, e in enumerate(events):
        d = e.get("date", "—")
        desc = e.get("description", "—")
        col1, col2, col3 = st.columns([1, 4, 1])
        with col1:
            st.markdown(f"**{d}**")
        with col2:
            st.markdown(desc)
        with col3:
            if st.button("🗑", key=f"ev_del_{i}", help="Удалить"):
                delete_event(d, desc)
                st.rerun()
