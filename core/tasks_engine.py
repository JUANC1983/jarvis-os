import json
import os

FILE = "tasks.json"


def load_tasks():
    if not os.path.exists(FILE):
        return []
    with open(FILE, "r") as f:
        return json.load(f)


def save_tasks(tasks):
    with open(FILE, "w") as f:
        json.dump(tasks, f)


def add_task(title, priority, date):
    tasks = load_tasks()

    tasks.append({
        "title": title,
        "priority": priority,
        "date": date,
        "done": False
    })

    save_tasks(tasks)
    return tasks


def toggle_task(index):
    tasks = load_tasks()
    tasks[index]["done"] = not tasks[index]["done"]
    save_tasks(tasks)
    return tasks


def get_tasks():
    return load_tasks()