"""Offline regression coverage for WWE/NXT/AAA/AEW/ROH and iCalendar.

No test calls Wikipedia. Fixtures deliberately exercise the HTML/wikitext
shapes the production scraper relies on.
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

import fetch_events as f
import generate_calendar as g
from validate_calendar import validate_calendar


def event(name, when="2026-11-07", promotion="WWE", **overrides):
    data = {
        "name": name, "date": when, "promotion": promotion,
        "venue": "Test Arena", "city": "Test City",
        "network": "ESPN",
    }
    data.update(overrides)
    return data


def soup(html):
    return BeautifulSoup(html, "html.parser")


def schedule(section, headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr" + (f' style="{style}"' if style else "") + ">"
        + "".join(f"<td>{value}</td>" for value in cells)
        + "</tr>"
        for cells, style in rows
    )
    return soup(
        f"<html><title>Fixture</title><h2>{section}</h2>"
        f"<h3>2026</h3><table><tr>{head}</tr>{body}</table></html>"
    )


class DateAndSourceRules(unittest.TestCase):
    def test_complete_dates_only(self):
        self.assertEqual(
            f.parse_complete_date("November 7", year=2026), "2026-11-07"
        )
        for value in ("TBA", "TBD", "November", "November 7–8",
                      "November 7 and 8", "November 7 to 8", ""):
            with self.subTest(value=value):
                self.assertIsNone(f.parse_complete_date(value, year=2026))

    def test_delayed_air_date_is_explicit_and_generic(self):
        self.assertEqual(
            f.parse_air_date_override(
                "September 26 (will air September 30)", year=2026
            ), "2026-09-30"
        )
        self.assertIsNone(
            f.parse_air_date_override("September 26", year=2026)
        )

    def test_rowspan_in_raw_wwe_classification(self):
        wiki = (
            "==Upcoming event schedule==\n"
            '{| class="wikitable" id="Upcoming_events_2026"\n'
            "!Date\n!Event\n"
            '|- style="background:#B9E2C9"\n'
            "|September 11\n"
            '|rowspan="2" | [[Triplemanía 34]]\n'
            '|- style="background:#B9E2C9"\n'
            "|September 13\n"
            "|}\n==Number of events by year=="
        )
        with mock.patch.object(f, "fetch_wikitext", return_value=wiki):
            classes = f.wwe_upcoming_classifications()
        self.assertEqual(
            classes[(f.normalize_text("Triplemanía 34"), "2026-09-11")],
            "WWE/AAA",
        )
        self.assertEqual(
            classes[(f.normalize_text("Triplemanía 34"), "2026-09-13")],
            "WWE/AAA",
        )

    def test_wwe_nxt_and_co_produced_event_details(self):
        rows = [
            (["October 10", "Money in the Bank", "Arena 1",
              "New Orleans", ""], ""),
            (["October 31", "Halloween Havoc", "TBA", "TBA", ""],
             "background-color:#FFFF80"),
            (["November 7", "Worlds Collide", "Allstate Arena",
              "Rosemont", ""], "background-color:#B9E2C9"),
            (["November 14", "Sunday Night's Main Event", "Arena 4",
              "Chicago", ""], ""),
            (["TBA", "Future Show", "TBA", "TBA", ""], ""),
        ]
        page = schedule("Upcoming event schedule",
                        ["Date", "Event", "Venue", "Location", "Notes"], rows)
        with (
            mock.patch.object(f, "fetch_soup", return_value=page),
            mock.patch.object(f, "wwe_upcoming_classifications",
                              return_value={}),
        ):
            result = f.scrape_wwe([])
        by_name = {x["name"]: x for x in result}
        self.assertEqual(len(result), 4)
        self.assertEqual(
            (by_name["Money in the Bank"]["promotion"],
             by_name["Money in the Bank"]["network"]), ("WWE", "ESPN")
        )
        self.assertEqual(
            (by_name["Halloween Havoc"]["promotion"],
             by_name["Halloween Havoc"]["network"]), ("NXT", "The CW")
        )
        self.assertEqual(
            (by_name["Worlds Collide"]["promotion"],
             by_name["Worlds Collide"]["network"]), ("WWE/AAA", "YouTube")
        )
        self.assertEqual(by_name["Worlds Collide"]["venue"],
                         "Allstate Arena")
        self.assertEqual(by_name["Sunday Night's Main Event"]["network"],
                         "Peacock")

    def test_two_part_wwe_aaa_event_has_both_nights(self):
        rows = [
            (["September 11", "Triplemanía 34", "Arena A", "City A",
              "Two-part event"], "background:#B9E2C9"),
            (["September 13", "Triplemanía 34", "Arena B", "City B",
              "Two-part event"], "background:#B9E2C9"),
        ]
        page = schedule("Upcoming event schedule",
                        ["Date", "Event", "Venue", "Location", "Notes"], rows)
        with (
            mock.patch.object(f, "fetch_soup", return_value=page),
            mock.patch.object(f, "wwe_upcoming_classifications",
                              return_value={}),
        ):
            result = f.scrape_wwe([])
        self.assertEqual([x["name"] for x in result], [
            "Triplemanía 34 Night 1", "Triplemanía 34 Night 2"
        ])
        self.assertEqual([x["venue"] for x in result], ["Arena A", "Arena B"])

    def test_wwe_past_events_recover_future_broadcast(self):
        html = (
            "<html><title>Fixture</title>"
            "<h2>Upcoming event schedule</h2><h3>2026</h3>"
            "<table><tr><th>Date</th><th>Event</th><th>Venue</th>"
            "<th>Location</th><th>Notes</th></tr>"
            "<tr><td>October 10</td><td>Money in the Bank</td>"
            "<td>Arena</td><td>City</td><td></td></tr></table>"
            "<h2>Past events</h2><h3>2026</h3>"
            "<table><tr><th>Date</th><th>Event</th><th>Venue</th>"
            "<th>Location</th><th>Notes</th></tr>"
            '<tr style="background:#B9E2C9">'
            "<td>September 26 (will air September 30)</td>"
            "<td>Worlds Collide</td><td>Allstate Arena</td>"
            "<td>Rosemont</td><td>YouTube</td></tr></table></html>"
        )
        with (
            mock.patch.object(f, "fetch_soup", return_value=soup(html)),
            mock.patch.object(f, "wwe_upcoming_classifications",
                              return_value={}),
            mock.patch.object(f, "calendar_today",
                              return_value=date(2026, 9, 27)),
        ):
            result = f.scrape_wwe([])
        collide = next(x for x in result if x["name"] == "Worlds Collide")
        self.assertEqual(collide["date"], "2026-09-30")
        self.assertEqual(collide["_source_date"], "2026-09-26")
        self.assertEqual(collide["promotion"], "WWE/AAA")
        self.assertEqual(collide["network"], "YouTube")

    def test_past_event_not_recovered_after_air_date(self):
        html = (
            "<html><title>Fixture</title>"
            "<h2>Upcoming event schedule</h2><h3>2026</h3>"
            "<table><tr><th>Date</th><th>Event</th><th>Venue</th>"
            "<th>Location</th></tr><tr><td>October 10</td>"
            "<td>Money in the Bank</td><td>Arena</td><td>City</td>"
            "</tr></table><h2>Past events</h2><h3>2026</h3>"
            "<table><tr><th>Date</th><th>Event</th><th>Venue</th>"
            "<th>Location</th></tr>"
            "<tr><td>September 26 (will air September 30)</td>"
            "<td>Worlds Collide</td><td>Arena</td><td>City</td></tr>"
            "</table></html>"
        )
        with (
            mock.patch.object(f, "fetch_soup", return_value=soup(html)),
            mock.patch.object(f, "wwe_upcoming_classifications",
                              return_value={}),
            mock.patch.object(f, "calendar_today",
                              return_value=date(2026, 10, 9)),
        ):
            result = f.scrape_wwe([])
        self.assertEqual([x["name"] for x in result], ["Money in the Bank"])

    def test_aaa_excludes_saturday_weekly_tv_and_keeps_specials(self):
        rows = [
            (["October 10", "Saturday Special", "Tijuana", "Venue A"], ""),
            (["October 11", "Lucha Event", "Monterrey", "Venue B"], ""),
            (["October 16", "Lucha Event", "Mexico City", "Venue C"], ""),
            (["TBA", "Undated", "City", "TBA"], ""),
        ]
        page = schedule("Upcoming event schedule",
                        ["Date", "Event", "Location", "Venue"], rows)
        with mock.patch.object(f, "fetch_soup", return_value=page):
            result = f.scrape_aaa([])
        self.assertEqual([x["name"] for x in result], [
            "Lucha Event Night 1", "Lucha Event Night 2"
        ])
        self.assertEqual([x["network"] for x in result],
                         ["YouTube", "YouTube"])
        self.assertEqual(result[0]["city"], "Monterrey")

    def test_aew_only_dated_upcoming_pay_per_views(self):
        page = schedule(
            "Upcoming events",
            ["Event", "Date", "Location", "Venue"],
            [
                (["WrestleDream", "October 17", "Orlando", "Arena"], ""),
                (["Undated Show", "TBA", "Unknown", "TBA"], ""),
            ]
        )
        with mock.patch.object(f, "fetch_soup", return_value=page):
            result = f.scrape_aew([])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "WrestleDream")
        self.assertEqual(result[0]["network"], "PPV")
        self.assertEqual(result[0]["city"], "Orlando")

    def test_roh_only_dated_livestream_events(self):
        page = schedule(
            "Upcoming",
            ["Date", "Event", "Venue", "Location"],
            [
                (["November 7", "Final Battle", "ROH Arena",
                  "Philadelphia"], ""),
                (["TBA", "Surprise", "TBA", "TBA"], ""),
            ]
        )
        with mock.patch.object(f, "fetch_soup", return_value=page):
            result = f.scrape_roh([])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["promotion"], "ROH")
        self.assertEqual(result[0]["network"], "PPV")
        self.assertEqual(result[0]["venue"], "ROH Arena")

    def test_missing_source_structure_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "expected schedule"):
            f.validate_source("AEW", False, [], [], {"AEW"})

    def test_existing_future_items_require_future_source_data(self):
        old = [event("WrestleDream", "2026-10-17", "AEW")]
        with mock.patch.object(f, "calendar_today",
                               return_value=date(2026, 10, 9)):
            with self.assertRaisesRegex(RuntimeError, "no future"):
                f.validate_source("AEW", True, [], old, {"AEW"})


class SafetyAndIdentityRules(unittest.TestCase):
    def test_missing_one_future_event_blocks_publication(self):
        previous = [event("Crown Jewel"), event("Survivor Series", "2026-11-28")]
        current = [event("Crown Jewel")]
        with mock.patch.object(f, "calendar_today",
                               return_value=date(2026, 10, 9)):
            with self.assertRaisesRegex(RuntimeError,
                                        "Survivor Series"):
                f.guard_upcoming_event_losses(current, previous)

    def test_reschedule_and_reclassification_are_not_missing_events(self):
        previous = [event("Worlds Collide", "2026-09-26", "AAA")]
        current = [event("Worlds Collide", "2026-09-30", "WWE/AAA")]
        with mock.patch.object(f, "calendar_today",
                               return_value=date(2026, 9, 20)):
            f.guard_upcoming_event_losses(current, previous)

    def test_past_event_can_age_out(self):
        with mock.patch.object(f, "calendar_today",
                               return_value=date(2026, 10, 9)):
            f.guard_upcoming_event_losses(
                [], [event("Worlds Collide", "2026-09-30", "WWE/AAA")]
            )

    def test_stable_uid_and_stamp_when_unchanged(self):
        old = event("Crown Jewel",
                    uid="existing-uid@example.com",
                    dtstamp="20260901T000000Z")
        new = event("Crown Jewel")
        f.assign_stable_metadata([new], [old])
        self.assertEqual(new["uid"], old["uid"])
        self.assertEqual(new["dtstamp"], old["dtstamp"])

    def test_rescheduled_event_preserves_uid_and_updates_stamp(self):
        old = event("Worlds Collide", "2026-09-26", "WWE/AAA",
                    uid="original-physical-uid@example.com",
                    dtstamp="20260901T000000Z")
        new = event("Worlds Collide", "2026-09-30", "WWE/AAA",
                    _source_date="2026-09-26")
        f.assign_stable_metadata([new], [old])
        self.assertEqual(new["uid"], old["uid"])
        self.assertNotEqual(new["dtstamp"], old["dtstamp"])

    def test_new_delayed_event_uses_physical_date_uid(self):
        delayed = event("Worlds Collide", "2026-09-30", "WWE/AAA",
                        _source_date="2026-09-26")
        self.assertIn("2026-09-26@", f.legacy_uid_for_event(delayed))

    def test_recent_past_retention_is_seven_days_inclusive(self):
        today = date(2026, 10, 9)
        events = [
            event("Seven Days", "2026-10-02"),
            event("Eight Days", "2026-10-01"),
            event("Future", "2026-11-07"),
        ]
        with mock.patch.object(f, "calendar_today", return_value=today):
            kept, removed = f.filter_events_by_retention(events)
        self.assertEqual([x["name"] for x in kept],
                         ["Seven Days", "Future"])
        self.assertEqual(removed, 1)

    def test_recent_history_retained_but_superseded_date_is_not(self):
        previous = [
            event("Worlds Collide", "2026-09-26", "WWE/AAA"),
            event("Another", "2026-09-27"),
        ]
        current = [event("Worlds Collide", "2026-09-30", "WWE/AAA",
                         _source_date="2026-09-26")]
        with mock.patch.object(f, "calendar_today",
                               return_value=date(2026, 9, 29)):
            count = f.retain_recent_past_events(current, previous)
        self.assertEqual(count, 1)
        self.assertEqual([x["name"] for x in current],
                         ["Worlds Collide", "Another"])

    def test_aaa_duplicate_suppression_uses_physical_date(self):
        current = [
            event("Worlds Collide", "2026-09-30", "WWE/AAA",
                  _source_date="2026-09-26"),
            event("Worlds Collide", "2026-09-26", "AAA"),
        ]
        result, removed = f.suppress_aaa_duplicates(current)
        self.assertEqual(removed, 1)
        self.assertEqual([x["promotion"] for x in result], ["WWE/AAA"])

    def test_exact_event_deduplication(self):
        first = event("Crown Jewel")
        second = dict(first)
        distinct = event("Full Gear", promotion="AEW")
        result = f.deduplicate_events([first, second, distinct])
        self.assertEqual(len(result), 2)

    def test_unchanged_json_is_not_rewritten(self):
        sample = [event("Crown Jewel")]
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "data/events.json"
            with mock.patch.object(f, "EVENTS_FILE", file):
                f.write_events_atomically(sample)
                self.assertTrue(file.exists())
                with mock.patch.object(Path, "replace",
                                       side_effect=AssertionError("rewrote")):
                    f.write_events_atomically(sample)


class CalendarFormatRules(unittest.TestCase):
    def sample_events(self):
        first = event(
            "Survivor Series: WarGames", "2026-11-28",
            uid="wrestling-unique-1@example.com",
            dtstamp="20260901T000000Z",
            city="Houston, Texas", venue="Daikin Park",
            network="ESPN",
        )
        second = event(
            "Lucha, Night; 1", "2026-11-29", "WWE/AAA",
            uid="wrestling-unique-2@example.com",
            dtstamp="20260901T000001Z",
            venue="Arena", city="México City",
            network="YouTube",
        )
        return [first, second]

    def render(self, items):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "events.json"
            feed = root / "calendar.ics"
            data.write_text(json.dumps(items), encoding="utf-8")
            with (
                mock.patch.object(g, "EVENTS_FILE", data),
                mock.patch.object(g, "CALENDAR_FILE", feed),
            ):
                g.main()
                first = feed.read_bytes()
                with mock.patch.object(Path, "replace",
                                       side_effect=AssertionError("rewrote")):
                    g.main()
                self.assertEqual(feed.read_bytes(), first)
            return first

    def test_correct_all_day_dates_and_details(self):
        items = self.sample_events()
        feed = self.render(items)
        self.assertEqual(validate_calendar(feed, items), 2)
        self.assertIn(b"DTSTART;VALUE=DATE:20261128", feed)
        self.assertIn(b"DTEND;VALUE=DATE:20261129", feed)
        self.assertIn(b"DESCRIPTION:Network: ESPN", feed)
        self.assertIn(b"SUMMARY:WWE Survivor Series: WarGames", feed)
        self.assertIn(b"LOCATION:Daikin Park\\, Houston\\, Texas", feed)
        self.assertIn(b"SUMMARY:WWE/AAA Lucha\\, Night\\; 1", feed)
        self.assertIn("México".encode("utf-8"), feed)

    def test_rfc_folding_is_utf8_octet_safe(self):
        item = self.sample_events()[0]
        item["venue"] = "Arena " + "É" * 60
        data = self.render([item])
        self.assertTrue(all(len(line) <= 75
                            for line in data.split(b"\r\n")))
        self.assertEqual(validate_calendar(data, [item]), 1)

    def test_rejects_bad_line_endings(self):
        items = self.sample_events()
        feed = self.render(items)
        with self.assertRaisesRegex(ValueError, "LF"):
            validate_calendar(feed.replace(b"\r\n", b"\n"), items)

    def test_rejects_duplicate_uids_in_json(self):
        items = self.sample_events()
        items[1]["uid"] = items[0]["uid"]
        with self.assertRaisesRegex(ValueError, "duplicated"):
            validate_calendar(self.render(self.sample_events()), items)

    def test_rejects_mismatched_ics_details(self):
        items = self.sample_events()
        feed = self.render(items)
        changed = feed.replace(b"Network: ESPN", b"Network: HBO!")
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_calendar(changed, items)

    def test_rejects_overlong_physical_lines(self):
        items = self.sample_events()
        feed = self.render(items)
        with self.assertRaisesRegex(ValueError, "75-octet"):
            validate_calendar(
                feed.replace(
                    b"X-WR-CALNAME:Wrestling Calendar",
                    b"X-WR-CALNAME:" + b"A" * 100,
                ),
                items,
            )

    def test_generator_rejects_duplicate_uid(self):
        items = self.sample_events()
        items[1]["uid"] = items[0]["uid"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "events.json"
            data.write_text(json.dumps(items), encoding="utf-8")
            with (
                mock.patch.object(g, "EVENTS_FILE", data),
                mock.patch.object(g, "CALENDAR_FILE", root / "calendar.ics"),
            ):
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    g.main()


if __name__ == "__main__":
    unittest.main()
