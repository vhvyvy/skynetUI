"""
KPI чаттеров: PPV Open Rate, APV, Total Chats.
Источники: Onlymonster API, Notion, ручной ввод.
Структура: {year: {month: {chatter: {ppv_open_rate, apv, total_chats, model?, source}}}}
"""
import json
import os

KPI_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chatter_kpi.json")
MAPPING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chatter_id_to_name.json")


def get_chatter_id_to_name_mapping():
    """
    Маппинг user_id (Onlymonster) → имя или [имена].
    Файл data/chatter_id_to_name.json.
    Формат: "159159": "@nick" или "159159": ["@nick", "OnlyMonster name"]
    """
    if not os.path.exists(MAPPING_FILE):
        return {}
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def get_name_to_chatter_id_reverse_mapping():
    """Обратный маппинг: любой алиас → user_id. Для merge с транзакциями."""
    mapping = get_chatter_id_to_name_mapping()
    reverse = {}
    for uid, names in mapping.items():
        for name in (names if isinstance(names, list) else [names]):
            n = str(name).strip()
            if n:
                reverse[n] = str(uid)
    return reverse


def _ensure_data_dir():
    d = os.path.dirname(KPI_FILE)
    if not os.path.exists(d):
        os.makedirs(d)


def _load_all():
    if not os.path.exists(KPI_FILE):
        return {}
    try:
        with open(KPI_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_all(data):
    _ensure_data_dir()
    with open(KPI_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_kpi(year, month, apply_id_mapping=True):
    """
    Возвращает dict {chatter: {ppv_open_rate, apv, total_chats, model?, source}}.
    Если apply_id_mapping=True, маппит user_id → имя по data/chatter_id_to_name.json.
    При формате "id": ["name1", "name2"] используется первый как display.
    """
    data = _load_all()
    y, m = str(year), str(month)
    if y not in data or m not in data[y]:
        return {}
    kpi = data[y][m]
    if not apply_id_mapping:
        return kpi
    mapping = get_chatter_id_to_name_mapping()
    if not mapping:
        return kpi
    result = {}
    for uid, val in kpi.items():
        names = mapping.get(str(uid), uid)
        display = names[0] if isinstance(names, list) and names else (names if names else uid)
        result[str(display).strip()] = val
    return result


def get_unmapped_user_ids(year, month):
    """user_id из KPI, для которых нет записи в маппинге."""
    kpi_by_id, _ = get_kpi_for_merge(year, month)
    mapping = get_chatter_id_to_name_mapping()
    return [uid for uid in kpi_by_id if str(uid) not in mapping]


def get_kpi_for_merge(year, month):
    """
    Возвращает (kpi_by_id, name_to_id).
    kpi_by_id: {user_id: {ppv_open_rate, apv, ...}}
    name_to_id: {имя_или_алиас: user_id} для сопоставления с chatter из транзакций.
    """
    data = _load_all()
    y, m = str(year), str(month)
    if y not in data or m not in data[y]:
        return {}, {}
    kpi = data[y][m]
    mapping = get_chatter_id_to_name_mapping()
    name_to_id = {}
    for uid, names in mapping.items():
        for n in (names if isinstance(names, list) else [names]):
            if n:
                name_to_id[str(n).strip()] = str(uid)
    return kpi, name_to_id


def save_kpi(year, month, chatter, ppv_open_rate=None, apv=None, total_chats=None, model=None, source="manual"):
    """Сохраняет KPI для чаттера."""
    data = _load_all()
    y, m = str(year), str(month)
    if y not in data:
        data[y] = {}
    if m not in data[y]:
        data[y][m] = {}
    entry = data[y][m].get(chatter, {})
    if ppv_open_rate is not None:
        entry["ppv_open_rate"] = float(ppv_open_rate)
    if apv is not None:
        entry["apv"] = float(apv)
    if total_chats is not None:
        entry["total_chats"] = int(total_chats)
    if model is not None:
        entry["model"] = str(model)
    entry["source"] = source
    data[y][m][chatter] = entry
    _save_all(data)


def save_kpi_batch(year, month, records):
    """
    records: list of {chatter, ppv_open_rate, apv, total_chats, model?, source?}
    """
    data = _load_all()
    y, m = str(year), str(month)
    if y not in data:
        data[y] = {}
    if m not in data[y]:
        data[y][m] = {}
    for r in records:
        chatter = r.get("chatter") or r.get("member") or r.get("member_name")
        if not chatter:
            continue
        entry = {
            "ppv_open_rate": r.get("ppv_open_rate"),
            "apv": r.get("apv"),
            "total_chats": r.get("total_chats"),
            "model": r.get("model") or r.get("creator"),
            "source": r.get("source", "api"),
        }
        entry = {k: v for k, v in entry.items() if v is not None}
        if entry:
            data[y][m][str(chatter).strip()] = {**data[y][m].get(str(chatter).strip(), {}), **entry}
    _save_all(data)
