# Skynet UI

Дашборд для управления OnlyFans-агентством: финансы, чаттеры, KPI, планы, AI-аналитика.

> **Старт:** открой [START_HERE.md](START_HERE.md) — пошаговый гид по запуску и деплою.

## Возможности

- **Обзор** — выручка, расходы, прибыль, маржа, прогноз на месяц
- **Финансы** — детализация, распределение
- **Чаттеры** — выручка по моделям и чаттерам
- **KPI** — PPV Open Rate, APV, RPC, Conversion Score (Onlymonster API)
- **Планы** — гибкий % чаттера по выполнению плана
- **Структура** — модель × чаттер
- **События** — контекст для AI (новая модель, ушёл чаттер и т.д.)
- **AI** — анализ на GPT-4o с полным контекстом данных

## Быстрый старт

```bash
git clone https://github.com/YOUR_USER/skynetUI.git
cd skynetUI
python -m venv venv
venv\Scripts\activate   # Windows
# или: source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

Создай `.streamlit/secrets.toml`:

```toml
db_host = "localhost"
db_port = 5432
db_name = "skynet"
db_user = "postgres"
db_password = "YOUR_PASSWORD"

# Опционально
openai_api_key = "sk-..."
[onlymonster]
api_url = "https://omapi.onlymonster.ai"
api_key = "YOUR_OM_KEY"
```

Или используй `.env` с `OPENAI_API_KEY`.

```bash
streamlit run app.py
```

## Деплой и авто-синхронизация

Подробная инструкция: [DEPLOYMENT.md](DEPLOYMENT.md)

- Хостинг: Streamlit Cloud, Railway, Render
- Авто-синхронизация Notion → PostgreSQL 3 раза в сутки (cron / GitHub Actions)
