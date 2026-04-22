from utils import save_json, load_json
from config import CATEGORIES

USER_DATA_FILE = "user_data.json"

class UserPreferences:
    def __init__(self, user_id):
        self.user_id = user_id
        self.data = load_json(USER_DATA_FILE, {}).get(str(user_id), {})
        # Default preferences
        self.data.setdefault("categories", CATEGORIES.copy())
        self.data.setdefault("location", "any")
        self.data.setdefault("date_range", "upcoming")

    def save(self):
        all_data = load_json(USER_DATA_FILE, {})
        all_data[str(self.user_id)] = self.data
        save_json(all_data, USER_DATA_FILE)

    @property
    def categories(self):
        return self.data["categories"]

    @categories.setter
    def categories(self, value):
        self.data["categories"] = value
        self.save()

    @property
    def location(self):
        return self.data["location"]

    @location.setter
    def location(self, value):
        self.data["location"] = value
        self.save()

    @property
    def date_range(self):
        return self.data["date_range"]

    @date_range.setter
    def date_range(self, value):
        self.data["date_range"] = value
        self.save()