import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

EVENTS_FILE = Path("data/events.json")
PAST_EVENT_RETENTION_DAYS = 7

AAA_INCLUDED_EVENT_NAMES = {
    "eternal glory"
}


def clean_text(text):
    text = re.sub(r"\[\s*\d+\s*\]", "", text)
    text = " ".join(text.split()).strip()
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text


def normalize_text(text):
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return clean_text(normalized).casefold()


def parse_date(date_text, year=None):
    today = date.today()

    if year is not None:
        parsed = datetime.strptime(
            f"{date_text} {year}",
            "%B %d %Y"
        )
        return parsed.strftime("%Y-%m-%d")

    current_year = datetime.now().year

    parsed = datetime.strptime(
        f"{date_text} {current_year}",
        "%B %d %Y"
    )

    # Keep dates from the last seven days in the current year.
    # Older dates are assumed to refer to the next calendar year.
    if parsed.date() < today - timedelta(days=PAST_EVENT_RETENTION_DAYS):
        parsed = parsed.replace(year=current_year + 1)

    return parsed.strftime("%Y-%m-%d")


def extract_month_day(date_text):
    match = re.match(
        r"^(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2}\b",
        clean_text(date_text)
    )

    if not match:
        return None

    return match.group(0)


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


def find_table_before_next_heading(heading):
    element = heading.find_next()

    while element:
        if element.name in ("h2", "h3"):
            return None

        if element.name == "table":
            return element

        element = element.find_next()

    return None


def expand_table_rows(table):
    expanded_rows = []
    pending_rowspans = {}

    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)

        expanded = []
        previous_rowspans = pending_rowspans
        pending_rowspans = {}

        column_index = 0
        cell_index = 0

        while cell_index < len(cells) or previous_rowspans:
            if column_index in previous_rowspans:
                value, rows_remaining = previous_rowspans.pop(
                    column_index
                )

                expanded.append(value)

                if rows_remaining > 1:
                    pending_rowspans[column_index] = (
                        value,
                        rows_remaining - 1
                    )

                column_index += 1
                continue

            if cell_index < len(cells):
                cell = cells[cell_index]
                value = clean_text(
                    cell.get_text(" ", strip=True)
                )

                rowspan = int(cell.get("rowspan", 1))
                colspan = int(cell.get("colspan", 1))

                for _ in range(colspan):
                    expanded.append(value)

                    if rowspan > 1:
                        pending_rowspans[column_index] = (
                            value,
                            rowspan - 1
                        )

                    column_index += 1

                cell_index += 1
                continue

            next_column = min(previous_rowspans)

            while column_index < next_column:
                expanded.append("")
                column_index += 1

        expanded_rows.append(expanded)

    return expanded_rows


def is_included_aaa_event(event_name):
    normalized_name = normalize_text(event_name)

    return (
        normalized_name.startswith("triplemania")
        or normalized_name in AAA_INCLUDED_EVENT_NAMES
    )


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
# AAA
# -------------------

aaa_url = (
    "https://en.wikipedia.org/wiki/"
    "List_of_major_Lucha_Libre_AAA_Worldwide_events"
)

response = requests.get(
    aaa_url,
    headers=HEADERS,
    timeout=30
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

aaa_rows = []
upcoming_heading = None

for heading in soup.find_all("h2"):
    if "Upcoming event schedule" in heading.get_text(" ", strip=True):
        upcoming_heading = heading
        break

if upcoming_heading:
    for heading in upcoming_heading.find_all_next(["h2", "h3"]):
        if heading is upcoming_heading:
            continue

        if heading.name == "h2":
            break

        year_text = clean_text(
            heading.get_text(" ", strip=True)
        )

        if not re.fullmatch(r"\d{4}", year_text):
            continue

        year = int(year_text)
        table = find_table_before_next_heading(heading)

        if not table:
            continue

        expanded_rows = expand_table_rows(table)

        for cells in expanded_rows[1:]:
            if len(cells) < 4:
                continue

            date_text = cells[0]
            event_name = cells[1]
            city = cells[2]
            venue = cells[3]

            if not is_included_aaa_event(event_name):
                continue

            month_day = extract_month_day(date_text)

            # Eternal Glory is approved, but it will not be added
            # until Wikipedia lists a complete month-and-day date.
            if not month_day:
                continue

            aaa_rows.append({
                "name": event_name,
                "date": parse_date(month_day, year=year),
                "venue": venue or "TBA",
                "city": city or "TBA",
                "network": "YouTube",
                "promotion": "AAA"
            })

aaa_event_counts = {}

for event in aaa_rows:
    name = event["name"]
    aaa_event_counts[name] = aaa_event_counts.get(name, 0) + 1

aaa_event_numbers = {}

for event in aaa_rows:
    name = event["name"]

    if aaa_event_counts[name] > 1:
        aaa_event_numbers[name] = aaa_event_numbers.get(name, 0) + 1
        event["name"] = (
            f"{name} Night {aaa_event_numbers[name]}"
        )

    events.append(event)

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
