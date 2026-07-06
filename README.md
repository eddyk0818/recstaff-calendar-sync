# RecStaff Calendar Sync

A small Python tool I made to sync my RecStaff work schedule into Apple Calendar.

I work as a lifeguard/swim instructor, and I got tired of checking RecStaff manually or copying shifts into my calendar. RecStaff did not give me a calendar subscription link, so I made my own `.ics` feed.

## What it does

- Opens my RecStaff schedule using a saved browser session
- Scrapes visible shift times from the schedule page
- Converts shifts into `.ics` calendar events
- Lets Apple Calendar subscribe to the generated calendar file
- Avoids committing private login/session files

## Tech used

- Python
- Playwright
- iCalendar / `.ics`
- macOS LaunchAgents
- Local HTTP server

## What I learned

- Browser automation with Playwright
- Working with authenticated sessions
- Parsing dates and times from messy webpage text
- Generating calendar events
- Handling time zones and duplicate events

## Limitations

- This depends on the current RecStaff page layout, so it may break if the site changes.
- The first setup still requires manually logging in through a browser.
- It is currently tested only with my own schedule and Apple Calendar setup.

## Current status

This is mainly built for my own RecStaff setup. It may need changes to work for other accounts, workplaces, or schedule page layouts.
