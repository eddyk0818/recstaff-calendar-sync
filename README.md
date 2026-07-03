# RecStaff Calendar Sync

A Python automation tool that converts a RecStaff work schedule into an Apple Calendar-compatible `.ics` calendar feed.

## Why I built this

My work scheduling platform did not provide a native Apple Calendar export or iCal subscription link. I wanted my shifts to appear automatically in Apple Calendar, so I built a custom sync tool.

## What it does

- Opens the RecStaff schedule page using a saved authenticated browser session
- Extracts visible shift information from the rendered schedule calendar
- Parses shift dates, start times, end times, and role codes
- Generates an Apple Calendar-compatible `.ics` file
- Serves the `.ics` file locally so Apple Calendar can subscribe to it
- Can be automated with macOS LaunchAgents for periodic refreshes

## Tech used

- Python
- Playwright
- iCalendar / `.ics` format
- macOS LaunchAgents
- Local HTTP server

## How it works

RecStaff schedule page
→ Python + Playwright scraper
→ Parsed shift events
→ Generated `.ics` calendar file
→ Local HTTP server
→ Apple Calendar subscription

## Setup

Create a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -r requirements.txt
    python3 -m playwright install chromium

Run the sync script:

    python3 recstaff_sync.py

On the first run, the script opens a browser window. Log in to RecStaff, navigate to the schedule page, then return to Terminal and press Enter. The script saves the browser session locally so future runs can reuse it.

## Privacy note

This project is designed for personal schedule automation. It uses the user's own authenticated session and does not bypass login or access control.

Private files such as `state.json`, `schedule_url.txt`, logs, and generated `.ics` files should not be committed to GitHub.
