from datetime import datetime
from ics import Calendar, Event

calendar = Calendar()

event = Event()
event.name = "Calendar Test Event"
event.begin = "2026-01-01 19:00:00"
event.description = "If you can see this event, the calendar generator is working."

calendar.events.add(event)

with open("calendar.ics", "w") as f:
    f.writelines(calendar.serialize_iter())
