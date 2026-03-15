import os
import streamlit as st

from services.db import set_app_settings


def _is_client():
    v = (os.getenv("CLIENT_MODE") or os.getenv("SKYNET_CLIENT") or "").lower().strip()
    return v in ("1", "true", "yes", "on")


IS_CLIENT = _is_client()


def render(transactions_df, expenses_df, metrics):
    st.title("Настройки")
    st.subheader("Экономическая модель")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.chatter_percent = st.slider(
            "Чаттер %",
            0, 100,
            value=st.session_state.chatter_percent,
            key="settings_chatter_pct",
        )
        st.session_state.admin_percent = st.slider(
            "Админы %",
            0, 100,
            value=st.session_state.admin_percent,
            key="settings_admin_pct",
        )

    with col2:
        st.session_state.model_percent = st.slider(
            "Модель %",
            0, 100,
            value=st.session_state.model_percent,
            key="settings_model_pct",
        )
        st.session_state.withdraw_percent = st.slider(
            "Вывод %",
            0, 100,
            value=st.session_state.withdraw_percent,
            key="settings_withdraw_pct",
        )

    st.session_state.use_withdraw = st.toggle(
        "Учитывать комиссию вывода",
        value=st.session_state.use_withdraw,
        help="6% от выручки — комиссия на вывод средств",
        key="settings_use_withdraw",
    )

    if not IS_CLIENT:
        st.session_state.use_retention = st.toggle(
            "Удержание 2.5% с моделей и чаттеров (с января)",
            value=st.session_state.get("use_retention", True),
            help="2.5% от долей моделей и чаттеров забирает агентство. Включите/выключите, чтобы увидеть влияние на прибыль.",
            key="settings_use_retention",
        )

    if st.button("Сохранить настройки", type="primary", key="settings_save_btn"):
        set_app_settings({
            "model_percent": st.session_state.model_percent,
            "chatter_percent": st.session_state.chatter_percent,
            "admin_percent": st.session_state.admin_percent,
            "withdraw_percent": st.session_state.withdraw_percent,
            "use_withdraw": "1" if st.session_state.use_withdraw else "0",
            "use_retention": "1" if st.session_state.get("use_retention", True) else "0",
            "use_plans": "1" if st.session_state.get("use_plans", True) else "0",
        })
        st.cache_data.clear()  # чтобы при следующем запуске подтянулись настройки из БД
        st.success("Настройки сохранены. Они применятся во всех вкладках и сохранятся после обновления страницы.")
        st.rerun()

    st.divider()

    total_percent = (
        st.session_state.model_percent
        + st.session_state.chatter_percent
        + st.session_state.admin_percent
        + st.session_state.withdraw_percent
    )

    st.subheader("Текущая структура")

    st.write(f"Модель: {st.session_state.model_percent}%")
    st.write(f"Чаттер: {st.session_state.chatter_percent}%")
    st.write(f"Админы: {st.session_state.admin_percent}%")
    st.write(f"Вывод: {st.session_state.withdraw_percent}%")
    st.write(f"Суммарно удержаний: {total_percent}%")
    if not IS_CLIENT and st.session_state.get("use_retention", True):
        st.write("**Retention 2.5%** (с model+chatter): включён")

    if total_percent > 100:
        st.error("⚠ Сумма процентов превышает 100%")