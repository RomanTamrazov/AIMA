from typing import List, Dict, Any
from preferences import UserPreferences

def filter_events(events: List[Dict], prefs: UserPreferences) -> List[Dict]:
    """Filter events based on user preferences."""
    filtered = []
    for ev in events:
        # Category filter (simple keyword matching in description/name)
        ev_text = (ev.get("name", "") + " " + ev.get("description", "")).lower()
        matches_cat = any(cat in ev_text for cat in prefs.categories)
        if not matches_cat:
            continue

        # Location filter
        loc = ev.get("location", "").lower()
        if prefs.location != "any" and prefs.location not in loc and "online" not in loc:
            continue

        # Date filter (basic: only "upcoming" – you can implement more)
        if prefs.date_range == "upcoming":
            # Simple: assume future if date is not empty and not in the past
            # For real use, compare with current date
            pass
        filtered.append(ev)
    return filtered

def format_event(event: Dict[str, Any]) -> str:
    """Return a formatted string for a single event."""
    name = event.get("name", "Без названия")
    date = event.get("date", "Дата не указана")
    location = event.get("location", "Место не указано")
    desc = event.get("description", "")
    url = event.get("url", "")
    msg = f"*{name}*\n📅 {date}\n📍 {location}\n📝 {desc}"
    if url:
        msg += f"\n🔗 [Подробнее]({url})"
    return msg