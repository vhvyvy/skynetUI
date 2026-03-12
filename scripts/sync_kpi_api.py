"""
Синхронизация KPI из Onlymonster API в chatter_kpi.
Для GitHub Actions sync-client — сохраняет данные в PostgreSQL.
Запуск: python scripts/sync_kpi_api.py
Env: PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, ONLYMONSTER_API_KEY, ONLYMONSTER_API_URL
"""
import os
import sys
import calendar
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Без Streamlit — только env
os.environ.setdefault("ONLYMONSTER_API_URL", "https://omapi.onlymonster.ai")


def main():
    from services.onlymonster import fetch_chatter_metrics, get_api_config
    from services.chatter_kpi import save_kpi_batch

    cfg = get_api_config()
    if not cfg.get("url") or not cfg.get("api_key"):
        print("ONLYMONSTER_API_KEY и ONLYMONSTER_API_URL обязательны")
        sys.exit(1)

    now = datetime.utcnow()
    for year, month in [(now.year, now.month), (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)]:
        start = datetime(year, month, 1)
        end = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
        try:
            result = fetch_chatter_metrics(start_date=start, end_date=end)
            if result:
                save_kpi_batch(year, month, result)
                print(f"KPI: сохранено {len(result)} записей за {year}-{month:02d}")
            else:
                print(f"KPI: 0 записей за {year}-{month:02d}")
        except Exception as e:
            print(f"KPI {year}-{month}: {e}")


if __name__ == "__main__":
    main()
