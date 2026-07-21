# Wrestling Calendar

An automatically updating iCalendar (`.ics`) subscription for major professional wrestling events.

Subscribe once, and your calendar stays up to date as event dates, venues, locations, and broadcast platforms are announced or changed.

## Included Events

- WWE Premium Live Events (PLEs)
- WWE Saturday Night’s Main Event
- WWE Sunday Night’s Main Event
- NXT Premium Live Events (PLEs)
- WWE/AAA Supercards
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

## Supported Calendar Apps

- Apple Calendar
- Google Calendar
- Microsoft Outlook
- Any application that supports iCalendar subscriptions

## How It Works

A scheduled GitHub Actions workflow retrieves the latest event data, rebuilds the calendar file, and publishes any changes through GitHub Pages.

## Data Sources

- Wikipedia — WWE
- Wikipedia — AEW
- Wikipedia — Ring of Honor (ROH)

## Disclaimer

This is an unofficial, fan-created calendar and is not affiliated with WWE, NXT, AAA, AEW, or ROH.

Event information is sourced from publicly available data and updated automatically. Event dates, venues, locations, and broadcast platforms are subject to change.
