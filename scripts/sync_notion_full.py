"""
Унифицированная синхронизация Notion → PostgreSQL.
Объединяет логику из skynet/sync_expenses.py, sync_month.py, sync_DEC.py.

Запуск:
  python scripts/sync_notion_full.py              # всё (expenses + transactions)
  python scripts/sync_notion_full.py --expenses   # только расходы
  python scripts/sync_notion_full.py --transactions  # только транзакции
  python scripts/sync_notion_full.py --transactions --month 2024-12  # декабрь (shift_type=select)

Конфиг: config/notion_sync.json (скопируй из config/notion_sync.example.json)
Env: NOTION_TOKEN, PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import psycopg2
from dotenv import load_dotenv

root = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(root, ".env"))
load_dotenv(os.path.join(root, "skynet", ".env"))
load_dotenv(os.path.join(root, "services", ".env"))

# Для клиентской версии можно передавать переменные с суффиксом _CLIENT.
# Порядок приоритета:
#  - токен: NOTION_TOKEN → NOTION_TOKEN_CLIENT → NOTION_API_KEY
#  - БД: PG_*_CLIENT → PG_* → DB_* → fallback
NOTION_TOKEN = (
    os.getenv("NOTION_TOKEN")
    or os.getenv("NOTION_TOKEN_CLIENT")
    or os.getenv("NOTION_API_KEY")
)
PG_HOST = (
    os.getenv("PG_HOST_CLIENT")
    or os.getenv("PG_HOST")
    or os.getenv("DB_HOST")
    or "localhost"
)
PG_PORT = int(
    os.getenv("PG_PORT_CLIENT")
    or os.getenv("PG_PORT")
    or os.getenv("DB_PORT")
    or "5432"
)
PG_DB = (
    os.getenv("PG_DB_CLIENT")
    or os.getenv("PG_DB")
    or os.getenv("DB_NAME")
    or "skynet"
)
PG_USER = (
    os.getenv("PG_USER_CLIENT")
    or os.getenv("PG_USER")
    or os.getenv("DB_USER")
    or "postgres"
)
PG_PASSWORD = (
    os.getenv("PG_PASSWORD_CLIENT")
    or os.getenv("PG_PASSWORD")
    or os.getenv("DB_PASSWORD")
    or os.getenv("DB_PASS")
    or ""
)

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def load_config():
    for name in ("notion_sync.json", "notion_sync.example.json"):
        path = os.path.join(root, "config", name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def get_connection():
    kwargs = dict(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
    )
    if PG_HOST and (".neon.tech" in PG_HOST or "proxy.rlwy.net" in PG_HOST):
        kwargs["sslmode"] = "require"
    return psycopg2.connect(**kwargs)


def _resolve_page_to_database_id(page_id):
    """Если ID — страница с вложенной базой, возвращаем ID базы. Иначе None."""
    block_id = page_id.replace("-", "")  # Notion API принимает с дефисами или без
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    try:
        resp = requests.get(url, headers=HEADERS, params={"page_size": 50}, timeout=15)
        data = resp.json()
        if data.get("object") == "error":
            return None
        for block in data.get("results", []):
            if block.get("type") == "child_database":
                # id блока child_database = id базы данных
                return block.get("id", "").replace("-", "")
        return None
    except Exception:
        return None


def fetch_notion_db(db_id):
    """Загружает страницы из Notion database. Если db_id — страница, пробует найти вложенную базу."""
    def _fetch(actual_id):
        url = f"https://api.notion.com/v1/databases/{actual_id}/query"
        results = []
        start_cursor = None
        while True:
            payload = {"start_cursor": start_cursor} if start_cursor else {}
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
            data = resp.json()
            if data.get("object") == "error" or data.get("code"):
                return None, data.get("message", "unknown")
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")
        return results, None

    out, err = _fetch(db_id)
    if err and "page, not a database" in str(err):
        resolved = _resolve_page_to_database_id(db_id)
        if resolved:
            print(f"  [expenses] ID {db_id[:8]}... — страница, найдена база {resolved[:8]}...")
            out, err = _fetch(resolved)
    if err:
        print(f"  Notion API error (expenses {db_id[:8]}...): {err}")
        return []
    return out


def _title(prop):
    if prop and prop.get("type") == "title" and prop.get("title"):
        return prop["title"][0].get("plain_text", "").strip()
    return None


def _select(prop):
    if not prop:
        return None
    t = prop.get("type")
    if t == "select" and prop.get("select"):
        return prop["select"].get("name")
    if t == "multi_select" and prop.get("multi_select"):
        return prop["multi_select"][0].get("name")
    if t == "rich_text" and prop.get("rich_text"):
        return prop["rich_text"][0].get("plain_text")
    return None


def _number(prop):
    if prop and prop.get("type") == "number":
        return prop.get("number")
    return None


def _date(prop):
    if prop and prop.get("type") == "date" and prop.get("date"):
        return prop["date"].get("start")
    return None


def resolve_relation(page_id, cache=None):
    if not page_id:
        return None
    cache = cache or {}
    if page_id in cache:
        return cache[page_id]
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    data = resp.json()
    for p in data.get("properties", {}).values():
        if p.get("type") == "title" and p.get("title"):
            title = p["title"][0].get("plain_text", "").strip()
            cache[page_id] = title
            return title
    return None


# ==================== EXPENSES ====================

def sync_expenses(config):
    # Env переопределяет config — для разделения личный/клиент (разные секреты)
    # При NOTION_SYNC_CLIENT=1 НЕ используем config — только env (защита от пересечения)
    is_client = os.getenv("NOTION_SYNC_CLIENT", "").strip().lower() in ("1", "true", "yes")
    ids_env = (
        os.getenv("NOTION_EXPENSES_DATABASE_IDS_CLIENT")
        or os.getenv("NOTION_EXPENSES_DATABASE_IDS")
        or os.getenv("NOTION_EXPENSES_DATABASE_ID")
    )
    if ids_env:
        db_ids = [x.strip() for x in str(ids_env).split(",") if x.strip()]
    elif not is_client:
        db_ids = config.get("expenses", {}).get("database_ids", [])
    else:
        db_ids = []
    if not db_ids:
        print("Нет database_ids для expenses")
        return

    conn = get_connection()
    cur = conn.cursor()
    inserted, updated, skipped = 0, 0, 0

    for db_id in db_ids:
        for page in fetch_notion_db(db_id):
            notion_id = page["id"]
            props = page.get("properties", {})
            try:
                vendor = _title(props.get("Name", {}))
                category = _select(props.get("Expense Category"))
                date_val = _date(props.get("Transaction Date"))
                amount = _number(props.get("Amount Spent"))
                payment_method = _select(props.get("Payment Method"))
                rel = props.get("Модель", {}).get("relation", [])
                model_id = rel[0]["id"] if rel else None
                model = resolve_relation(model_id)

                if not model:
                    skipped += 1
                if not date_val or amount is None:
                    continue
                if "T" in str(date_val):
                    date_val = str(date_val)[:10]

                cur.execute("SELECT id FROM expenses WHERE notion_id = %s", (notion_id,))
                if cur.fetchone():
                    cur.execute(
                        """UPDATE expenses SET date=%s, model=%s, category=%s, vendor=%s, payment_method=%s, amount=%s
                           WHERE notion_id=%s""",
                        (date_val, model or "", category or "", vendor or "", payment_method or "", amount, notion_id),
                    )
                    updated += 1
                else:
                    cur.execute(
                        """INSERT INTO expenses (notion_id, date, model, category, vendor, payment_method, amount)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (notion_id, date_val, model or "", category or "", vendor or "", payment_method or "", amount),
                    )
                    inserted += 1
            except Exception as e:
                print("Expenses error:", e)
        conn.commit()

    cur.close()
    conn.close()
    print("Expenses: inserted", inserted, "updated", updated, "skipped", skipped)


