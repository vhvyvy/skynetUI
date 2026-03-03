"""
События агентства — для контекста AI.
Примеры: новая модель, ушёл чаттер, сменились админы.
"""
import json
import os

EVENTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "events.json")


def _ensure_data_dir():
    d = os.path.dirname(EVENTS_FILE)
    if not os.path.exists(d):
        os.makedirs(d)


def _load_all():
    if not os.path.exists(EVENTS_FILE):
        return []
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _save_all(events: list):
    _ensure_data_dir()
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def get_all_events() -> list:
    """Возвращает список событий [{date, description}, ...], отсортированный по дате (новые первые)."""
    events = _load_all()
    events = [e for e in events if isinstance(e, dict) and e.get("date") and e.get("description")]
    events.sort(key=lambda e: e["date"], reverse=True)
    return events


def add_event(date: str, description: str) -> None:
    """Добавляет событие. date в формате YYYY-MM-DD."""
    events = _load_all()
    events.append({"date": date.strip(), "description": description.strip()})
    events.sort(key=lambda e: e["date"], reverse=True)
    _save_all(events)


def delete_event(date: str, description: str) -> None:
    """Удаляет первое совпавшее событие по date и description."""
    events = _load_all()
    events = [e for e in events if not (e.get("date") == date and e.get("description") == description)]
    _save_all(events)


def get_events_for_context(selected_year: int = None, selected_month: int = None) -> list:
    """Возвращает все события для контекста AI (отсортированные по дате)."""
    return get_all_events()
