# Развёртывание для клиента — платный хостинг

План: взять версию с GitHub (без локальных правок), разместить на быстром платном хостинге, привязать к ключам и базам клиента.

---

## 1. Чистая версия с GitHub

**Важно:** не использовать локальную папку — там могут быть правки.

```bash
# Новый каталог для клиента
git clone https://github.com/ТВОЙ_НИК/skynetUI.git skynetUI-client
cd skynetUI-client

# Опционально: отдельный branch или репо для клиента
# git remote add client-repo https://github.com/ТВОЙ_НИК/skynetUI-client.git
```

Либо создать новый приватный репо для клиента и push только нужного кода.

---

## 2. Платный хостинг (варианты)

| Платформа            | Цена         | Скорость | Подходит для |
|----------------------|--------------|----------|--------------|
| **Railway**          | от ~$5/мес   | быстрый  | Рекомендуется |
| **Render**           | от $7/мес    | средний  | Да |
| **Streamlit Cloud Team** | от $250/мес | быстрый  | Enterprise |
| **Fly.io**           | от ~$5/мес   | быстрый  | Опытным |

### Railway (рекомендуется)

1. [railway.app](https://railway.app) → Start a New Project
2. **Deploy from GitHub** → выбери репо
3. **Variables** добавь (см. шаблон ниже)
4. **Settings** → Build: `pip install -r requirements.txt`, Start: `streamlit run app.py --server.port $PORT`
5. Платный план — быстрый инстанс

**Вход по паролю и cookie (рекомендуется):** чтобы не светить дашборд без входа и запоминать сессию на 7 дней, используй прокси из папки `auth_proxy`. В Railway: Build как обычно (`pip install -r requirements.txt`), дополнительно установи зависимости прокси: `pip install -r auth_proxy/requirements.txt`. Start: `python auth_proxy/run_with_streamlit.py`. Переменные: `APP_PASSWORD`, при HTTPS — `AUTH_PROXY_SECURE=true`. Подробнее: [auth_proxy/README.md](auth_proxy/README.md).

### Render

1. [render.com](https://render.com) → New → Web Service
2. Подключи GitHub-репо
3. Build: `pip install -r requirements.txt`
4. Start: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. В **Environment** добавь переменные

---

## 3. Шаблон конфигурации клиента

### Переменные окружения / Secrets (TOML для Streamlit)

```toml
# PostgreSQL — БД клиента
db_host = "хост.клиента.neon.tech"
db_port = 5432
db_name = "neondb"
db_user = "пользователь"
db_password = "пароль"

# OpenAI (AI-вкладка)
openai_api_key = "sk-..."

# Onlymonster
[onlymonster]
api_url = "https://omapi.onlymonster.ai"
api_key = "om_token_КЛЮЧ_КЛИЕНТА"
account_ids = "ID1, ID2, ID3"   # опционально: только эти аккаунты

# Notion — для авто-синка
# NOTION_TOKEN и PG_* лучше задать в Variables хостинга
```

### config/notion_sync.json

```json
{
  "expenses": {
    "database_ids": ["ID_БАЗЫ_РАСХОДОВ_1", "ID_БАЗЫ_РАСХОДОВ_2"]
  },
  "transactions": {
    "database_id": "ID_БАЗЫ_ТРАНЗАКЦИЙ",
    "month_overrides": {}
  }
}
```

### База данных

Таблицы `expenses`, `transactions`, `shifts` — как в `START_HERE.md` (шаг 2). Миграции не нужны, схема та же.

---

## 4. Чек-лист для клиента

- [ ] Код: клон с GitHub (чистая версия)
- [ ] PostgreSQL: база клиента (Neon/Supabase/Railway)
- [ ] Notion: интеграция + ID баз расходов и транзакций
- [ ] Onlymonster: `api_key` клиента, при необходимости `account_ids`
- [ ] OpenAI: ключ (если нужна AI-вкладка)
- [ ] Хостинг: Railway/Render — переменные заданы
- [ ] GitHub Actions: `PG_*_CLIENT`, `NOTION_TOKEN_CLIENT`, `NOTION_TRANSACTIONS_DATABASE_ID_CLIENT`, `NOTION_EXPENSES_DATABASE_IDS_CLIENT`, `ONLYMONSTER_*_CLIENT` для авто-синка
- [ ] Домен/ссылка: передать клиенту

---

## 5. Отличия от бесплатного

| Параметр     | Бесплатно (Streamlit Cloud) | Платно (Railway/Render) |
|--------------|-----------------------------|---------------------------|
| Скорость     | Медленнее, cold start       | Быстрее, без простоя      |
| Ресурсы      | Ограничены                  | Больше RAM/CPU            |
| Кастомизация | Нет                         | Любые env vars            |
| Домен        | streamlit.app               | Можно свой домен          |

---

## 6. Деплой (Railway)

```bash
# 1. Репо на GitHub (чистая версия)
# 2. railway.app → New Project → Deploy from GitHub
# 3. Variables — см. раздел 7
# 4. GitHub Secrets для sync-client — см. раздел 8
```

**Важно:** Sync-client НЕ использует config/notion_sync.json — только env-переменные из GitHub Secrets. Личный sync использует config. Так они не пересекаются.

---

## 7. Variables клиента (Railway)

Добавь в Railway → skynetUI → Variables:

| Переменная | Описание |
|------------|----------|
| `CLIENT_MODE` | `1` — клиентская версия (без retention) |
| `DATABASE_PUBLIC_URL` | Reference: `${{Postgres.DATABASE_PUBLIC_URL}}` |
| `NOTION_TOKEN` | Токен Notion |
| `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD` | Если не используешь Reference |
| `ONLYMONSTER_API_KEY` | Токен Onlymonster (начинается с `om_token_`) |
| `ONLYMONSTER_API_URL` | `https://omapi.onlymonster.ai` |
| `ONLYMONSTER_ACCOUNT_IDS` | `27910,162962` — ID аккаунтов (опц.) |
| `OPENAI_API_KEY` | Ключ OpenAI для вкладки AI |

**Маппинг Onlymonster ID → ник** (для KPI): `data/chatter_id_to_name.json`. У клиента: 27910→@JI9JI9, 162962→@pukvochko (уже добавлено в репо).

---

## 8. GitHub Actions: Secrets для Sync Client

Чтобы sync-client не пересекался с личным sync, нужны **отдельные** секреты. GitHub → Settings → Secrets and variables → Actions:

| Секрет | Описание |
|--------|----------|
| `PG_HOST_CLIENT` | Хост БД клиента (Railway Postgres) |
| `PG_PORT_CLIENT` | 5432 |
| `PG_DB_CLIENT` | Имя БД клиента |
| `PG_USER_CLIENT` | Пользователь |
| `PG_PASSWORD_CLIENT` | Пароль |
| `NOTION_TOKEN_CLIENT` | Токен Notion интеграции **клиента** |
| `NOTION_TRANSACTIONS_DATABASE_ID_CLIENT` | ID базы транзакций в Notion **клиента** |
| `NOTION_EXPENSES_DATABASE_IDS_CLIENT` | ID баз расходов (через запятую) **клиента** |
| `ONLYMONSTER_API_KEY_CLIENT` | Токен Onlymonster клиента |
| `ONLYMONSTER_API_URL_CLIENT` | `https://omapi.onlymonster.ai` |

**Личный sync** использует `PG_HOST`, `NOTION_TOKEN` и `config/notion_sync.json` — это твои данные. Они не пересекаются.
