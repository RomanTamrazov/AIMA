import json
import re
from datetime import datetime, timedelta
import html

def clean_html(text: str) -> str:
    """Удаляет HTML-теги и декодирует сущности."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы для Telegram Markdown V2."""
    if not text:
        return ''
    # Символы, которые нужно экранировать: _ * [ ] ( ) ~ ` > # + = | { } . !
    escape_chars = r'_*[]()~`>#+=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

def parse_date(date_str: str) -> str:
    """Приводит дату к формату YYYY-MM-DD, если возможно."""
    if not date_str:
        return ""
    # Уже YYYY-MM-DD
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str
    # DD.MM.YYYY
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if match:
        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # DD MMM YYYY (например, "15 марта 2025")
    match = re.search(r'(\d{1,2})\s+([а-я]+)\s+(\d{4})', date_str, re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }
        month_num = months.get(month_name.lower())
        if month_num:
            return f"{year}-{month_num:02d}-{int(day):02d}"
    return date_str

def is_date_valid(date_str: str) -> bool:
    """Проверяет, можно ли распарсить дату и не слишком ли она старая."""
    if not date_str:
        return False
    try:
        if '-' in date_str:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        elif '.' in date_str:
            dt = datetime.strptime(date_str[:10], "%d.%m.%Y")
        else:
            return False
        # Не старше 6 месяцев и не древнее 2023 года
        six_months_ago = datetime.now() - timedelta(days=180)
        if dt < six_months_ago or dt.year < 2023:
            return False
        return True
    except:
        return False

def filter_recent_events(events, max_months=6):
    """Оставляет события не старше max_months месяцев и будущие."""
    cutoff = datetime.now() - timedelta(days=30*max_months)
    filtered = []
    for ev in events:
        date_str = ev.get("date", "")
        if not is_date_valid(date_str):
            continue
        try:
            if '-' in date_str:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            elif '.' in date_str:
                dt = datetime.strptime(date_str[:10], "%d.%m.%Y")
            else:
                continue
            if dt >= cutoff:
                filtered.append(ev)
        except:
            continue
    return filtered

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(filename, default=None):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default or {}