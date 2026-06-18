import json
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

for row in rows[1:]:
    cells = row.find_all(["td", "th"])

    if len(cells) < 4:
        continue

    date = cells[0].get_text(" ", strip=True)
    event_name = cells[1].get_text(" ", strip=True)
    venue = cells[2].get_text(" ", strip=True)
    city = cells[3].get_text(" ", strip=True)

    if date == "TBA":
        continue

    promotion = "NXT" if "Great American Bash" in event_name else "WWE"

    if promotion == "NXT":
        network = "The CW"
    elif "Main Event" in event_name:
        network = "Peacock"
    else:
        network = "ESPN"

    events.append({
        "name": event_name,
        "date": date,
        "venue": venue,
        "city": city,
        "network": network,
        "promotion": promotion
    })

with open("data/events.json", "w") as f:
    json.dump(events, f, indent=2)

print(f"Generated {len(events)} events")
