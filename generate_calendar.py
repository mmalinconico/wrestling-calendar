import json
from datetime import datetime
from ics import Calendar, Event

calendar = Calendar()

with open("data/events.json", "r") as f:
    events = json.load(f)

for item in events:
    event = Event()

    promotion = item.get("promotion", "")

    if promotion and item["name"].startswith(f"{promotion} "):
        event.name = item["name"]
    elif promotion:
        event.name = f"{promotion} {item['name']}"
    else:
        event.name = item["name"]

    start_date = datetime.strptime(
        item["date"],
        "%Y-%m-%d"
    ).date()

    event.begin = start_date
    event.make_all_day()

    venue = item.get("venue", "")
    city = item.get("city", "")

    if venue and city:
        event.location = f"{venue}, {city}"
    elif venue:
        event.location = venue
    elif city:
        event.location = city

    if item.get("network"):
        event.description = f"Network: {item['network']}"

    calendar.events.add(event)

print(f"Generated {len(calendar.events)} events")

with open("calendar.ics", "w") as f:
    f.writelines(calendar.serialize_iter())
