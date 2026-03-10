# 🚀 Запуск Skynet UI — пошаговый гид

Следуй шагам по порядку. Всё готово — тебе нужно только зарегистрироваться и вставить ключи.

---

## Шаг 0: Что тебе понадобится

| Сервис | Для чего | Платно? |
|--------|----------|---------|
| **GitHub** | Хранение кода | Бесплатно |
| **Streamlit Cloud** | Хостинг дашборда | Бесплатно |
| **Neon** или **Supabase** | PostgreSQL в облаке | Бесплатный тариф |
| **Notion** | У тебя уже есть | — |
| **OpenAI** | AI-анализ (вкладка AI) | От $5 пополнения |

---

## Шаг 1: PostgreSQL в облаке

### Вариант A: Neon (проще)

1. Зайди на **[neon.tech](https://neon.tech)**
2. Нажми **Sign up** → войди через GitHub
3. Создай проект (название любое, например `skynet`)
4. Скопируй данные подключения:
   - **Host** (что-то вроде `ep-xxx.us-east-2.aws.neon.tech`)
   - **Database** (обычно `neondb`)
   - **User** (обычно твой ник)
   - **Password** (показан один раз — сохрани!)

### Вариант B: Supabase

1. Зайди на **[supabase.com](https://supabase.com)**
2. **Start your project** → войди через GitHub
3. Создай проект
4. **Settings** → **Database** → скопируй:
   - Host, Database, User, Password (из connection string)

---

## Шаг 2: Создать базу данных

База `skynet` уже должна существовать. В Neon она создаётся автоматически. Если нет — в консоли SQL выполни:

```sql
CREATE TABLE IF NOT EXISTS expenses (
  id SERIAL PRIMARY KEY,
  notion_id TEXT UNIQUE,
  date DATE,
  model TEXT,
  category TEXT,
  vendor TEXT,
  payment_method TEXT,
  amount NUMERIC
);

CREATE TABLE IF NOT EXISTS transactions (
  id SERIAL PRIMARY KEY,
  date DATE,
  model TEXT,
  chatter TEXT,
  amount NUMERIC,
  shift_id TEXT,
  shift_name TEXT,
  month_source TEXT,
  synced_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shifts (
  id TEXT PRIMARY KEY,
  name TEXT
);
```

---

## Шаг 3: GitHub

1. Зайди на **[github.com](https://github.com)**
2. **New repository** → название `skynetUI`, Public
3. В терминале в папке проекта:

```bash
git init
git add .
git commit -m "Initial"
git branch -M main
git remote add origin https://github.com/ТВОЙ_НИК/skynetUI.git
git push -u origin main
```

---

## Шаг 4: Streamlit Cloud (хостинг дашборда)

1. Зайди на **[share.streamlit.io](https://share.streamlit.io)**
2. **Sign in with GitHub**
3. **New app** → выбери репозиторий `skynetUI`, branch `main`
4. **Main file path**: `app.py`
5. **Advanced settings** → **Secrets** — вставь:

```toml
db_host = "ТВОЙ_HOST_ИЗ_NEON"
db_port = 5432
db_name = "neondb"
db_user = "ТВОЙ_USER"
db_password = "ТВОЙ_PASSWORD"

openai_api_key = "sk-..."

[onlymonster]
api_url = "https://omapi.onlymonster.ai"
api_key = "ТВОЙ_OM_КЛЮЧ"
```

6. **Deploy**

Через минуту дашборд откроется по ссылке.

---

## Шаг 5: Notion API (для синхронизации)

1. Зайди на **[notion.so/my-integrations](https://www.notion.so/my-integrations)**
2. **New integration** → название `Skynet Sync`
3. Скопируй **Internal Integration Secret** (начинается с `ntn_` или `secret_`)
4. Открой свои базы в Notion (расходы, транзакции) → **Share** → подключи интеграцию

---

## Шаг 6: Конфиг синхронизации

Если `config/notion_sync.json` уже создан и заполнен — шаг выполнен, переходи к Шагу 7.

Иначе:
1. Скопируй конфиг: `copy config\notion_sync.example.json config\notion_sync.json`
2. Вставь свои ID баз (из URL Notion: `notion.so/workspace/XXXXX?v=...` → `XXXXX`):

```json
{
  "expenses": {
    "database_ids": ["ID_ДЕКАБРЯ", "ID_ЯНВАРЯ", "ID_ФЕВРАЛЯ", "ID_МАРТА"]
  },
  "transactions": {
    "database_id": "ID_БАЗЫ_ТРАНЗАКЦИЙ",
    "month_overrides": {
      "2024-12": {
        "database_id": "ID_ДЕКАБРЯ_ТРАНЗАКЦИЙ",
        "shift_type": "select"
      }
    }
  }
}
```

---

## Шаг 7: Авто-синхронизация (3 раза в сутки)

### GitHub Actions

1. В репо **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** — добавь:
   - `NOTION_TOKEN` = твой Notion integration secret
   - `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD` = из Neon

Workflow `.github/workflows/sync.yml` уже есть — он запустится по расписанию.

### Или cron (если БД на своем сервере)

```bash
0 0,8,16 * * * cd /path/to/skynetUI && venv/bin/python scripts/sync_notion_full.py >> /tmp/sync.log 2>&1
```

---

## Шаг 8: Проверка

- Дашборд: твоя ссылка `xxx.streamlit.app`
- Данные: после первой синхронизации появятся в дашборде
- AI: работает, если добавлен `openai_api_key`

---

## Чек-лист

- [ ] Neon/Supabase — есть Host, User, Password
- [ ] GitHub — репо создан, код запушен
- [ ] Streamlit Cloud — app задеплоен, secrets вставлены
- [ ] Notion — интеграция создана, базы расшарены
- [ ] config/notion_sync.json — ID баз указаны
- [ ] GitHub Actions secrets — добавлены (для авто-синка)

---

## Если что-то не работает

- **Дашборд пустой** → проверь secrets (db_host, пароль), запусти sync вручную
- **Sync падает** → проверь NOTION_TOKEN, права интеграции на базы
- **AI не отвечает** → проверь openai_api_key, баланс OpenAI
