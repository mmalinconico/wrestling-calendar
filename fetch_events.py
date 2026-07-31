import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "WrestlingCalendarBot/1.0 (personal hobby calendar)"
}

EVENTS_FILE = Path("data/events.json")
PAST_EVENT_RETENTION_DAYS = 7
MAX_RESCHEDULE_MATCH_DAYS = 180

AAA_INCLUDED_EVENT_NAMES = {
    "eternal glory",
}

CALENDAR_FIELDS = (
    "name",
    "date",
    "venue",
    "city",
    "network",
    "promotion",
)


def clean_text(text):
    text = re.sub(r"\[\s*\d+\s*\]", "", str(text))
    text = " ".join(text.split()).strip()
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text


def normalize_text(text):
    normalized = unicodedata.normalize("NFKD", str(text))
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return clean_text(normalized).casefold()


def slugify(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "unknown"


def parse_date(date_text, year=None):
    cleaned = clean_text(date_text)

    if year is not None:
        cleaned = re.sub(r",?\s+\d{4}$", "", cleaned).strip()
        parsed = datetime.strptime(
            f"{cleaned} {year}",
            "%B %d %Y",
        )
        return parsed.strftime("%Y-%m-%d")

    for date_format in (
        "%B %d, %Y",
        "%B %d %Y",
        "%b %d, %Y",
        "%b %d %Y",
    ):
        try:
            parsed = datetime.strptime(cleaned, date_format)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    today = date.today()
    parsed = datetime.strptime(
        f"{cleaned} {today.year}",
        "%B %d %Y",
    )

    # Dates older than the retention window are assumed to belong
    # to the next calendar year when the source omits the year.
    if parsed.date() < today - timedelta(days=PAST_EVENT_RETENTION_DAYS):
        parsed = parsed.replace(year=today.year + 1)

    return parsed.strftime("%Y-%m-%d")


def extract_month_day(date_text):
    match = re.match(
        r"^(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2}\b",
        clean_text(date_text),
    )

    return match.group(0) if match else None


def event_key(event):
    return (
        event.get("promotion", ""),
        event.get("name", ""),
        event.get("date", ""),
    )


def name_key(event):
    return (
        event.get("promotion", ""),
        normalize_text(event.get("name", "")),
    )


def load_previous_events():
    if not EVENTS_FILE.exists():
        return []

    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load previous events: {error}")

    return []


def fetch_soup(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    if soup.title is None or not soup.find("table"):
        raise RuntimeError(f"Unexpected page structure at {url}")

    return soup


def find_heading(soup, text_fragment, levels=("h2", "h3")):
    wanted = normalize_text(text_fragment)

    for heading in soup.find_all(list(levels)):
        heading_text = normalize_text(
            heading.get_text(" ", strip=True)
        )

        if wanted in heading_text:
            return heading

    return None


def find_table_in_section(heading, required_words=()):
    if heading is None:
        return None

    element = heading.find_next()

    while element:
        if element.name == "h2":
            return None

        if element.name == "table":
            table_text = normalize_text(
                element.get_text(" ", strip=True)
            )

            if all(word in table_text for word in required_words):
                return element

        element = element.find_next()

    return None


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
                        rows_remaining - 1,
                    )

                column_index += 1
                continue

            if cell_index < len(cells):
                cell = cells[cell_index]
                value = clean_text(
                    cell.get_text(" ", strip=True)
                )

                try:
                    rowspan = int(cell.get("rowspan", 1))
                    colspan = int(cell.get("colspan", 1))
                except (TypeError, ValueError):
                    rowspan = 1
                    colspan = 1

                for _ in range(colspan):
                    expanded.append(value)

                    if rowspan > 1:
                        pending_rowspans[column_index] = (
                            value,
                            rowspan - 1,
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


def legacy_uid_for_event(event):
    promotion = slugify(event.get("promotion", "wrestling"))
    name = slugify(event.get("name", "event"))
    event_date = slugify(event.get("date", "unknown-date"))

    if name == promotion or name.startswith(f"{promotion}-"):
        identity = name
    else:
        identity = f"{promotion}-{name}"

    return (
        f"wrestling-{identity}-{event_date}"
        "@mmalinconico.github.io"
    )


def calendar_data_changed(current_event, previous_event):
    return any(
        current_event.get(field, "")
        != previous_event.get(field, "")
        for field in CALENDAR_FIELDS
    )


def parse_stored_date(event):
    try:
        return datetime.strptime(
            event.get("date", ""),
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return None


def assign_stable_metadata(events, previous_events):
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    claimed = set()

    def available_candidates(predicate):
        return [
            previous
            for previous in previous_events
            if id(previous) not in claimed and predicate(previous)
        ]

    for event in events:
        matched = None

        exact_candidates = available_candidates(
            lambda previous: event_key(previous) == event_key(event)
        )

        if exact_candidates:
            matched = exact_candidates[0]

        if matched is None:
            current_date = parse_stored_date(event)
            same_name_candidates = available_candidates(
                lambda previous: name_key(previous) == name_key(event)
            )

            dated_candidates = []

            for previous in same_name_candidates:
                previous_date = parse_stored_date(previous)

                if current_date is None or previous_date is None:
                    continue

                difference = abs((previous_date - current_date).days)

                if difference <= MAX_RESCHEDULE_MATCH_DAYS:
                    dated_candidates.append((difference, previous))

            if dated_candidates:
                dated_candidates.sort(key=lambda item: item[0])
                matched = dated_candidates[0][1]

        if matched is None:
            same_date_candidates = available_candidates(
                lambda previous: (
                    previous.get("promotion") == event.get("promotion")
                    and previous.get("date") == event.get("date")
                )
            )

            if len(same_date_candidates) == 1:
                matched = same_date_candidates[0]

        if matched is not None:
            claimed.add(id(matched))
            event["uid"] = (
                matched.get("uid")
                or legacy_uid_for_event(matched)
            )

            if (
                matched.get("dtstamp")
                and not calendar_data_changed(event, matched)
            ):
                event["dtstamp"] = matched["dtstamp"]
            else:
                event["dtstamp"] = timestamp
        else:
            event["uid"] = legacy_uid_for_event(event)
            event["dtstamp"] = timestamp


def validate_source(
    source_name,
    structure_found,
    parsed_events,
    previous_events,
    promotions,
):
    if not structure_found:
        raise RuntimeError(
            f"{source_name}: expected schedule section/table not found. "
            "Aborting without replacing the calendar data."
        )

    today_text = date.today().isoformat()
    previous_future = [
        event
        for event in previous_events
        if event.get("promotion") in promotions
        and event.get("date", "") >= today_text
    ]

    if not parsed_events and previous_future:
        raise RuntimeError(
            f"{source_name}: parsed zero events while "
            f"{len(previous_future)} future events were previously stored. "
            "Aborting to prevent an accidental wipe."
        )


def scrape_wwe(previous_events):
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_WWE_pay-per-view_and_livestreaming_supercards"
    )
    soup = fetch_soup(url)
    heading = find_heading(soup, "Upcoming event schedule")
    table = find_table_in_section(
        heading,
        required_words=("date", "event", "venue"),
    )
    parsed_events = []

    if table is not None:
        rows = table.find_all("tr")
        index = 1

        while index < len(rows):
            cells = rows[index].find_all(["td", "th"])

            if len(cells) < 4:
                index += 1
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
                index += 1
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

            if event_name == "Worlds Collide":
                promotion = "WWE/AAA"
                network = "YouTube"

            if "two-part event" in notes.lower():
                parsed_events.append({
                    "name": f"{event_name} Night 1",
                    "date": parse_date(date_text),
                    "venue": venue,
                    "city": city,
                    "network": network,
                    "promotion": promotion,
                })

                if index + 1 >= len(rows):
                    raise RuntimeError(
                        f"WWE/NXT: second date missing for {event_name}."
                    )

                next_cells = rows[index + 1].find_all(["td", "th"])

                if len(next_cells) != 1:
                    raise RuntimeError(
                        f"WWE/NXT: unexpected second-date row for {event_name}."
                    )

                night2_date = clean_text(
                    next_cells[0].get_text(" ", strip=True)
                )

                parsed_events.append({
                    "name": f"{event_name} Night 2",
                    "date": parse_date(night2_date),
                    "venue": venue,
                    "city": city,
                    "network": network,
                    "promotion": promotion,
                })

                index += 1
            else:
                parsed_events.append({
                    "name": event_name,
                    "date": parse_date(date_text),
                    "venue": venue,
                    "city": city,
                    "network": network,
                    "promotion": promotion,
                })

            index += 1

    validate_source(
        "WWE/NXT",
        table is not None,
        parsed_events,
        previous_events,
        {"WWE", "NXT", "WWE/AAA"},
    )
    return parsed_events


def scrape_aaa(previous_events):
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_major_Lucha_Libre_AAA_Worldwide_events"
    )
    soup = fetch_soup(url)
    heading = find_heading(
        soup,
        "Upcoming event schedule",
        levels=("h2",),
    )
    parsed_rows = []
    year_table_count = 0

    if heading is not None:
        for year_heading in heading.find_all_next(["h2", "h3"]):
            if year_heading is heading:
                continue

            if year_heading.name == "h2":
                break

            year_text = clean_text(
                year_heading.get_text(" ", strip=True)
            )

            if not re.fullmatch(r"\d{4}", year_text):
                continue

            year = int(year_text)
            table = find_table_before_next_heading(year_heading)

            if table is None:
                continue

            year_table_count += 1

            for cells in expand_table_rows(table)[1:]:
                if len(cells) < 4:
                    continue

                date_text = cells[0]
                event_name = cells[1]
                city = cells[2]
                venue = cells[3]

                if not is_included_aaa_event(event_name):
                    continue

                month_day = extract_month_day(date_text)

                # Eternal Glory remains excluded until a complete
                # month-and-day date is listed.
                if not month_day:
                    continue

                parsed_rows.append({
                    "name": event_name,
                    "date": parse_date(month_day, year=year),
                    "venue": venue or "TBA",
                    "city": city or "TBA",
                    "network": "YouTube",
                    "promotion": "AAA",
                })

    event_counts = {}

    for event in parsed_rows:
        name = event["name"]
        event_counts[name] = event_counts.get(name, 0) + 1

    event_numbers = {}
    parsed_events = []

    for event in parsed_rows:
        name = event["name"]

        if event_counts[name] > 1:
            event_numbers[name] = event_numbers.get(name, 0) + 1
            event["name"] = f"{name} Night {event_numbers[name]}"

        parsed_events.append(event)

    validate_source(
        "AAA",
        heading is not None and year_table_count > 0,
        parsed_events,
        previous_events,
        {"AAA"},
    )
    return parsed_events


def scrape_aew(previous_events):
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_All_Elite_Wrestling_pay-per-view_events"
    )
    soup = fetch_soup(url)
    heading = find_heading(soup, "Upcoming events")
    table = find_table_in_section(heading)
    parsed_events = []

    if table is not None:
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])

            if len(cells) < 4:
                continue

            parsed_events.append({
                "name": clean_text(
                    cells[0].get_text(" ", strip=True)
                ),
                "date": parse_date(
                    clean_text(cells[1].get_text(" ", strip=True))
                ),
                "city": clean_text(
                    cells[2].get_text(" ", strip=True)
                ),
                "venue": clean_text(
                    cells[3].get_text(" ", strip=True)
                ),
                "network": "PPV",
                "promotion": "AEW",
            })

    validate_source(
        "AEW",
        table is not None,
        parsed_events,
        previous_events,
        {"AEW"},
    )
    return parsed_events


