# Wrestling Calendar

An automatically updating iCalendar (`.ics`) subscription for major professional wrestling events.

Subscribe once, and your calendar stays up to date as event dates, venues, locations, and broadcast platforms are announced or changed.

## Included Events

- WWE Premium Live Events (PLEs)
- WWE Saturday/Sunday Night’s Main Events
- NXT Premium Live Events (PLEs)
- WWE/AAA Supercards
- Select AAA special events
- AEW Pay-Per-Views (PPVs)
- ROH Pay-Per-Views (PPVs)

Weekly television shows and regular television specials are intentionally excluded to keep the calendar focused on major events.

Completed events remain on the calendar for approximately seven days before being removed.

## Subscribe

Use this subscription URL:

https://mmalinconico.github.io/wrestling-calendar/calendar.ics

## Features

- Retrieves upcoming event information from Wikipedia.
- Updates every four hours using GitHub Actions.
- Automatically updates event dates, venues, cities, and broadcast platforms as information changes.
- Retains completed events for seven days.
- Generates a standards-compliant iCalendar (`.ics`) subscription.
- Hosted with GitHub Pages.

## Regression Tests and Publication Safeguards

- **Test Wrestling Calendar** runs offline regression tests and validates the
  checked-in ICS when a pull request to `main` is opened or updated.
- Production runs the same regression suite before fetching Wikipedia data and
  validates the newly generated ICS **before** committing or publishing.
- Tests cover WWE/NXT/AAA/AEW/ROH filtering, incomplete dates, delayed airing,
  promotion classifications, stable UIDs, seven-day retention, duplicate
  prevention, network/venue metadata, and RFC 5545 all-day formatting.
- If a previously published *future* event unexpectedly disappears, the
  production update **fails closed**. The existing subscription remains
  unchanged until a source-data correction or confirmed cancellation is
  reviewed. Date moves and normal retention still work.
- Unchanged JSON and ICS output is not rewritten, and the production workflow
  commits only if there is a real content change. This avoids unnecessary
  GitHub Pages deployments.
- No tests make live network requests. The production fetch cadence stays
  every four hours.

To test locally: `python -m unittest discover -s tests -v` followed by
`python validate_calendar.py` (the latter checks the tracked ICS/JSON files).

## Supported Calendar Apps

- Apple Calendar
- Google Calendar
- Microsoft Outlook
- Any application that supports iCalendar subscriptions

## How It Works

A scheduled GitHub Actions workflow retrieves the latest event data, rebuilds the calendar file, and publishes any changes through GitHub Pages.

## Data Sources

- Wikipedia — WWE
- Wikipedia — AAA
- Wikipedia — AEW
- Wikipedia — ROH

## Disclaimer

This is an unofficial, fan-created calendar and is not affiliated with WWE, NXT, AAA, AEW, or ROH.

Event information is sourced from publicly available data and updated automatically. Event dates, venues, locations, and broadcast platforms are subject to change.
