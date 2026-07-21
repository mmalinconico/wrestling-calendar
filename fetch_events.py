import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

EVENTS_FILE = Path("data/events.json")
PAST_EVENT_RETENTION_DAYS = 7


def clean_text(text):
    text = re.sub(r"\[\s*\d+\s*\]", "", text)
    return " ".join(text.split()).strip()


def parse_date(date_text):
    current_year = datetime.now().year

    parsed = datetime.strptime(
        f"{date_text} {current_year}",
        "%B %d %Y"
    )

    if parsed.date() < datetime.now().date():
        parsed = parsed.replace(year=current_year + 1)

    return parsed.strftime("%Y-%m-%d")


def event_key(event):
    return (
        event.get("promotion", ""),
        event.get("name", ""),
        event.get("date", "")
    )


def load_previous_events():
    if not EVENTS_FILE.exists():
        return []

    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load previous events: {error}")

    return []


previous_events = load_previous_events()
events = []

# -------------------
# WWE / NXT
# -------------------

wwe_url = (
    "https://en.wikipedia.org/wiki/"
    "List_of_WWE_pay-per-view_and_livestreaming_supercards"
)

response = requests.get(
    wwe_url,
    headers=HEADERS,
    timeout=30
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

schedule_table = None

for heading in soup.find_all(["h2", "h3"]):
    if "Upcoming event schedule" in heading.get_text(" ", strip=True):
        tables = heading.find_all_next("table", limit=5)

        for table in tables:
            text = table.get_text(" ", strip=True)

            if "Date" in text and "Event" in text and "Venue" in text:
                schedule_table = table
                break

        break

if schedule_table:
    rows = schedule_table.find_all("tr")

    i = 1

    while i < len(rows):
        cells = rows[i].find_all(["td", "th"])

        if len(cells) < 4:
            i += 1
            continue

        date_text = clean_text(
            cells[0].get_text(" ", strip=True)
        )

        event_name = clean_text(
            cells[1].get_text(" ", strip=True)
        )

        venue = clean_text(
            cells[2].get_text(" ", strip=True)
        )

        city = clean_text(
            cells[3].get_text(" ", strip=True)
        )

        notes = (
            clean_text(cells[4].get_text(" ", strip=True))
            if len(cells) > 4
            else ""
        )

        if date_text == "TBA":
            i += 1
            continue

        promotion = (
            "NXT"
            if event_name.startswith("NXT")
            or "Great American Bash" in event_name
            else "WWE"
        )

        if promotion == "NXT":
            network = "The CW"
        elif "Main Event" in event_name:
            network = "Peacock"
        else:
            network = "ESPN"

        # Manual overrides
        if event_name == "Worlds Collide":
            promotion = "WWE/AAA"
            network = "YouTube"

        if "two-part event" in notes.lower():
            events.append({
                "name": f"{event_name} Night 1",
                "date": parse_date(date_text),
                "venue": venue,
                "city": city,
                "network": network,
                "promotion": promotion
            })

            if i + 1 < len(rows):
                next_cells = rows[i + 1].find_all(
                    ["td", "th"]
                )

                if len(next_cells) == 1:
                    night2_date = clean_text(
                        next_cells[0].get_text(
                            " ",
                            strip=True
                        )
                    )

                    events.append({
                        "name": f"{event_name} Night 2",
                        "date": parse_date(night2_date),
                        "venue": venue,
                        "city": city,
                        "network": network,
                        "promotion": promotion
                    })

                    i += 1

        else:
            events.append({
                "name": event_name,
                "date": parse_date(date_text),
                "venue": venue,
                "city": city,
                "network": network,
                "promotion": promotion
            })

        i += 1

# -------------------
# AEW
# -------------------

aew_url = (
    "https://en.wikipedia.org/wiki/"
    "List_of_All_Elite_Wrestling_pay-per-view_events"
)

response = requests.get(
    aew_url,
    headers=HEADERS,
    timeout=30
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for heading in soup.find_all(["h2", "h3"]):
    if "Upcoming events" in heading.get_text(" ", strip=True):
        table = heading.find_next("table")

        if table:
            rows = table.find_all("tr")

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])

                if len(cells) < 4:
                    continue

                event_name = clean_text(
                    cells[0].get_text(" ", strip=True)
                )

                date_text = clean_text(
                    cells[1].get_text(" ", strip=True)
                )

                city = clean_text(
                    cells[2].get_text(" ", strip=True)
                )

                venue = clean_text(
                    cells[3].get_text(" ", strip=True)
                )

                events.append({
                    "name": event_name,
                    "date": parse_date(date_text),
                    "venue": venue,
                    "city": city,
                    "network": "PPV",
                    "promotion": "AEW"
                })

        break

# -------------------
# ROH
# -------------------

roh_url = (
    "https://en.wikipedia.org/wiki/"
    "List_of_Ring_of_Honor_pay-per-view_and_livestreaming_events"
)

response = requests.get(
    roh_url,
    headers=HEADERS,
    timeout=30
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for heading in soup.find_all(["h2", "h3"]):
    if "Upcoming" in heading.get_text(" ", strip=True):
        table = heading.find_next("table")

        if table:
            rows = table.find_all("tr")

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])

                if len(cells) < 4:
                    continue

                date_text = clean_text(
                    cells[0].get_text(" ", strip=True)
                )

                event_name = clean_text(
                    cells[1].get_text(" ", strip=True)
                )

                venue = clean_text(
                    cells[2].get_text(" ", strip=True)
                )

                city = clean_text(
                    cells[3].get_text(" ", strip=True)
                )

                events.append({
                    "name": event_name,
                    "date": parse_date(date_text),
                    "venue": venue,
                    "city": city,
                    "network": "PPV",
                    "promotion": "ROH"
                })

        break

# -------------------
# Retain recent past events
# -------------------

today = date.today()
retention_start = today - timedelta(
    days=PAST_EVENT_RETENTION_DAYS
)

current_event_keys = {
    event_key(event)
    for event in events
}

retained_count = 0

for previous_event in previous_events:
    key = event_key(previous_event)

    if key in current_event_keys:
        continue

    try:
        previous_event_date = datetime.strptime(
            previous_event["date"],
            "%Y-%m-%d"
        ).date()
    except (KeyError, TypeError, ValueError):
        continue

    if retention_start <= previous_event_date <= today:
        events.append(previous_event)
        current_event_keys.add(key)
        retained_count += 1

events.sort(
    key=lambda event: (
        event["date"],
        event.get("promotion", ""),
        event.get("name", "")
    )
)

EVENTS_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

with EVENTS_FILE.open(
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        events,
        f,
        indent=2,
        ensure_ascii=False
    )

print(f"Retained {retained_count} recent past events")
print(f"Generated {len(events)} events")
