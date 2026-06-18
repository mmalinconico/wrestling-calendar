import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}



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


events = []

# -------------------
# WWE / NXT
# -------------------

wwe_url = "https://en.wikipedia.org/wiki/List_of_WWE_pay-per-view_and_livestreaming_supercards"

response = requests.get(wwe_url, headers=HEADERS)
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

        date_text = clean_text(cells[0].get_text(" ", strip=True))
        event_name = clean_text(cells[1].get_text(" ", strip=True))
        venue = clean_text(cells[2].get_text(" ", strip=True))
        city = clean_text(cells[3].get_text(" ", strip=True))
        notes = clean_text(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else ""

        if date_text == "TBA":
            i += 1
            continue

        promotion = "NXT" if "Great American Bash" in event_name else "WWE"

        if promotion == "NXT":
            network = "The CW"
        elif "Main Event" in event_name:
            network = "Peacock"
        else:
            network = "ESPN"

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
                next_cells = rows[i + 1].find_all(["td", "th"])

                if len(next_cells) == 1:
                    night2_date = clean_text(next_cells[0].get_text(" ", strip=True))

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
# AEW / ROH
# -------------------

aew_url = "https://en.wikipedia.org/wiki/List_of_All_Elite_Wrestling_pay-per-view_events"

response = requests.get(aew_url, headers=HEADERS)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for heading in soup.find_all(["h2", "h3"]):
    if "Upcoming events" in heading.get_text(" ", strip=True):

        table = heading.find_next("table")

        rows = table.find_all("tr")

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])

            if len(cells) < 4:
                continue

            event_name = clean_text(cells[0].get_text(" ", strip=True))
            date_text = clean_text(cells[1].get_text(" ", strip=True))
            city = clean_text(cells[2].get_text(" ", strip=True))
            venue = clean_text(cells[3].get_text(" ", strip=True))

            promotion = "AEW"

            events.append({
                "name": event_name,
                "date": parse_date(date_text),
                "venue": venue,
                "city": city,
                "network": "PPV",
                "promotion": promotion
            })

        break

events.sort(key=lambda x: x["date"])

with open("data/events.json", "w") as f:
    json.dump(events, f, indent=2)

print(f"Generated {len(events)} events")
