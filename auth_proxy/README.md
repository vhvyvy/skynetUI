# Auth для Skynet UI

Вход по паролю и **HTTP-only cookie** (сессия 7 дней). Два варианта деплоя.

## Рекомендуется: Docker с nginx (безопасно, дашборд грузится)

В репозитории есть **Dockerfile**: nginx проверяет cookie через `auth_request`, проксирует всё (включая WebSocket) в Streamlit. Сервис входа только отдаёт форму и `/auth/verify`.

**Railway:** подключи репо, включи деплой из Dockerfile (по умолчанию подхватится). В Variables задай `APP_PASSWORD`, при HTTPS — `AUTH_PROXY_SECURE=true`, плюс БД/Notion и т.д. Команду Start не переопределяй — в образе уже прописан запуск nginx + auth + Streamlit.

**Локально:** `docker build -t skynet . && docker run -e APP_PASSWORD=пароль -e PORT=8080 -p 8080:8080 skynet` — открой http://localhost:8080.

---

## Вариант без Docker (только форма входа в Streamlit)

Если не используешь Docker, можно запускать только Streamlit с паролем в приложении:

- **Build** без Docker (Nixpacks), **Start:** `python run_streamlit_port.py`
- **Variables:** `APP_PASSWORD` и остальное. Переменную `AUTH_PROXY` не ставь.
- Вход по форме в Streamlit (сессия может сбрасываться при обновлении страницы).

## Запуск (старый прокси на FastAPI, без nginx)

### Вариант 1: Два процесса вручную

В одном терминале (из корня репозитория):

```bash
streamlit run app.py --server.port=8501 --server.address=127.0.0.1
```

В другом:

```bash
cd auth_proxy
pip install -r requirements.txt
set APP_PASSWORD=твой_пароль
python main.py
```

Открывай **http://localhost:8000** — там будет форма входа, после входа — дашборд.

### Вариант 2: Всё одним скриптом

Из **корня** репозитория:

```bash
set APP_PASSWORD=твой_пароль
python auth_proxy/run_with_streamlit.py
```

Прокси будет на порту 8000, Streamlit поднимается автоматически на 8501.

### Переменные окружения

| Переменная | Описание |
|------------|----------|
| `APP_PASSWORD` или `ADMIN_PASSWORD` | Пароль входа. Если не задан — прокси не проверяет авторизацию (всё пускает). |
| `STREAMLIT_URL` | URL Streamlit (по умолчанию `http://127.0.0.1:8501`). |
| `PORT` | Порт прокси (по умолчанию 8000). |
| `AUTH_PROXY_SECURE` | `true` — cookie с флагом Secure (для HTTPS). |

### Выход

Открыть в браузере: **http://localhost:8000/logout** — cookie удалится и редирект на форму входа.

## Деплой (Railway и др.)

1. **Одна форма входа**  
   Задай в переменных окружения `AUTH_PROXY=1`. Тогда Streamlit не будет показывать свою форму входа — весь контроль доступа только через прокси. Пароль задаётся в `APP_PASSWORD`.

2. **Один сервис**  
   Запускай один процесс через `run_with_streamlit.py`, чтобы в контейнере работали и Streamlit, и прокси:
   - Команда запуска: `python auth_proxy/run_with_streamlit.py`
   - Рабочая директория: корень репозитория
   - В env задай `APP_PASSWORD` и при необходимости `STREAMLIT_URL` (для того же хоста можно оставить по умолчанию).

3. **Два сервиса**  
   Можно поднять Streamlit и прокси разными сервисами; тогда у прокси задай `STREAMLIT_URL` на внутренний URL Streamlit.

4. **HTTPS**  
   На продакшене выстави `AUTH_PROXY_SECURE=true`, чтобы cookie ставился с флагом Secure.

## Эндпоинт для nginx auth_request

Если ставишь nginx перед прокси:

- `GET /auth/verify` — возвращает 200 при валидной cookie, 401 при отсутствии/невалидной.  
  В nginx: `auth_request /auth/verify;` (проксировать на этот сервис).
