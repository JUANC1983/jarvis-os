import json
import os

FILE = "meetings.json"


def load_meetings():
    if not os.path.exists(FILE):
        return []
    with open(FILE, "r") as f:
        return json.load(f)


def save_meetings(data):
    with open(FILE, "w") as f:
        json.dump(data, f)


def add_meeting(title, time, notes):
    meetings = load_meetings()

    meetings.append({
        "title": title,
        "time": time,
        "notes": notes
    })

    save_meetings(meetings)
    return meetings


def get_meetings():
    return load_meetings()