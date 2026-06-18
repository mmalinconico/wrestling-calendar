import requests
from bs4 import BeautifulSoup

url = "https://en.wikipedia.org/wiki/List_of_WWE_pay-per-view_and_livestreaming_supercards"

headers = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

tables = soup.find_all("table", class_="wikitable")

for i, table in enumerate(tables):
    text = table.get_text(" ", strip=True)

    if "Night of Champions" in text:
        print("\nFOUND TABLE:", i)
        print(text[:3000])
        break
