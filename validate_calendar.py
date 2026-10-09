"""Independent RFC 5545 and Apple Calendar compatibility checks for the feed.

Validation is read-only. Run after generating calendar.ics and before git add.
"""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from generate_calendar import display_name, escape_ical_text

REQUIRED_CALENDAR_PROPERTIES = (
    "VERSION:2.0",
    "PRODID:-//Matt Malinconico//Wrestling Calendar//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Wrestling Calendar",
)


def validate_calendar(calendar_bytes, events):
    """Raise ValueError for malformed, changed, or mismatched calendar data."""
    if not calendar_bytes or not calendar_bytes.endswith(b"\r\n"):
        raise ValueError("ICS must end with CRLF")
    if b"\n" in calendar_bytes.replace(b"\r\n", b""):
        raise ValueError("ICS contains LF not preceded by CR")
    if b"\r" in calendar_bytes.replace(b"\r\n", b""):
        raise ValueError("ICS contains bare CR")
    if calendar_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValueError("ICS must not include a UTF-8 BOM")

    physical_lines = calendar_bytes[:-2].split(b"\r\n")
    for line in physical_lines:
        if not line:
            raise ValueError("ICS contains a blank physical line")
        if len(line) > 75:
            raise ValueError("ICS line exceeds RFC 5545 75-octet limit")

    try:
        text = calendar_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("ICS must be valid UTF-8") from exc

    logical_lines = []
    for line in text[:-2].split("\r\n"):
        if line.startswith((" ", "\t")):
            if not logical_lines:
                raise ValueError("Orphaned folded continuation")
            logical_lines[-1] += line[1:]
        else:
            logical_lines.append(line)

    if logical_lines[0] != "BEGIN:VCALENDAR":
        raise ValueError("Missing BEGIN:VCALENDAR")
    if logical_lines[-1] != "END:VCALENDAR":
        raise ValueError("Missing END:VCALENDAR")
    if logical_lines[1:6] != list(REQUIRED_CALENDAR_PROPERTIES):
        raise ValueError("Calendar metadata changed unexpectedly")

    published = []
    position = 6
    while position < len(logical_lines) - 1:
        if logical_lines[position] != "BEGIN:VEVENT":
            raise ValueError("Unexpected content outside VEVENT")
        position += 1
        properties = {}
        while position < len(logical_lines) - 1:
            line = logical_lines[position]
            position += 1
            if line == "END:VEVENT":
                break
            if ":" not in line:
                raise ValueError("VEVENT property lacks colon")
            key, value = line.split(":", 1)
            if key in properties:
                raise ValueError(f"Duplicate property in VEVENT: {key}")
            if not key or not value:
                raise ValueError("Empty VEVENT property name/value")
            properties[key] = value
        else:
            raise ValueError("Unterminated VEVENT")
        published.append(properties)

    if len(events) != len(published):
        raise ValueError("JSON and ICS event counts differ")

    json_uids = [event.get("uid") for event in events]
    feed_uids = [event.get("UID") for event in published]
    if (not all(json_uids) or not all(feed_uids)
            or len(json_uids) != len(set(json_uids))
            or len(feed_uids) != len(set(feed_uids))):
        raise ValueError("Missing or duplicated event UID")
    if set(json_uids) != set(feed_uids):
        raise ValueError("JSON and ICS UID sets differ")

    event_by_uid = {item["uid"]: item for item in events}
    for properties in published:
        item = event_by_uid[properties["UID"]]
        allowed = {
            "UID", "DTSTAMP", "DTSTART;VALUE=DATE", "DTEND;VALUE=DATE",
            "SUMMARY", "DESCRIPTION", "LOCATION",
        }
        if not set(properties).issubset(allowed):
            raise ValueError("Unexpected VEVENT property or timed event")

        stamp = properties.get("DTSTAMP", "")
        if not re.fullmatch(r"\d{8}T\d{6}Z", stamp):
            raise ValueError("DTSTAMP must be UTC in YYYYMMDDTHHMMSSZ format")
        try:
            datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
            start = date.fromisoformat(item["date"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("Invalid date or timestamp") from exc

        expected = {
            "UID": item["uid"],
            "DTSTAMP": item["dtstamp"],
            "DTSTART;VALUE=DATE": start.strftime("%Y%m%d"),
            "DTEND;VALUE=DATE": (start + timedelta(days=1)).strftime("%Y%m%d"),
            "SUMMARY": escape_ical_text(display_name(item)),
        }
        if item.get("network"):
            expected["DESCRIPTION"] = escape_ical_text(
                "Network: " + item["network"]
            )
        location = ", ".join(
            part for part in (item.get("venue"), item.get("city")) if part
        )
        if location:
            expected["LOCATION"] = escape_ical_text(location)

        if properties != expected:
            raise ValueError(
                f"Calendar contents disagree with JSON for {item['uid']}"
            )
    return len(published)


def main():
    with Path("data/events.json").open(encoding="utf-8") as stream:
        events = json.load(stream)
    count = validate_calendar(Path("calendar.ics").read_bytes(), events)
    print(f"Validated {count} RFC 5545 all-day events (Apple Calendar safe)")


if __name__ == "__main__":
    main()
