import json
from datetime import datetime
from ics import Calendar, Event

calendar = Calendar()

with open("data/events.json", "r") as f:
    events = json.load(f)

for item in events:
    event = Event()

    event.name = item["name"]

    start_time = datetime.strptime(
        f"{item['date']} {item['time']}",
        "%Y-%m-%d %H:%M"
    )

    event.begin = start_time

    event.description = (
        f"Venue: {item['venue']}\n"
        f"City: {item['city']}\n"
        f"Network: {item['network']}"
    )

    calendar.events.add(event)

with open("calendar.ics", "w") as f:
    f.writelines(calendar.serialize_iter())
