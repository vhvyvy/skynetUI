"""
Диагностика: что Notion возвращает для базы.
  python scripts/debug_notion_db.py 317fad2b5c5780888ae3d2f6dc078d4c

Покажет: API ответ, кол-во строк, имена свойств, первые значения.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", ".env"))

NOTION_TOKEN = os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY")
db_id = sys.argv[1] if len(sys.argv) > 1 else "317fad2b5c5780888ae3d2f6dc078d4c"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def main():
    import requests
    if not NOTION_TOKEN:
        print("NOTION_TOKEN не задан")
        sys.exit(1)
    print(f"Проверяю базу {db_id[:8]}...")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    resp = requests.post(url, headers=HEADERS, json={}, timeout=15)
    data = resp.json()
    if data.get("object") == "error":
        print("API ошибка:", data.get("message", data))
        if "page, not a database" in str(data.get("message", "")):
            print("\nЭто страница, не база. Пробуем blocks/children...")
            bid = db_id.replace("-", "")
            blk_url = f"https://api.notion.com/v1/blocks/{bid}/children"
            r2 = requests.get(blk_url, headers=HEADERS, params={"page_size": 50}, timeout=15)
            blks = r2.json()
            if blks.get("object") == "error":
                print("Blocks ошибка:", blks.get("message"))
            else:
                for b in blks.get("results", []):
                    if b.get("type") == "child_database":
                        print("  Найден child_database, id:", b.get("id"))
        sys.exit(1)
    rows = data.get("results", [])
    print(f"Строк: {len(rows)}")
    if rows:
        props = rows[0].get("properties", {})
        print("Свойства (имена):", list(props.keys()))
        for k in ["Date", "date", "Transaction Date", "Модель", "модель", "Model", "Сумма выхода", "Сумма", "Amount", "Amount Spent", "Чаттер", "Chatter"]:
            if k in props:
                p = props[k]
                t = p.get("type")
                val = p.get("date") or p.get("number") or p.get("relation") or p.get("select") or p.get("rich_text")
                print(f"  {k}: type={t}, val={str(val)[:80]}...")
    else:
        print("База пустая или нет доступа")

if __name__ == "__main__":
    main()