# ==================== TRANSACTIONS ====================

model_cache = {}
chatter_cache = {}
shift_cache = {}


def get_page_title(page_id, cache):
    if page_id in cache:
        return cache[page_id]
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    data = resp.json()
    for p in data.get("properties", {}).values():
        if p.get("type") == "title" and p.get("title"):
            t = p["title"][0].get("plain_text", "").strip()
            cache[page_id] = t
            return t
    return None


def ensure_shift_exists(shift_id, cur, conn):
    cur.execute("SELECT id FROM shifts WHERE id = %s", (shift_id,))
    if cur.fetchone():
        return
    name = get_page_title(shift_id, shift_cache)
    if not name:
        return
    cur.execute("INSERT INTO shifts (id, name) VALUES (%s, %s)", (shift_id, name))
    conn.commit()


def parse_transaction_row(row, shift_type="relation"):
    props = row.get("properties", {})
    amount_prop = (
        props.get("Сумма выхода") or props.get("Сумма") or props.get("Amount")
        or props.get("Amount Spent") or {}
    )
    amount = float(amount_prop.get("number") or 0) if isinstance(amount_prop, dict) else 0
    date_prop = props.get("Date") or props.get("date") or props.get("Transaction Date") or {}
    date_obj = (date_prop or {}).get("date") if isinstance(date_prop, dict) else None
    date_val = date_obj["start"] if date_obj else None

    model_prop = props.get("Модель") or props.get("модель") or props.get("Model") or props.get("model")
    model_rel = (model_prop or {}).get("relation", []) if isinstance(model_prop, dict) else []
    model_name = get_page_title(model_rel[0]["id"], model_cache) if model_rel else None
    if not model_name and model_rel:
        model_name = "—"  # fallback если нет доступа к связанной странице

    chatter = None
    cp = props.get("Чаттер") or props.get("Chatter") or props.get("чаттер") or {}
    ct = (cp or {}).get("type")
    if ct == "rich_text" and (cp or {}).get("rich_text"):
        chatter = cp["rich_text"][0].get("plain_text")
    elif ct == "select" and (cp or {}).get("select"):
        chatter = cp["select"].get("name")
    elif ct == "people" and (cp or {}).get("people"):
        chatter = cp["people"][0].get("name")
    elif ct == "relation" and (cp or {}).get("relation"):
        chatter = get_page_title(cp["relation"][0]["id"], chatter_cache)

    def _extract_shift_from_prop(prop):
        if not isinstance(prop, dict):
            return None, None
        ptype = prop.get("type")
        if ptype == "relation" and prop.get("relation"):
            rid = prop["relation"][0].get("id")
            if rid:
                return rid, "relation"
        if ptype == "select" and prop.get("select"):
            name = (prop["select"].get("name") or "").strip()
            if name:
                return name, "select"
        if ptype == "multi_select" and prop.get("multi_select"):
            name = (prop["multi_select"][0].get("name") or "").strip()
            if name:
                return name, "multi_select"
        if ptype == "rich_text" and prop.get("rich_text"):
            txt = (prop["rich_text"][0].get("plain_text") or "").strip()
            if txt:
                return txt, "rich_text"
        if ptype == "title" and prop.get("title"):
            txt = (prop["title"][0].get("plain_text") or "").strip()
            if txt:
                return txt, "title"
        if ptype == "people" and prop.get("people"):
            name = (prop["people"][0].get("name") or "").strip()
            if name:
                return name, "people"
        return None, None

    # Храним совместимость: сначала используем ожидаемый тип, затем авто-fallback.
    shift_val, shift_kind = None, None
    preferred = "relation" if shift_type == "relation" else "select"
    fallback = "select" if preferred == "relation" else "relation"
    key_hints = ("смен", "shift", "admin", "админ")

    # 1) По прямым именам полей
    named_props = [props.get("Смена"), props.get("Shift"), props.get("Admin"), props.get("Админ")]
    for target_kind in (preferred, fallback):
        for p in named_props:
            val, kind = _extract_shift_from_prop(p)
            if val and kind and ((target_kind == "relation" and kind == "relation") or (target_kind != "relation" and kind != "relation")):
                shift_val, shift_kind = val, kind
                break
        if shift_val:
            break

    # 2) По похожим названиям любых свойств
    if not shift_val:
        for target_kind in (preferred, fallback):
            for key, prop in props.items():
                lname = str(key).strip().lower()
                if not any(h in lname for h in key_hints):
                    continue
                val, kind = _extract_shift_from_prop(prop)
                if val and kind and ((target_kind == "relation" and kind == "relation") or (target_kind != "relation" and kind != "relation")):
                    shift_val, shift_kind = val, kind
                    break
            if shift_val:
                break

    return date_val, model_name, chatter, amount, shift_val, shift_kind


