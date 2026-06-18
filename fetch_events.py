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

rows = schedule_table.find_all("tr")

for i, row in enumerate(rows):
    cells = row.find_all(["td", "th"])

    print(f"\nROW {i}")
    print("CELL COUNT:", len(cells))

    for j, cell in enumerate(cells):
        print(f"CELL {j}: {cell.get_text(' ', strip=True)}")
