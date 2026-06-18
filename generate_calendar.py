import json
from datetime import datetime, timedelta
from ics import Calendar, Event

calendar = Calendar()

with open("data/events.json", "r") as f:
    events = json.load(f)

for item in events:
    event = Event()

    event.name = item["name"]

    start_date = datetime.strptime(
        item["date"],
        "%Y-%m-%d"
    )

    event.begin = start_date
    event.end = start_date + timedelta(days=1)

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
