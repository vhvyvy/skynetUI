# Деплой и авто-синхронизация

## 1. Публикация (GitHub)

```bash
git init
git add .
git commit -m "Initial"
git remote add origin https://github.com/YOUR_USER/skynetUI.git
git push -u origin main
```

`.gitignore` исключает: `.env`, `secrets.toml`, `venv/`, `data/*.json`, `config/notion_sync.json`, `skynet/.env`.

---

## 2. Хостинг приложения

### Streamlit Community Cloud

1. [share.streamlit.io](https://share.streamlit.io) → подключи репо
2. **Main file path** = `app.py`
3. **Secrets** (TOML):

```toml
db_host = "хост"
db_port = 5432
db_name = "skynet"
db_user = "postgres"
db_password = "пароль"
openai_api_key = "sk-..."
[onlymonster]
api_url = "https://omapi.onlymonster.ai"
api_key = "..."
```

PostgreSQL: Neon, Supabase, Railway.

---

## 3. Синхронизация Notion → PostgreSQL

Скрипт `scripts/sync_notion_full.py` объединяет логику из `skynet/`:
- **expenses** — расходы из нескольких Notion-баз (по месяцу)
- **transactions** — транзакции, поддержка разных схем (Смена: relation или select)

### Конфиг

```bash
cp config/notion_sync.example.json config/notion_sync.json
```

В `config/notion_sync.json`:
- **expenses.database_ids** — ID баз расходов (Dec, Jan, Feb, Mar…)
- **transactions.database_id** — ID базы транзакций
- **transactions.month_overrides** — для месяцев с другой схемой, напр. `"2024-12": {"database_id": "...", "shift_type": "select"}`

### .env

```env
NOTION_TOKEN=ntn_xxx
PG_HOST=localhost
PG_PORT=5432
PG_DB=skynet
PG_USER=postgres
PG_PASSWORD=...
```

### Запуск

```bash
python scripts/sync_notion_full.py                    # всё
python scripts/sync_notion_full.py --expenses         # только расходы
python scripts/sync_notion_full.py --transactions    # только транзакции
python scripts/sync_notion_full.py --transactions --month 2024-12  # декабрь
```

### Cron (3 раза в сутки)

```
0 0,8,16 * * * cd /path/to/skynetUI && venv/bin/python scripts/sync_notion_full.py >> /tmp/sync.log 2>&1
```

### GitHub Actions

В `.github/workflows/sync.yml` добавь секреты: `NOTION_TOKEN`, `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`.  
Для config: либо закоммить `config/notion_sync.json` (ID баз), либо создать его в workflow из секретов.

---

## 4. Папка skynet/

Локальные скрипты `sync_expenses.py`, `sync_month.py`, `sync_DEC.py` — оригиналы.  
Везде используется `scripts/sync_notion_full.py` с `config/notion_sync.json`.  
`skynet/.env` не коммитится.
