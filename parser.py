import aiohttp
import asyncio
import re
from bs4 import BeautifulSoup
import json
from typing import List, Dict, Any
from config import SOURCES
from utils import parse_date, save_json, load_json, filter_recent_events, clean_html

EVENTS_CACHE_FILE = "events_cache.json"

async def parse_ict2go(session: aiohttp.ClientSession, url: str) -> List[Dict[str, Any]]:
    """Парсит страницу https://ict2go.ru/events/, извлекая все события."""
    try:
        async with session.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()
    except Exception as e:
        print(f"Ошибка загрузки {url}: {e}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    events = []

    # Ищем все блоки с событиями – по структуре страницы: обычно div с классом, содержащим 'event' или 'item'
    # Анализируя содержимое, можно искать строки с датой в формате DD.MM.YYYY | Город
    # Но проще найти все блоки, которые содержат ссылку с классом event-title или подобным
    for block in soup.find_all('div', class_=re.compile(r'event|item|post')):
        # Ищем ссылку с названием
        link = block.find('a', class_=re.compile(r'event-title|title'))
        if not link:
            continue
        name = link.get_text(strip=True)
        if not name:
            continue

        # Дата и место
        # Ищем элемент с датой: может быть span с классом date или просто текст, содержащий DD.MM.YYYY | Город
        date_place = block.find(class_=re.compile(r'date|place|meta'))
        if not date_place:
            # Попробуем найти текст с паттерном даты
            text = block.get_text()
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})\s*\|\s*([^\n]+)', text)
            if match:
                date_raw, location = match.groups()
                date = parse_date(date_raw)
            else:
                continue
        else:
            date_text = date_place.get_text(strip=True)
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})\s*\|\s*([^\n]+)', date_text)
            if match:
                date_raw, location = match.groups()
                date = parse_date(date_raw)
            else:
                continue

        # Описание – часто в соседнем блоке
        desc_block = block.find(class_=re.compile(r'desc|description|text'))
        description = desc_block.get_text(strip=True) if desc_block else ''
        if not description:
            # Возьмём текст после даты
            pass
        description = clean_html(description)[:200]

        # Ссылка (если есть)
        url_link = link.get('href', '')
        if url_link and not url_link.startswith('http'):
            url_link = 'https://ict2go.ru' + url_link

        # Тип мероприятия (из тегов или из текста)
        # По умолчанию определим по ключевым словам
        ev_type = 'conference'
        if 'хакатон' in name.lower():
            ev_type = 'hackathon'
        elif 'олимпиад' in name.lower():
            ev_type = 'olympiad'
        elif 'конкурс' in name.lower():
            ev_type = 'contest'

        events.append({
            'name': name,
            'date': date,
            'location': location.strip(),
            'description': description,
            'url': url_link,
            'source_url': url,
            'type': ev_type
        })

    # Дополнительно: если не нашли по классам, ищем по прямому паттерну в тексте
    if not events:
        # Простой regex по всему тексту: ищем строки вида "DD.MM.YYYY | Город\nНазвание"
        text = soup.get_text()
        # Паттерн: дата, затем пробелы, вертикальная черта, город, затем перевод строки и название
        pattern = r'(\d{2}\.\d{2}\.\d{4})\s*\|\s*([^\n]+)\s*\n\s*([^\n]+)'
        matches = re.findall(pattern, text)
        for date_raw, location, name in matches:
            name = name.strip()
            if not name:
                continue
            date = parse_date(date_raw)
            events.append({
                'name': name,
                'date': date,
                'location': location.strip(),
                'description': '',
                'url': '',
                'source_url': url,
                'type': 'conference'
            })

    return events

async def parse_all_sources(force_refresh=False) -> List[Dict[str, Any]]:
    """Основной парсер: сначала пытается собрать с сайтов, если нет – fallback."""
    if not force_refresh:
        cached = load_json(EVENTS_CACHE_FILE, [])
        if cached:
            filtered = filter_recent_events(cached, max_months=6)
            print(f"Загружено из кэша {len(cached)} событий, после фильтрации — {len(filtered)}")
            return filtered

    print("Начинаю парсинг...")
    all_events = []
    async with aiohttp.ClientSession() as session:
        for url in SOURCES:
            print(f"\nОбработка {url}")
            if 'ict2go.ru' in url:
                events = await parse_ict2go(session, url)
                print(f"  → Найдено {len(events)} событий на ict2go")
                all_events.extend(events)
            else:
                # Здесь можно добавить другие источники
                pass
            await asyncio.sleep(1)

    # Если не нашли ни одного события, используем fallback
    if not all_events:
        print("\n⚠️ Не удалось найти события на сайтах. Использую запасной список.")
    else:
        # Удаляем дубликаты по имени и дате
        unique = {}
        for ev in all_events:
            name = ev.get("name", "").lower().strip()
            date = ev.get("date", "")
            if name and len(name) > 2:
                key = (name, date)
                if key not in unique:
                    unique[key] = ev
        all_events = list(unique.values())

    # Фильтрация по дате
    recent = filter_recent_events(all_events, max_months=6)
    print(f"После фильтрации дат: {len(recent)} событий")

    if recent:
        save_json(recent, EVENTS_CACHE_FILE)

    return recent