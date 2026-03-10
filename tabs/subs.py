"""
Вкладка «Сабы» — Trial links, Tracking links, транзакции из Onlymonster API.
Одна вкладка — одна модель. Шорткаты по месяцам. Финансы по trial/tracking (API — на уровне аккаунта).
"""
import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date

from services.onlymonster import (
    get_api_config,
    fetch_accounts,
    fetch_trial_links,
    fetch_tracking_links,
    fetch_transactions,
)


def render(transactions_df, expenses_df, metrics, plan_metrics=None, selected_year=None, selected_month=None):
    st.title("🔗 Сабы — Trial и Tracking links")
    st.caption("Данные Onlymonster API: trial/tracking links, транзакции по аккаунтам.")

    api_cfg = get_api_config()
    if not api_cfg.get("url") or not api_cfg.get("api_key"):
        st.warning(
            "Onlymonster API не настроен. Добавь в `.streamlit/secrets.toml` секцию `[onlymonster]` с `api_url` и `api_key`, "
            "или в `.env`: `ONLYMONSTER_API_URL` и `ONLYMONSTER_API_KEY`."
        )
        return

    # Выбор периода (для транзакций/прибыли)
    st.subheader("Период")
    st.caption("Выбери месяц — транзакции и данные будут за этот период. Клик по шорткату сразу загружает данные.")
    _yr = selected_year or 2026
    _mo = selected_month or 1
    _default_start = date(_yr, _mo, 1)
    _default_end = date(_yr, _mo, calendar.monthrange(_yr, _mo)[1])
    # Шорткаты по месяцам (ставят subs_period_start/end и рестартят — до создания date_input)
    MONTHS_RU = {
        1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
        7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек",
    }
    today = date.today()
    shortcut_cols = st.columns(min(12, 8))
    for i, col in enumerate(shortcut_cols):
        m = today.month - i
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        lbl = f"{MONTHS_RU.get(m, m)} {y}"
        if col.button(lbl, key=f"subs_shortcut_{y}_{m}", use_container_width=True):
            last = calendar.monthrange(y, m)[1]
            st.session_state["subs_period_start"] = date(y, m, 1)
            st.session_state["subs_period_end"] = date(y, m, last)
            st.session_state["subs_auto_load"] = True
            for k in ("subs_start", "subs_end"):
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    period_start = st.session_state.get("subs_period_start", _default_start)
    period_end = st.session_state.get("subs_period_end", _default_end)
    subs_auto_load = st.session_state.pop("subs_auto_load", False)
    c1, c2 = st.columns(2)
    with c1:
        subs_start = st.date_input("Начало периода", value=period_start, key="subs_start")
    with c2:
        subs_end = st.date_input("Конец периода", value=period_end, key="subs_end")
    start = datetime(subs_start.year, subs_start.month, subs_start.day)
    end = datetime(subs_end.year, subs_end.month, subs_end.day, 23, 59, 59)
    if start > end:
        st.error("Начало периода не может быть позже конца.")
        return

    ids_set = api_cfg.get("account_ids")
    trigger_load = subs_auto_load or st.button("🔄 Загрузить данные из API", key="subs_refresh")

    if trigger_load:
        with st.spinner("Запрос к API..."):
            try:
                accounts = fetch_accounts(with_expired=True)
                if accounts is None:
                    st.error("Нет ответа от API.")
                    return

                if not accounts:
                    st.warning("В Onlymonster нет подключённых аккаунтов для твоей организации.")
                    return

                if ids_set:
                    accounts_to_fetch = [
                        a for a in accounts
                        if str(a.get("id", "")) in ids_set or str(a.get("platform_account_id", "")) in ids_set
                    ]
                    if not accounts_to_fetch:
                        st.warning(f"Ни один аккаунт не совпал с ID из конфига. Проверь ONLYMONSTER_ACCOUNT_IDS или onlymonster.account_ids.")
                        return
                else:
                    accounts_to_fetch = accounts

                all_trials = []
                all_track = []
                all_transactions = {}
                failed_accounts = []
                for acc in accounts_to_fetch:
                    pid = acc.get("platform_account_id")
                    name = acc.get("name") or acc.get("username") or str(pid)
                    if not pid:
                        continue
                    pid = str(pid)

                    try:
                        trials = fetch_trial_links(pid, start, end) or []
                    except Exception as e:
                        trials = []
                        failed_accounts.append((name or pid, str(e)[:80]))
                    for t in trials:
                        all_trials.append({
                            "Аккаунт": name,
                            "platform_account_id": pid,
                            "ID": t.get("id"),
                            "Название": t.get("name") or "—",
                            "URL": t.get("url"),
                            "Клики": t.get("clicks", 0),
                            "Claims (активаций)": t.get("claims", 0),
                            "Лимит claims": t.get("claims_limit") or "∞",
                            "Дней триала": t.get("duration_days"),
                            "Активен": "Да" if t.get("is_active") else "Нет",
                            "Истекает": t.get("expires_at") or "—",
                            "Создан": t.get("created_at"),
                            "Источник": "API trial-links",
                        })

                    try:
                        tracks = fetch_tracking_links(pid, start, end) or []
                    except Exception as e:
                        tracks = []
                        if (name or pid) not in [x for x, _ in failed_accounts]:
                            failed_accounts.append((name or pid, str(e)[:80]))
                    for tr in tracks:
                        all_track.append({
                            "Аккаунт": name,
                            "platform_account_id": pid,
                            "ID": tr.get("id"),
                            "Название": tr.get("name") or "—",
                            "URL": tr.get("url"),
                            "Клики": tr.get("clicks", 0),
                            "Сабов": tr.get("subscribers", 0),
                            "Активен": "Да" if tr.get("is_active") else "Нет",
                            "Создан": tr.get("created_at"),
                            "Источник": "API tracking-links",
                        })

                    try:
                        txns = fetch_transactions(pid, start, end) or []
                        all_transactions[name] = txns
                    except Exception:
                        all_transactions[name] = []

                txn_counts = {name: len(txns) for name, txns in all_transactions.items()}
                st.session_state["subs_trials"] = all_trials
                st.session_state["subs_transactions"] = all_transactions
                st.session_state["subs_tracking"] = all_track
                st.session_state["subs_accounts"] = accounts
                st.session_state["subs_period"] = (start, end)
                st.session_state["subs_txn_counts"] = txn_counts
                msg = f"Загружено: {len(all_trials)} trial, {len(all_track)} tracking. Транзакций из API: {', '.join(f'{k} {v}' for k, v in txn_counts.items())}"
                if failed_accounts:
                    st.warning(f"Ошибка для {len(failed_accounts)} аккаунтов: {failed_accounts[0][1]}")
                st.toast(msg, icon="✅")
                st.rerun()
            except PermissionError as e:
                st.error(str(e))
                st.info(
                    "403 Forbidden обычно означает: (1) Доступ к API ограничен твоим тарифом — свяжись с Onlymonster в Telegram @MonsterSupport_bot. "
                    "(2) Токен создан, но для этих эндпоинтов нужны доп. права."
                )
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Ошибка API: {e}")

    accounts = st.session_state.get("subs_accounts", [])
    trials = st.session_state.get("subs_trials", [])
    tracking = st.session_state.get("subs_tracking", [])
    subs_txns = st.session_state.get("subs_transactions", {})

    if not accounts and not trials and not tracking:
        st.info("Нажми «Загрузить данные из API», чтобы подтянуть аккаунты и trial/tracking links.")
        return

    period_info = st.session_state.get("subs_period")
    txn_counts = st.session_state.get("subs_txn_counts", {})
    if period_info:
        st.info(f"Trial/Tracking: ссылки созданные в период. Транзакции: за период. {period_info[0].strftime('%Y-%m-%d')} — {period_info[1].strftime('%Y-%m-%d')}")
    if txn_counts:
        counts_str = " | ".join(f"**{k}**: {v} txns" for k, v in txn_counts.items())
        st.caption(f"Транзакций из API по аккаунтам: {counts_str}")
    only_active = st.checkbox("Показывать только активные trial/tracking links", value=False, key="subs_only_active")
    st.divider()

    # Собираем уникальные модели
    model_order = [a.get("name") or a.get("username") or str(a.get("platform_account_id", "")) for a in accounts]
    model_order = [m for m in model_order if m]
    models_from_data = set()
    for t in trials:
        models_from_data.add(t.get("Аккаунт"))
    for tr in tracking:
        models_from_data.add(tr.get("Аккаунт"))
    for m in models_from_data:
        if m and m not in model_order:
            model_order.append(m)

    # Только модели с trial или tracking (после фильтра активных)
    models_with_data = []
    for m in model_order:
        mt = [t for t in trials if t.get("Аккаунт") == m]
        mk = [t for t in tracking if t.get("Аккаунт") == m]
        if only_active:
            mt = [t for t in mt if t.get("Активен") == "Да"]
            mk = [t for t in mk if t.get("Активен") == "Да"]
        if mt or mk:
            models_with_data.append(m)

    model_tabs = st.tabs(models_with_data) if models_with_data else []
    for mi, model_name in enumerate(models_with_data):
        model_trials = [t for t in trials if t.get("Аккаунт") == model_name]
        model_tracking = [t for t in tracking if t.get("Аккаунт") == model_name]
        if only_active:
            model_trials = [t for t in model_trials if t.get("Активен") == "Да"]
            model_tracking = [t for t in model_tracking if t.get("Активен") == "Да"]

        # Финансовые метрики (status=done или альтернативы)
        model_txns = subs_txns.get(model_name, [])
        def _is_done(t):
            s = (t.get("status") or "").strip().lower()
            return s in ("done", "completed", "success", "ok", "finished") or not s
        done_txns = [t for t in model_txns if _is_done(t)]
        if not done_txns and model_txns:
            done_txns = model_txns  # fallback: если ни один статус не распознан — считаем все
        total_rev = sum(float(t.get("amount", 0) or 0) for t in done_txns)
        txn_count = len(done_txns)
        avg_check = total_rev / txn_count if txn_count > 0 else 0
        sub_txns = [t for t in done_txns if "subscription" in str(t.get("type", "")).lower()]
        sub_count = len(sub_txns)
        total_subs_track = sum(t.get("Сабов", 0) or 0 for t in model_tracking)
        total_trials_claimed = sum(t.get("Claims (активаций)", 0) or 0 for t in model_trials)
        total_clicks = sum(t.get("Клики", 0) or 0 for t in model_tracking) + sum(t.get("Клики", 0) or 0 for t in model_trials)

        with model_tabs[mi]:
            st.caption(f"Выручка: ${total_rev:,.0f} | Транзакций: {txn_count} | Ср. чек: ${avg_check:,.0f} | Trial claims: {total_trials_claimed} | Сабов (track): {int(total_subs_track)}")
            tab_trial, tab_track, tab_finance = st.tabs(["Trial links", "Tracking links", "Финансы"])

            with tab_trial:
                if model_trials:
                    df = pd.DataFrame(model_trials)
                    cols = ["Название", "URL", "Клики", "Claims (активаций)", "Лимит claims", "Дней триала", "Активен", "Создан"]
                    cols = [c for c in cols if c in df.columns]
                    try:
                        from st_aggrid import AgGrid, GridOptionsBuilder
                        gb = GridOptionsBuilder.from_dataframe(df[cols])
                        gb.configure_default_column(sortable=True, filterable=True, resizable=True)
                        gb.configure_column("URL", wrapText=True)
                        AgGrid(df[cols], gridOptions=gb.build(), theme="streamlit", height=min(250, 80 + len(df) * 40), fit_columns_on_grid_load=True, key=f"subs_trial_{mi}")
                    except ImportError:
                        st.dataframe(df[cols], use_container_width=True, hide_index=True)
                    with st.expander("Ссылки для копирования"):
                        for idx, t in enumerate(model_trials):
                            st.text_input(t.get("Название", t.get("ID", "")), value=t.get("URL", ""), key=f"trial_{mi}_{idx}")
                else:
                    st.caption("Нет trial links.")

            with tab_track:
                if model_tracking:
                    df = pd.DataFrame(model_tracking)
                    cols = ["Название", "URL", "Клики", "Сабов", "Активен", "Создан"]
                    cols = [c for c in cols if c in df.columns]
                    try:
                        from st_aggrid import AgGrid, GridOptionsBuilder
                        gb = GridOptionsBuilder.from_dataframe(df[cols])
                        gb.configure_default_column(sortable=True, filterable=True, resizable=True)
                        gb.configure_column("URL", wrapText=True)
                        AgGrid(df[cols], gridOptions=gb.build(), theme="streamlit", height=min(250, 80 + len(df) * 40), fit_columns_on_grid_load=True, key=f"subs_track_{mi}")
                    except ImportError:
                        st.dataframe(df[cols], use_container_width=True, hide_index=True)
                    total_subs = sum(t.get("Сабов", 0) or 0 for t in model_tracking)
                    total_clicks = sum(t.get("Клики", 0) or 0 for t in model_tracking)
                    st.caption(f"Сабов: {int(total_subs)} | Кликов: {int(total_clicks)}")
                else:
                    st.caption("Нет tracking links.")

            with tab_finance:
                # Trial links — метрики (без выручки, API не даёт)
                st.subheader("Trial links")
                total_trials_claims = sum(t.get("Claims (активаций)", 0) or 0 for t in model_trials)
                total_trials_clicks = sum(t.get("Клики", 0) or 0 for t in model_trials)
                c1, c2 = st.columns(2)
                c1.metric("Claims (активаций)", total_trials_claims)
                c2.metric("Кликов", total_trials_clicks)
                st.caption("Показаны trial links, созданные в выбранный период. Claims и клики — суммарно. Выручка — только в дашборде Onlymonster.")

                st.divider()

                # Tracking links — метрики (без выручки, API не даёт)
                st.subheader("Tracking links")
                total_track_subs = sum(t.get("Сабов", 0) or 0 for t in model_tracking)
                total_track_clicks = sum(t.get("Клики", 0) or 0 for t in model_tracking)
                c3, c4 = st.columns(2)
                c3.metric("Сабов", int(total_track_subs))
                c4.metric("Кликов", total_track_clicks)
                st.caption("Показаны tracking links, созданные в выбранный период. Сабов и кликов — суммарно. Выручка — только в дашборде Onlymonster.")

                st.divider()

                # Общие финансы по аккаунту
                st.subheader("Общие финансы по аккаунту")
                st.caption("Транзакции OnlyFans за выбранный период (status=done; при неизвестных статусах — все).")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Выручка", f"${total_rev:,.2f}")
                col2.metric("Транзакций", txn_count)
                col3.metric("Средний чек", f"${avg_check:,.2f}" if avg_check else "—")
                col4.metric("Подписок", sub_count)

                # Диагностика API
                raw_count = len(model_txns)
                status_values = {}
                for t in model_txns:
                    s = str(t.get("status", "—") or "—")
                    status_values[s] = status_values.get(s, 0) + 1
                with st.expander("🔧 Диагностика API", expanded=(raw_count > 0 and txn_count == 0)):
                    pid = (model_tracking[0].get("platform_account_id") if model_tracking else None) or (model_trials[0].get("platform_account_id") if model_trials else None)
                    st.text(f"Аккаунт: {model_name} | platform_account_id: {pid or '—'}")
                    st.text(f"Транзакций из API (всего): {raw_count} | учтено (done/completed): {txn_count}")
                    st.text(f"Status в API: {dict(status_values)}")
                    if raw_count == 0:
                        st.caption("0 транзакций — проверь: период, синк Onlymonster с OnlyFans, доступ к API транзакциям.")

                if done_txns:
                    by_type = {}
                    for t in done_txns:
                        typ = str(t.get("type", "unknown"))
                        amt = float(t.get("amount", 0) or 0)
                        by_type[typ] = by_type.get(typ, {"sum": 0, "count": 0})
                        by_type[typ]["sum"] += amt
                        by_type[typ]["count"] += 1
                    type_df = pd.DataFrame([{"Тип": k, "Сумма": v["sum"], "Кол-во": v["count"]} for k, v in by_type.items()]).sort_values("Сумма", ascending=False)
                    st.subheader("По типу транзакции")
                    st.dataframe(type_df.style.format({"Сумма": "${:,.2f}"}), use_container_width=True, hide_index=True)

                    # Разбивка по спендерам (fan)
                    by_fan = {}
                    for t in done_txns:
                        fan = t.get("fan") or {}
                        fan_id = fan.get("id") if isinstance(fan, dict) else str(fan) or "unknown"
                        fan_id = str(fan_id) if fan_id else "unknown"
                        amt = float(t.get("amount", 0) or 0)
                        by_fan[fan_id] = by_fan.get(fan_id, {"sum": 0, "count": 0})
                        by_fan[fan_id]["sum"] += amt
                        by_fan[fan_id]["count"] += 1
                    spender_rows = [
                        {
                            "Fan ID": fid,
                            "Сумма": d["sum"],
                            "Транзакций": d["count"],
                            "Ср. чек": d["sum"] / d["count"] if d["count"] > 0 else 0,
                        }
                        for fid, d in by_fan.items()
                    ]
                    spender_df = pd.DataFrame(spender_rows).sort_values("Сумма", ascending=False)
                    st.subheader("По спендерам")
                    st.dataframe(
                        spender_df.style.format({"Сумма": "${:,.2f}", "Ср. чек": "${:,.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(f"Спендеров: {len(by_fan)} (фан, сделавших ≥1 покупку)")
                st.caption("Подписок = recurring subscription. «Оставили» (churn) — API не отдаёт.")
