import json
import re
from datetime import datetime, timedelta
from pathlib import Path

EVENTS_FILE = Path("data/events.json")
CALENDAR_FILE = Path("calendar.ics")


def display_name(item):
    promotion = item.get("promotion", "")
    event_name = item["name"]

    if (
        promotion
        and event_name.lower().startswith(
            f"{promotion.lower()} "
        )
    ):
        return event_name

    if promotion:
        return f"{promotion} {event_name}"

    return event_name


def escape_ical_text(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_ical_line(line):
    lines = []
    current = ""
    current_length = 0

    for character in line:
        character_length = len(character.encode("utf-8"))

        if current and current_length + character_length > 75:
            lines.append(current)
            current = f" {character}"
            current_length = 1 + character_length
        else:
            current += character
            current_length += character_length

    lines.append(current)
    return "\r\n".join(lines)


def validate_event(item):
    for field in ("name", "date", "promotion", "uid", "dtstamp"):
        if not item.get(field):
            raise ValueError(
                f"Event is missing required field '{field}': {item}"
            )

    datetime.strptime(item["date"], "%Y-%m-%d")

    if not re.fullmatch(r"\d{8}T\d{6}Z", item["dtstamp"]):
        raise ValueError(
            f"Invalid DTSTAMP for {item['name']}: "
            f"{item['dtstamp']}"
        )


def serialize_event(item):
    validate_event(item)

    start_date = datetime.strptime(
        item["date"],
        "%Y-%m-%d",
    ).date()

    end_date = start_date + timedelta(days=1)

    location_parts = [
        value
        for value in (
            item.get("venue", ""),
            item.get("city", ""),
        )
        if value
    ]

    lines = [
        "BEGIN:VEVENT",
        f"UID:{item['uid']}",
        f"DTSTAMP:{item['dtstamp']}",
        f"DTSTART;VALUE=DATE:{start_date.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{end_date.strftime('%Y%m%d')}",
        f"SUMMARY:{escape_ical_text(display_name(item))}",
    ]

    if item.get("network"):
        lines.append(
            "DESCRIPTION:"
            + escape_ical_text(
                f"Network: {item['network']}"
            )
        )

    if location_parts:
        lines.append(
            "LOCATION:"
            + escape_ical_text(", ".join(location_parts))
        )

    lines.append("END:VEVENT")
    return lines


def write_calendar_atomically(lines):
    temporary_file = CALENDAR_FILE.with_suffix(".ics.tmp")

    content = "\r\n".join(
        fold_ical_line(line)
        for line in lines
    ) + "\r\n"

    temporary_file.write_bytes(
        content.encode("utf-8")
    )

    temporary_file.replace(CALENDAR_FILE)


def main():
    with EVENTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        events = json.load(file)

    if not isinstance(events, list):
        raise ValueError(
            "data/events.json must contain a list of events"
        )

    events.sort(
        key=lambda item: (
            item.get("date", ""),
            item.get("promotion", ""),
            item.get("name", ""),
        )
    )

    seen_uids = set()

    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Matt Malinconico//Wrestling Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Wrestling Calendar",
    ]

    for item in events:
        validate_event(item)

        uid = item["uid"]

        if uid in seen_uids:
            raise ValueError(
                f"Duplicate calendar UID detected: {uid}"
            )

        seen_uids.add(uid)
        calendar_lines.extend(
            serialize_event(item)
        )

    calendar_lines.append("END:VCALENDAR")

    write_calendar_atomically(
        calendar_lines
    )

    print(f"Generated {len(events)} events")


if __name__ == "__main__":
    main()
