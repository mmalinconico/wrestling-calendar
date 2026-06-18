import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_WWE_pay-per-view_and_livestreaming_supercards"

headers = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

response = requests.get(URL, headers=headers)
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

if schedule_table is None:
    raise Exception("Could not find Upcoming event schedule table")

events = []

rows = schedule_table.find_all("tr")
year = 2026

i = 1

while i < len(rows):
    cells = rows[i].find_all(["td", "th"])

    if len(cells) < 4:
        i += 1
        continue

    date_text = cells[0].get_text(" ", strip=True)
    event_name = cells[1].get_text(" ", strip=True)
    venue = cells[2].get_text(" ", strip=True)
    city = cells[3].get_text(" ", strip=True)
    notes = cells[4].get_text(" ", strip=True) if len(cells) > 4 else ""

    if date_text == "TBA":
        i += 1
        continue

    event_name = re.sub(r"\[\s*\d+\s*\]", "", event_name).strip()

    promotion = "NXT" if "Great American Bash" in event_name else "WWE"

    if promotion == "NXT":
        network = "The CW"
    elif "Main Event" in event_name:
        network = "Peacock"
    else:
        network = "ESPN"

    date_obj = datetime.strptime(
        f"{date_text} {year}",
        "%B %d %Y"
    )

    # Handle two-night events
    if "two-part event" in notes.lower():
        events.append({
            "name": f"{event_name} Night 1",
            "date": date_obj.strftime("%Y-%m-%d"),
            "venue": venue,
            "city": city,
            "network": network,
            "promotion": promotion
        })

        if i + 1 < len(rows):
            next_cells = rows[i + 1].find_all(["td", "th"])

            if len(next_cells) == 1:
                night2_date = next_cells[0].get_text(" ", strip=True)

                night2_obj = datetime.strptime(
                    f"{night2_date} {year}",
                    "%B %d %Y"
                )

                events.append({
                    "name": f"{event_name} Night 2",
                    "date": night2_obj.strftime("%Y-%m-%d"),
                    "venue": venue,
                    "city": city,
                    "network": network,
                    "promotion": promotion
                })

                i += 1

    else:
        events.append({
            "name": event_name,
            "date": date_obj.strftime("%Y-%m-%d"),
            "venue": venue,
            "city": city,
            "network": network,
            "promotion": promotion
        })

    i += 1

with open("data/events.json", "w") as f:
    json.dump(events, f, indent=2)

print(f"Generated {len(events)} events")
