"""
Вкладка KPI чаттеров — полный блок метрик с памяткой и аналитикой.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
from datetime import datetime

from services.chatter_kpi import get_kpi, get_kpi_for_merge, get_unmapped_user_ids, save_kpi_batch
from services.onlymonster import fetch_chatter_metrics, parse_kpi_csv, get_api_config


def _build_kpi_df(transactions_df, metrics, plan_metrics, selected_year, selected_month):
    """Строит полный KPI-датафрейм для чаттеров."""
    if transactions_df is None or transactions_df.empty or "chatter" not in transactions_df.columns:
        return None

    df = transactions_df.copy()
    df["chatter"] = df["chatter"].fillna("— (без чаттера)").astype(str).str.strip()
    df.loc[df["chatter"] == "", "chatter"] = "— (без чаттера)"

    chatter_pct = st.session_state.get("chatter_percent", 25)
    total_revenue = metrics["revenue"]
    use_plans = plan_metrics and plan_metrics.get("by_model")
    by_model = plan_metrics.get("by_model", {}) if plan_metrics else {}

    if use_plans and "model" in df.columns:
        df = df.copy()
        df["_model"] = df["model"].fillna("—").astype(str).str.strip()
        df["_chatter_pct"] = df["_model"].map(lambda m: by_model.get(m, {}).get("chatter_pct", chatter_pct))
        df["_chatter_cut"] = df["amount"] * df["_chatter_pct"] / 100
        chatter_by_chatter = df.groupby("chatter", dropna=False)["_chatter_cut"].sum()
    else:
        chatter_by_chatter = df.groupby("chatter", dropna=False)["amount"].sum() * chatter_pct / 100

    kpi = (
        df.groupby("chatter", dropna=False)
        .agg(Выручка=("amount", "sum"), Транзакций=("amount", "count"))
        .reset_index()
    )
    kpi["Средний чек"] = (kpi["Выручка"] / kpi["Транзакций"]).round(2)
    kpi["Доля выручки %"] = (kpi["Выручка"] / total_revenue * 100).round(1) if total_revenue > 0 else 0
    kpi["Расчётная оплата"] = kpi["chatter"].map(chatter_by_chatter).fillna(0).round(2)
    kpi = kpi.sort_values("Выручка", ascending=False)

    kpi_by_id, name_to_id = get_kpi_for_merge(selected_year or 2025, selected_month or 1) if selected_year and selected_month else ({}, {})
    kpi_data = get_kpi(selected_year or 2025, selected_month or 1) if selected_year and selected_month else {}

    def _metrics_for_chatter(c):
        s = str(c).strip()
        uid = name_to_id.get(s)
        if not uid:
            # Fallback: match by prefix (e.g. "@JI9JI9 Анна" → "@JI9JI9")
            for name, nid in name_to_id.items():
                if s.startswith(str(name)) or str(name).startswith(s):
                    uid = nid
                    break
        if uid:
            return kpi_by_id.get(uid, {})
        return kpi_data.get(c, {})

    kpi["PPV Open Rate %"] = kpi["chatter"].map(lambda c: _metrics_for_chatter(c).get("ppv_open_rate"))
    kpi["APV"] = kpi["chatter"].map(lambda c: _metrics_for_chatter(c).get("apv"))
    kpi["Total Chats"] = kpi["chatter"].map(lambda c: _metrics_for_chatter(c).get("total_chats"))

    for chatter_name, d in kpi_data.items():
        if chatter_name not in kpi["chatter"].tolist():
            kpi = pd.concat([kpi, pd.DataFrame([{
                "chatter": chatter_name, "Выручка": 0, "Транзакций": 0, "Средний чек": 0,
                "Доля выручки %": 0, "Расчётная оплата": 0,
                "PPV Open Rate %": d.get("ppv_open_rate"), "APV": d.get("apv"), "Total Chats": d.get("total_chats"),
            }])], ignore_index=True)

    # Не скрываем строки с user_id — иначе после sync через API данные не видны

    kpi["PPV Sold"] = kpi.apply(lambda r: round(r["Выручка"] / r["APV"], 2) if pd.notna(r["APV"]) and r["APV"] > 0 else None, axis=1)
    kpi["APC per chat"] = kpi.apply(lambda r: round(r["PPV Sold"] / r["Total Chats"], 2) if pd.notna(r["Total Chats"]) and r["Total Chats"] > 0 and pd.notna(r["PPV Sold"]) else None, axis=1)
    kpi["RPC"] = kpi.apply(lambda r: round(r["Выручка"] / r["Total Chats"], 2) if pd.notna(r["Total Chats"]) and r["Total Chats"] > 0 else None, axis=1)
    kpi["Volume rating"] = kpi.apply(lambda r: round(r["Total Chats"] * (r["PPV Open Rate %"] / 100), 2) if pd.notna(r["Total Chats"]) and pd.notna(r["PPV Open Rate %"]) and r["Total Chats"] > 0 else None, axis=1)

    kpi["Total Chats"] = kpi["Total Chats"].apply(lambda x: round(x, 2) if pd.notna(x) else x)

    # Дополнительные KPI (×100 для читаемости — иначе 0.01–0.02)
    kpi["Conversion Score"] = kpi.apply(lambda r: round((r["PPV Open Rate %"] or 0) * (r["APC per chat"] or 0), 2) if pd.notna(r["PPV Open Rate %"]) and pd.notna(r["APC per chat"]) else None, axis=1)
    kpi["Monetization Depth"] = kpi.apply(lambda r: round((r["RPC"] or 0) / (r["APV"] or 1) * 100, 2) if pd.notna(r["RPC"]) and pd.notna(r["APV"]) and r["APV"] > 0 else None, axis=1)
    kpi["Productivity Index"] = kpi.apply(lambda r: round((r["PPV Sold"] or 0) / (r["Total Chats"] or 1) * (r["PPV Open Rate %"] or 0), 2) if pd.notna(r["Total Chats"]) and r["Total Chats"] > 0 else None, axis=1)
    kpi["Efficiency Ratio"] = kpi.apply(lambda r: round((r["RPC"] or 0) / (r["APV"] or 1) * (r["PPV Open Rate %"] or 0), 2) if pd.notna(r["RPC"]) and pd.notna(r["APV"]) and pd.notna(r["PPV Open Rate %"]) and r["APV"] > 0 else None, axis=1)

    # Скрыть ID без маппинга и строки с нулевой расчётной оплатой
    HIDDEN_IDS = {"9680", "18073", "71191", "73588", "79737", "80144", "@hornykabanchik"}
    kpi = kpi[~kpi["chatter"].astype(str).str.strip().isin(HIDDEN_IDS)]
    kpi = kpi[(kpi["Расчётная оплата"].fillna(0) > 0)]
    return kpi


def render(transactions_df, expenses_df, metrics, plan_metrics=None, selected_year=None, selected_month=None):
    st.title("📊 KPI чаттеров")
    st.caption("Метрики Onlymonster, формулы и памятка по чтению данных")

    kpi = _build_kpi_df(transactions_df, metrics, plan_metrics, selected_year, selected_month)
    if kpi is None or kpi.empty:
        st.info("Нет данных за выбранный период. Перейдите на вкладку «Чаттеры» или загрузите транзакции.")
        return

    # ========== Памятка: как читать данные ==========
    with st.expander("📖 Памятка: как читать и анализировать KPI", expanded=True):
        st.markdown("""
        ### Базовые метрики
        | Метрика | Что значит | Как читать |
        |---------|------------|------------|
        | **Транзакций (выходы)** | Количество смен (записей в таблице) | Больше = больше смен отработано |
        | **Средний чек (средний выход)** | Средний чек за смену | Выше = умеет продавать крупнее; ниже = много мелких продаж |
        | **PPV Open Rate %** | % купленных PPV от отправленных | 20–30% — норм, 35%+ — сильный, <15% — пора дорабатывать контент/цены |
        | **APV** | Средняя сумма за купленный PPV | Показывает средний чек по PPV; растёт — лучше упаковка/цены |
        | **Total Chats** | Общее кол-во чатов с сообщениями | Объём работы, охват; рост при стабильном RPC — хорошо |
        | **RPC** | Revenue Per Chat = Выручка / Total Chats | Сколько $ приносит один чат; ключевая эффективность |
        | **PPV Sold** | Выручка / APV | Оценочное кол-во проданных PPV |
        | **APC per chat** | PPV Sold / Total Chats | Сколько PPV в среднем на чат |
        | **Volume rating** | Total Chats × PPV Open Rate % | «Взвешенный» объём: чаты × конверсия |
        ### Доп. метрики (масштаб 0–10+ для удобства)
        | Метрика | Формула | Как читать |
        |---------|---------|------------|
        | **Conversion Score** | PPV Open Rate × APC | Комбо «конверсия × продажи»; 1–3 норм, 5+ сильный |
        | **Monetization Depth** | (RPC/APV) × 100 | % «глубины» монетизации; 1–3 = мягко, 5+ = несколько продаж на чат |
        | **Productivity Index** | (PPV Sold/Total Chats) × PPV Open Rate | Продажи на чат с учётом конверсии |
        | **Efficiency Ratio** | (RPC/APV) × PPV Open Rate | Эффективность монетизации; чем выше, тем лучше |
        ### Выводы
        - **Высокий RPC + высокий Volume** — топ-чаттер, масштабируй
        - **Низкий PPV Open Rate, но высокий объём** — много шлёт, мало покупают → пересмотреть контент/цены
        - **Высокий APV, низкий Volume** — продаёт дорого, но мало охват → увеличить активность
        - **Рост Conversion Score** — чаттер прокачивается
        """)

    st.divider()

    # ========== Загрузка данных ==========
    st.subheader("Источники данных")
    col_load1, col_load2 = st.columns(2)
    with col_load1:
        uploaded = st.file_uploader("CSV/XLSX из Onlymonster", type=["csv", "xlsx", "xls"], key="kpi_upload")
        if uploaded:
            records = parse_kpi_csv(uploaded)
            if records and st.button("Применить"):
                save_kpi_batch(selected_year, selected_month, records)
                st.toast(f"Загружено {len(records)} записей", icon="✅")
                st.rerun()
    with col_load2:
        api_cfg = get_api_config()
        if api_cfg.get("url") and api_cfg.get("api_key"):
            st.caption("API Onlymonster подключён")
            if st.button("Синхронизировать через API", key="kpi_sync_api_btn"):
                if selected_year and selected_month:
                    start = datetime(selected_year, selected_month, 1)
                    end = datetime(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1], 23, 59, 59)
                    with st.spinner("Запрос к API Onlymonster..."):
                        try:
                            result = fetch_chatter_metrics(start_date=start, end_date=end)
                            if result is None:
                                st.error("Нет подключения к API. Проверьте api_url и api_key в секретах.")
                            elif len(result) == 0:
                                st.warning("API вернул 0 записей. Нет данных за выбранный месяц или проверьте токен.")
                            else:
                                save_kpi_batch(selected_year, selected_month, result)
                                st.toast(f"Загружено {len(result)} записей", icon="✅")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: {e}")
        else:
            st.warning(
                "Добавьте **ONLYMONSTER_API_KEY** и **ONLYMONSTER_API_URL** в Railway Variables, "
                "чтобы появилась кнопка синхронизации."
            )

    missing = kpi[kpi["PPV Open Rate %"].isna() & (kpi["Выручка"] > 0)]["chatter"].tolist()
    unmapped = get_unmapped_user_ids(selected_year or 2025, selected_month or 1) if selected_year and selected_month else []
    if missing:
        extra = f" User_id без маппинга: {', '.join(unmapped[:6])}." if unmapped else ""
        st.warning(f"Нет KPI у {len(missing)} чаттеров. Добавьте в `data/chatter_id_to_name.json`.{extra}")

    st.divider()

    # ========== Основная таблица KPI ==========
    st.subheader("Основная таблица KPI")
    kpi_renamed = kpi.copy()
    kpi_renamed = kpi_renamed.rename(columns={
        "Транзакций": "Транзакций (выходы)",
        "Средний чек": "Средний чек (средний выход)",
    })
    main_cols = ["chatter", "Выручка", "Транзакций (выходы)", "Средний чек (средний выход)", "Доля выручки %", "PPV Open Rate %", "APV", "Total Chats", "PPV Sold", "APC per chat", "RPC", "Volume rating", "Расчётная оплата"]
    main_cols = [c for c in main_cols if c in kpi_renamed.columns]
    main_df = kpi_renamed[main_cols].rename(columns={"chatter": "Чаттер"})
    try:
        from st_aggrid import AgGrid, GridOptionsBuilder
        gb = GridOptionsBuilder.from_dataframe(main_df)
        gb.configure_default_column(sortable=True, filterable=True, resizable=True)
        gb.configure_grid_options(domLayout="normal")
        go_main = gb.build()
        AgGrid(main_df.fillna("—"), gridOptions=go_main, theme="streamlit", height=400, fit_columns_on_grid_load=True, key="kpi_main_grid")
    except ImportError:
        fmt = {"Выручка": "${:,.2f}", "Средний чек (средний выход)": "${:,.2f}", "Расчётная оплата": "${:,.2f}", "Доля выручки %": "{:.1f}%"}
        st.dataframe(main_df.style.format({k: v for k, v in fmt.items() if k in main_df.columns}, na_rep="—"), use_container_width=True, hide_index=True)

    st.divider()

    # ========== Дополнительные KPI ==========
    st.subheader("Дополнительные метрики")
    st.caption("Conversion Score, Monetization Depth, Productivity Index, Efficiency Ratio — как читать: см. памятку выше.")
    extra_cols = ["chatter", "Conversion Score", "Monetization Depth", "Productivity Index", "Efficiency Ratio", "Выручка", "RPC"]
    extra_cols = [c for c in extra_cols if c in kpi.columns]
    extra_df = kpi[extra_cols].rename(columns={"chatter": "Чаттер"})
    try:
        from st_aggrid import AgGrid, GridOptionsBuilder
        gb = GridOptionsBuilder.from_dataframe(extra_df)
        gb.configure_default_column(sortable=True, filterable=True, resizable=True)
        go_extra = gb.build()
        AgGrid(extra_df.fillna("—"), gridOptions=go_extra, theme="streamlit", height=300, fit_columns_on_grid_load=True, key="kpi_extra_grid")
    except ImportError:
        st.dataframe(extra_df.style.format({"Выручка": "${:,.2f}"}, na_rep="—"), use_container_width=True, hide_index=True)

    st.divider()

    # Gauge charts для топ-чаттера
    top_row = kpi.iloc[0] if len(kpi) > 0 else None
    if top_row is not None and ("PPV Open Rate %" in kpi.columns or "Conversion Score" in kpi.columns):
        st.subheader("Ключевые метрики топ-чаттера по выручке")
        chatter_name = str(top_row.get("chatter", "—"))
        st.caption(f"Топ по выручке: {chatter_name}")
        ppv_val = top_row.get("PPV Open Rate %")
        conv_val = top_row.get("Conversion Score")
        rpc_val = top_row.get("RPC")
        g1, g2, g3 = st.columns(3)
        with g1:
            if pd.notna(ppv_val) and ppv_val is not None:
                fig_g = go.Figure(go.Indicator(mode="gauge+number", value=float(ppv_val), domain={"x": [0, 1], "y": [0, 1]}, title={"text": "PPV Open Rate %"}, gauge={"axis": {"range": [0, 50]}, "bar": {"color": "#00d4aa"}, "steps": [{"range": [0, 15], "color": "rgba(30,41,59,0.5)"}, {"range": [15, 30], "color": "rgba(0,212,170,0.2)"}, {"range": [30, 50], "color": "rgba(0,212,170,0.4)"}]}))
                fig_g.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20), height=200)
                st.plotly_chart(fig_g, use_container_width=True)
        with g2:
            if pd.notna(conv_val) and conv_val is not None:
                fig_g2 = go.Figure(go.Indicator(mode="gauge+number", value=float(conv_val), domain={"x": [0, 1], "y": [0, 1]}, title={"text": "Conversion Score"}, gauge={"axis": {"range": [0, 10]}, "bar": {"color": "#00d4aa"}, "steps": [{"range": [0, 3], "color": "rgba(30,41,59,0.5)"}, {"range": [3, 6], "color": "rgba(0,212,170,0.2)"}, {"range": [6, 10], "color": "rgba(0,212,170,0.4)"}]}))
                fig_g2.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20), height=200)
                st.plotly_chart(fig_g2, use_container_width=True)
        with g3:
            if pd.notna(rpc_val) and rpc_val is not None:
                fig_g3 = go.Figure(go.Indicator(mode="number", value=float(rpc_val), domain={"x": [0, 1], "y": [0, 1]}, title={"text": "RPC ($)"}, number={"prefix": "$", "valueformat": ",.2f"}))
                fig_g3.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20), height=200)
                st.plotly_chart(fig_g3, use_container_width=True)
        st.divider()

    # Топы
    st.divider()
    st.subheader("Топы по метрикам")
    c1, c2, c3 = st.columns(3)
    with c1:
        if "RPC" in kpi.columns and kpi["RPC"].notna().any():
            top_rpc = kpi.nlargest(5, "RPC")[["chatter", "RPC"]].rename(columns={"chatter": "Чаттер"})
            st.caption("Топ-5 по RPC (revenue per chat)")
            st.dataframe(top_rpc.style.format({"RPC": "${:,.2f}"}, na_rep="—"), use_container_width=True, hide_index=True)
    with c2:
        if "PPV Open Rate %" in kpi.columns and kpi["PPV Open Rate %"].notna().any():
            top_or = kpi.nlargest(5, "PPV Open Rate %")[["chatter", "PPV Open Rate %"]].rename(columns={"chatter": "Чаттер"})
            st.caption("Топ-5 по PPV Open Rate")
            st.dataframe(top_or.style.format({"PPV Open Rate %": "{:.1f}%"}, na_rep="—"), use_container_width=True, hide_index=True)
    with c3:
        if "Conversion Score" in kpi.columns and kpi["Conversion Score"].notna().any():
            top_cs = kpi.nlargest(5, "Conversion Score")[["chatter", "Conversion Score"]].rename(columns={"chatter": "Чаттер"})
            st.caption("Топ-5 по Conversion Score")
            st.dataframe(top_cs.style.format({"Conversion Score": "{:.2f}"}, na_rep="—"), use_container_width=True, hide_index=True)
