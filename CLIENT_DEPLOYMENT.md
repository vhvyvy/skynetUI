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
- [ ] GitHub Actions: `NOTION_TOKEN`, `PG_*` для авто-синка
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
# 3. Variables:
#    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
#    NOTION_TOKEN
#    OPENAI_API_KEY (опц.)
#    ONLYMONSTER_API_KEY=om_token_xxx
#    ONLYMONSTER_API_URL=https://omapi.onlymonster.ai
# 4. config/notion_sync.json — закоммитить или собирать из env
```

Если `config/notion_sync.json` закоммичен с ID баз клиента — всё подхватится. Иначе создай его вручную в репо для клиента.
