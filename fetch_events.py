import requests
from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_All_Elite_Wrestling_pay-per-view_events"

headers = {
"User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

response = requests.get(URL, headers=headers)
response.raise_for_status()

print("Status:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

for heading in soup.find_all(["h2", "h3"]):
text = heading.get_text(" ", strip=True)

```
if "Upcoming events" in text:
    print("\nFOUND HEADING:", text)

    tables = heading.find_all_next("table", limit=5)

    for i, table in enumerate(tables):
        print(f"\n--- TABLE {i} ---")
        print(table.get_text(" ", strip=True)[:3000])

    break
```
