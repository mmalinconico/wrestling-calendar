import json
import re
import unicodedata
from datetime import datetime

from ics import Calendar, Event


def normalize_uid_component(value):
    normalized = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    ascii_text = normalized.encode(
        "ascii",
        "ignore",
    ).decode("ascii")

    component = re.sub(
        r"[^a-z0-9]+",
        "-",
        ascii_text.lower(),
    ).strip("-")

    return component or "unknown"


def build_event_uid(item):
    promotion = normalize_uid_component(
        item.get("promotion", "wrestling")
    )

    name = normalize_uid_component(
        item.get("name", "event")
    )

    event_date = normalize_uid_component(
        item.get("date", "unknown-date")
    )

    # Avoid repeating the promotion when it is already part
    # of the event name, such as "NXT Heatwave."
    if (
        name == promotion
        or name.startswith(f"{promotion}-")
    ):
        event_identity = name
    else:
        event_identity = f"{promotion}-{name}"

    return (
        f"wrestling-{event_identity}-{event_date}"
        "@mmalinconico.github.io"
    )


calendar = Calendar()

with open(
    "data/events.json",
    "r",
    encoding="utf-8",
) as f:
    events = json.load(f)

for item in events:
    event = Event()

    promotion = item.get("promotion", "")
    event_name = item["name"]

    if (
        promotion
        and event_name.lower().startswith(
            f"{promotion.lower()} "
        )
    ):
        event.name = event_name
    elif promotion:
        event.name = f"{promotion} {event_name}"
    else:
        event.name = event_name

    start_date = datetime.strptime(
        item["date"],
        "%Y-%m-%d",
    ).date()

    event.begin = start_date
    event.make_all_day()

    # Use an explicitly supplied UID when available.
    # Otherwise derive a repeatable UID from the event information.
    event.uid = (
        item.get("uid")
        or build_event_uid(item)
    )

    venue = item.get("venue", "")
    city = item.get("city", "")

    if venue and city:
        event.location = f"{venue}, {city}"
    elif venue:
        event.location = venue
    elif city:
        event.location = city

    if item.get("network"):
        event.description = (
            f"Network: {item['network']}"
        )

    calendar.events.add(event)

print(f"Generated {len(calendar.events)} events")

with open(
    "calendar.ics",
    "w",
    encoding="utf-8",
) as f:
    f.writelines(calendar.serialize_iter())