def scrape_roh(previous_events):
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_Ring_of_Honor_pay-per-view_and_livestreaming_events"
    )
    soup = fetch_soup(url)
    heading = find_heading(soup, "Upcoming")
    table = find_table_in_section(heading)
    parsed_events = []

    if table is not None:
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])

            if len(cells) < 4:
                continue

            parsed_events.append({
                "date": parse_date(
                    clean_text(cells[0].get_text(" ", strip=True))
                ),
                "name": clean_text(
                    cells[1].get_text(" ", strip=True)
                ),
                "venue": clean_text(
                    cells[2].get_text(" ", strip=True)
                ),
                "city": clean_text(
                    cells[3].get_text(" ", strip=True)
                ),
                "network": "PPV",
                "promotion": "ROH",
            })

    validate_source(
        "ROH",
        table is not None,
        parsed_events,
        previous_events,
        {"ROH"},
    )
    return parsed_events


def retain_recent_past_events(events, previous_events):
    today = date.today()
    retention_start = today - timedelta(
        days=PAST_EVENT_RETENTION_DAYS
    )
    current_keys = {event_key(event) for event in events}
    retained_count = 0

    for previous_event in previous_events:
        key = event_key(previous_event)

        if key in current_keys:
            continue

        previous_date = parse_stored_date(previous_event)

        if (
            previous_date is not None
            and retention_start <= previous_date <= today
        ):
            events.append(dict(previous_event))
            current_keys.add(key)
            retained_count += 1

    return retained_count


def deduplicate_events(events):
    unique_events = []
    seen_keys = set()

    for event in events:
        key = event_key(event)

        if key in seen_keys:
            continue

        seen_keys.add(key)
        unique_events.append(event)

    return unique_events


def write_events_atomically(events):
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = EVENTS_FILE.with_suffix(".json.tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(
            events,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    temporary_file.replace(EVENTS_FILE)


def main():
    previous_events = load_previous_events()

    events = []
    events.extend(scrape_wwe(previous_events))
    events.extend(scrape_aaa(previous_events))
    events.extend(scrape_aew(previous_events))
    events.extend(scrape_roh(previous_events))

    events = deduplicate_events(events)
    retained_count = retain_recent_past_events(
        events,
        previous_events,
    )
    assign_stable_metadata(events, previous_events)

    events.sort(
        key=lambda event: (
            event["date"],
            event.get("promotion", ""),
            event.get("name", ""),
        )
    )

    write_events_atomically(events)

    print(f"Retained {retained_count} recent past events")
    print(f"Generated {len(events)} events")


if __name__ == "__main__":
    main()
