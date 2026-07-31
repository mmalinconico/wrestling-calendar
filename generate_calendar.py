import json
import re
from datetime import datetime, timedelta

from ics import Calendar, Event

calendar = Calendar()

with open("data/events.json", "r", encoding="utf-8") as f:
    events = json.load(f)

for item in events:
    event = Event()
    event.name = item["name"]

    if item.get("all_day"):
        event.begin = item["date"]
        event.make_all_day()
    else:
        start = datetime.fromisoformat(
            item["date"].replace("Z", "+00:00")
        )

        event.begin = start
        event.end = start + timedelta(hours=4)

    if item.get("uid"):
        event.uid = item["uid"]
    else:
        uid_name = re.sub(
            r"[^a-z0-9]+",
            "-",
            item["name"].lower(),
        ).strip("-")

        event.uid = (
            f"{uid_name}-"
            f"{item['id']}"
        )

    location_parts = []

    if item.get("venue"):
        location_parts.append(item["venue"])

    if item.get("city"):
        location_parts.append(item["city"])

    event.location = ", ".join(location_parts)

    description = []

    if item.get("network"):
        description.append(
            f"Network: {item['network']}"
        )

    if item.get("status"):
        description.append(item["status"])

    event.description = "\n".join(description)

    calendar.events.add(event)

with open("nfl-playoffs.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"Generated calendar with {len(events)} events")
