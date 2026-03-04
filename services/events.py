"""
События агентства — для контекста AI.
Примеры: новая модель, ушёл чаттер, сменились админы.
"""
from services.db import get_connection


def get_all_events() -> list:
    """Возвращает список событий [{date, description}, ...], отсортированный по дате (новые первые)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT date, description FROM events ORDER BY date DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"date": str(r[0]), "description": r[1] or ""} for r in rows]
    except Exception:
        return []


def add_event(date: str, description: str) -> None:
    """Добавляет событие. date в формате YYYY-MM-DD."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (date, description) VALUES (%s, %s)",
        (date.strip(), description.strip()),
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_event(date: str, description: str) -> None:
    """Удаляет первое совпавшее событие по date и description."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM events WHERE id = (SELECT id FROM events WHERE date = %s AND description = %s LIMIT 1)",
        (date, description),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_events_for_context(selected_year: int = None, selected_month: int = None) -> list:
    """Возвращает все события для контекста AI (отсортированные по дате)."""
    return get_all_events()
