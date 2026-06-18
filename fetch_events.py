import requests
from bs4 import BeautifulSoup

url = "https://en.wikipedia.org/wiki/List_of_WWE_pay-per-view_and_livestreaming_supercards"

headers = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

for heading in soup.find_all(["h2", "h3"]):
    heading_text = heading.get_text(" ", strip=True)

    if "Upcoming event schedule" in heading_text:
        print("\nFOUND HEADING:")
        print(heading_text)

        table = heading.find_next("table")

        if table:
            print("\nTABLE CONTENT:")
            print(table.get_text(" ", strip=True)[:5000])

        break
