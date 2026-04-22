import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Источники, которые будем пробовать
SOURCES = [
    "https://ict2go.ru/events/",          # Календарь IT-мероприятий (будем парсить напрямую)
    # Дополнительно можно добавить другие, но для начала хватит
]

CATEGORIES = ["hackathon", "contest", "conference", "olympiad", "ai", "ml"]