def _sync_one_transaction_db(db_id, shift_type, cur, conn, use_upsert=True):
    """Синхронизирует одну базу транзакций. Возвращает (inserted, skipped)."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    has_more, next_cursor, inserted, skipped = True, None, 0, 0

    while has_more:
        payload = {"start_cursor": next_cursor} if next_cursor else {}
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        data = resp.json()

        if data.get("object") == "error" or data.get("code"):
            msg = data.get("message", "")
            if "page, not a database" in str(msg):
                resolved = _resolve_page_to_database_id(db_id)
                rid = (resolved or "").replace("-", "")
                bid = db_id.replace("-", "")
                if rid and rid != bid:
                    print(f"  ID {db_id[:8]}... — страница, найдена вложенная база {resolved[:8]}..., retry")
                    return _sync_one_transaction_db(resolved, shift_type, cur, conn, use_upsert)
            print(f"  Notion API error: {msg or data.get('code', 'unknown')}")
            break

        rows = data.get("results", [])
        if not next_cursor and not rows:
            print(f"  Notion вернул 0 строк. Проверь: 1) Интеграция добавлена в базу (Share→Invite) 2) ID базы верный")
        elif not next_cursor and rows:
            print(f"  Notion: получено {len(rows)} страниц (будут подгружаться дальше по курсору)")

        for row in rows:
            notion_id = row.get("id")
            date_val, model, chatter, amount, shift_val, shift_kind = parse_transaction_row(row, shift_type)
            if not model:
                skipped += 1
                continue
            if shift_val and shift_kind == "relation":
                ensure_shift_exists(shift_val, cur, conn)

            shift_id = shift_val
            shift_name = None
            if shift_val and shift_kind == "relation":
                shift_name = shift_cache.get(shift_val)
            elif shift_val:
                shift_name = shift_val

            if use_upsert and notion_id:
                cur.execute("""
                    INSERT INTO transactions (notion_id, date, model, chatter, amount, shift_id, shift_name, synced_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (notion_id)
                    DO UPDATE SET date=EXCLUDED.date, model=EXCLUDED.model, chatter=EXCLUDED.chatter,
                        amount=EXCLUDED.amount, shift_id=EXCLUDED.shift_id, shift_name=EXCLUDED.shift_name, synced_at=NOW()
                """, (notion_id, date_val, model, chatter or "", amount, shift_id, shift_name))
            else:
                cur.execute(
                    """INSERT INTO transactions (date, model, chatter, amount, shift_id, shift_name) VALUES (%s, %s, %s, %s, %s, %s)""",
                    (date_val, model, chatter or "", amount, shift_id, shift_name),
                )
            inserted += 1
            if inserted % 100 == 0:
                print(f"  Transactions: {inserted}...")
        conn.commit()
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return inserted, skipped


def sync_transactions(config, truncate=False):
    tcfg = config.get("transactions", {})
    default_shift = tcfg.get("shift_type", "relation")

    # Env переопределяет config — для разделения личный/клиент (разные секреты)
    # При NOTION_SYNC_CLIENT=1 НЕ используем config — только env (защита от пересечения)
    is_client = os.getenv("NOTION_SYNC_CLIENT", "").strip().lower() in ("1", "true", "yes")
    main_id = (
        os.getenv("NOTION_TRANSACTIONS_DATABASE_ID_CLIENT")
        or os.getenv("NOTION_TRANSACTIONS_DATABASE_ID")
        or os.getenv("DATABASE_ID")
    )
    if not main_id and not is_client:
        main_id = tcfg.get("database_id")

    sources = []
    if main_id:
        sources.append((main_id, default_shift))

    # month_overrides только для личного sync (config)
    use_config_overrides = not is_client and not os.getenv("NOTION_TRANSACTIONS_DATABASE_ID")
    for month_key, override in ((tcfg.get("month_overrides") or {}) if use_config_overrides else {}).items():
        oid = override.get("database_id")
        oshift = override.get("shift_type", default_shift)
        if oid and (oid, oshift) not in [(s[0], s[1]) for s in sources]:
            sources.append((oid, oshift))

    if not sources:
        print("Нет database_id для transactions")
        return

    conn = get_connection()
    cur = conn.cursor()

    if truncate:
        print("TRUNCATE transactions (очистка дубликатов)...")
        cur.execute("TRUNCATE TABLE transactions")
        conn.commit()

    total_inserted, total_skipped = 0, 0

    for db_id, shift_type in sources:
        print(f"Transactions: база {db_id[:8]}... shift_type={shift_type}")
        inc, sk = _sync_one_transaction_db(db_id, shift_type, cur, conn)
        total_inserted += inc
        total_skipped += sk

    cur.close()
    conn.close()
    print("Transactions: всего inserted", total_inserted, "skipped", total_skipped)


def main():
    if not NOTION_TOKEN:
        print("Задай NOTION_TOKEN в .env")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--expenses", action="store_true")
    parser.add_argument("--transactions", action="store_true")
    parser.add_argument("--month", help="Напр. 2024-12 для month_overrides")
    parser.add_argument("--truncate-transactions", action="store_true",
                        help="Очистить таблицу transactions перед sync (убирает дубликаты)")
    args = parser.parse_args()

    do_exp = args.expenses or (not args.expenses and not args.transactions)
    do_trx = args.transactions or (not args.expenses and not args.transactions)

    config = load_config()
    if args.month and do_trx:
        overrides = config.get("transactions", {}).get("month_overrides", {}).get(args.month, {})
        if overrides:
            config.setdefault("transactions", {})
            config["transactions"] = {**config["transactions"], **overrides}

    if do_exp:
        sync_expenses(config)
    if do_trx:
        sync_transactions(config, truncate=args.truncate_transactions)


if __name__ == "__main__":
    main()
