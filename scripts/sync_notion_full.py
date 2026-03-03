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

NOTION_TOKEN = os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY")
PG_HOST = os.getenv("PG_HOST") or os.getenv("DB_HOST") or "localhost"
PG_PORT = int(os.getenv("PG_PORT") or os.getenv("DB_PORT") or "5432")
PG_DB = os.getenv("PG_DB") or os.getenv("DB_NAME") or "skynet"
PG_USER = os.getenv("PG_USER") or os.getenv("DB_USER") or "postgres"
PG_PASSWORD = os.getenv("PG_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("DB_PASS") or ""

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
    if PG_HOST and ".neon.tech" in PG_HOST:
        kwargs["sslmode"] = "require"
    return psycopg2.connect(**kwargs)


def fetch_notion_db(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    results = []
    start_cursor = None
    while True:
        payload = {"start_cursor": start_cursor} if start_cursor else {}
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
    return results


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
    db_ids = config.get("expenses", {}).get("database_ids", [])
    if not db_ids:
        ids_env = os.getenv("NOTION_EXPENSES_DATABASE_IDS") or os.getenv("NOTION_EXPENSES_DATABASE_ID")
        if ids_env:
            db_ids = [x.strip() for x in str(ids_env).split(",") if x.strip()]
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
    amount = props.get("Сумма выхода", {}).get("number") or 0
    date_obj = props.get("Date", {}).get("date")
    date_val = date_obj["start"] if date_obj else None

    model_rel = props.get("модель", {}).get("relation", [])
    model_name = get_page_title(model_rel[0]["id"], model_cache) if model_rel else None

    chatter = None
    cp = props.get("Чаттер", {})
    ct = cp.get("type")
    if ct == "rich_text" and cp.get("rich_text"):
        chatter = cp["rich_text"][0].get("plain_text")
    elif ct == "select" and cp.get("select"):
        chatter = cp["select"].get("name")
    elif ct == "people" and cp.get("people"):
        chatter = cp["people"][0].get("name")
    elif ct == "relation" and cp.get("relation"):
        chatter = get_page_title(cp["relation"][0]["id"], chatter_cache)

    shift_val = None
    if shift_type == "relation":
        for k, v in props.items():
            if v.get("type") == "relation" and k.strip().lower() in ("смена", "shift"):
                if v.get("relation"):
                    shift_val = v["relation"][0]["id"]
                break
    else:
        sp = props.get("Смена") or props.get("Shift")
        if sp and sp.get("type") == "select" and sp.get("select"):
            shift_val = sp["select"].get("name")

    return date_val, model_name, chatter, amount, shift_val


def _sync_one_transaction_db(db_id, shift_type, cur, conn):
    """Синхронизирует одну базу транзакций. Возвращает (inserted, skipped)."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    has_more, next_cursor, inserted, skipped = True, None, 0, 0

    while has_more:
        payload = {"start_cursor": next_cursor} if next_cursor else {}
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        data = resp.json()

        for row in data.get("results", []):
            date_val, model, chatter, amount, shift_val = parse_transaction_row(row, shift_type)
            if not model:
                skipped += 1
                continue
            if shift_val and shift_type == "relation":
                ensure_shift_exists(shift_val, cur, conn)
            cur.execute(
                """INSERT INTO transactions (date, model, chatter, amount, shift_id) VALUES (%s, %s, %s, %s, %s)""",
                (date_val, model, chatter or "", amount, shift_val),
            )
            inserted += 1
            if inserted % 100 == 0:
                print(f"  Transactions: {inserted}...")
        conn.commit()
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return inserted, skipped


def sync_transactions(config):
    tcfg = config.get("transactions", {})
    default_shift = tcfg.get("shift_type", "relation")

    # Собираем все базы: основная + из month_overrides
    sources = []
    main_id = tcfg.get("database_id") or os.getenv("DATABASE_ID")
    if main_id:
        sources.append((main_id, default_shift))

    for month_key, override in (tcfg.get("month_overrides") or {}).items():
        oid = override.get("database_id")
        oshift = override.get("shift_type", default_shift)
        if oid and (oid, oshift) not in [(s[0], s[1]) for s in sources]:
            sources.append((oid, oshift))

    if not sources:
        print("Нет database_id для transactions")
        return

    conn = get_connection()
    cur = conn.cursor()
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
        sync_transactions(config)


if __name__ == "__main__":
    main()
