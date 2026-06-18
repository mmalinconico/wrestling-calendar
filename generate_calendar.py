import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ics import Calendar, Event

calendar = Calendar()

with open("data/events.json", "r") as f:
    events = json.load(f)

eastern = ZoneInfo("America/New_York")

for item in events:
    event = Event()

    event.name = item["name"]

    start_time = datetime.strptime(
        f"{item['date']} {item['time']}",
        "%Y-%m-%d %H:%M"
    ).replace(tzinfo=eastern)

    duration_hours = item.get("duration_hours", 4)

    event.begin = start_time
    event.end = start_time + timedelta(hours=duration_hours)

    description_parts = []

    if item.get("venue"):
        description_parts.append(f"Venue: {item['venue']}")

    if item.get("city"):
        description_parts.append(f"City: {item['city']}")

    if item.get("network"):
        description_parts.append(f"Network: {item['network']}")

    if item.get("promotion"):
        description_parts.append(f"Promotion: {item['promotion']}")

    event.description = "\n".join(description_parts)

    calendar.events.add(event)
print(f"Generated {len(calendar.events)} events")
with open("calendar.ics", "w") as f:
    f.writelines(calendar.serialize_iter())
