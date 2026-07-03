import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, date, time
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright
from icalendar import Calendar, Event

BASE_URL = "https://app.recstaff.com/"
STATE_FILE = Path("state.json")
SCHEDULE_URL_FILE = Path("schedule_url.txt")
OUTPUT_ICS = Path("work_schedule.ics")

MONTH_SELECT = "select#selectGridMonth"
DAY_CELLS = "td.clickable.day"
SHIFT_ANCHORS = "a"

TIMEZONE = ZoneInfo("America/Vancouver")

TIME_RANGE_RE = re.compile(
    r"(?P<start>\d{1,2}(?::\d{2})?\s*[ap])\s*-\s*(?P<end>\d{1,2}(?::\d{2})?\s*[ap])",
    re.IGNORECASE,
)

WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def parse_time_token(token: str) -> time:
    token = token.strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?([ap])", token)
    if not m:
        raise ValueError(f"Could not parse time token: {token!r}")

    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = m.group(3)

    if hour == 12:
        hour = 0
    if meridiem == "p":
        hour += 12

    return time(hour=hour, minute=minute)


def selected_month_label(page) -> str:
    return normalize_text(
        page.locator(f"{MONTH_SELECT} option:checked").inner_text()
    )


def month_options(page) -> list[dict]:
    return page.locator(f"{MONTH_SELECT} option").evaluate_all(
        """
        options => options
            .map(o => ({ value: o.value, label: (o.textContent || "").trim() }))
            .filter(o => o.label.length > 0)
        """
    )


def month_grid_start(year: int, month: int) -> date:
    first = date(year, month, 1)
    # Python weekday: Monday=0 ... Sunday=6
    # Calendar grid starts Sunday, so convert to Sunday-based offset.
    sunday_based_offset = (first.weekday() + 1) % 7
    return first - timedelta(days=sunday_based_offset)


def summary_from_parts(start_token: str, end_token: str, rest: str) -> str:
    rest = rest.strip(" ,;-")

    code = "Shift"
    if rest:
        first_chunk = rest.split(",", 1)[0].strip()
        if first_chunk:
            code = first_chunk

    start_token = start_token.replace(" ", "")
    end_token = end_token.replace(" ", "")

    return f"{code} {start_token}-{end_token}"

def make_uid(start_dt: datetime, end_dt: datetime, description: str) -> str:
    raw = f"{start_dt.isoformat()}|{end_dt.isoformat()}|{description}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{digest}@recstaff-sync"


def scrape_current_month(page) -> list[dict]:
    label = selected_month_label(page)
    try:
        month_start = datetime.strptime(label, "%B %Y").date()
    except ValueError as exc:
        raise RuntimeError(f"Could not parse selected month label: {label!r}") from exc

    grid_start = month_grid_start(month_start.year, month_start.month)

    day_cells = page.locator(DAY_CELLS)
    day_count = day_cells.count()

    events = []

    for cell_index in range(day_count):
        cell = day_cells.nth(cell_index)
        cell_date = grid_start + timedelta(days=cell_index)

        anchors = cell.locator(SHIFT_ANCHORS)
        anchor_count = anchors.count()

        for shift_index in range(anchor_count):
            anchor = anchors.nth(shift_index)
            text = normalize_text(anchor.inner_text())

            if not text:
                continue

            m = TIME_RANGE_RE.search(text)
            if not m:
                continue

            start_token = m.group("start")
            end_token = m.group("end")

            start_t = parse_time_token(start_token)
            end_t = parse_time_token(end_token)

            start_dt = datetime.combine(cell_date, start_t, TIMEZONE)
            end_dt = datetime.combine(cell_date, end_t, TIMEZONE)

            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            rest = normalize_text(text[m.end():]).strip(" ,;-")
            summary = summary_from_parts(start_token, end_token, rest)
            description = text

            uid = make_uid(start_dt, end_dt, description)

            events.append(
                {
                    "uid": uid,
                    "summary": summary,
                    "description": description,
                    "start": start_dt,
                    "end": end_dt,
                }
            )

    return events

def wait_for_month_change(page, old_label: str, timeout_ms: int = 5000) -> None:
    page.wait_for_function(
        """({selector, oldLabel}) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            const selected = el.options[el.selectedIndex];
            return selected && selected.textContent.trim() !== oldLabel;
        }""",
        arg={"selector": MONTH_SELECT, "oldLabel": old_label},
        timeout=timeout_ms,
    )
    page.wait_for_timeout(800)


def select_month(page, value: str, label: str) -> None:
    current_value = page.locator(MONTH_SELECT).input_value()
    current_label = selected_month_label(page)

    if current_value == value and current_label == label:
        return

    page.select_option(MONTH_SELECT, value=value)
    wait_for_month_change(page, current_label)


def build_ics(events: list[dict], output_path: Path) -> None:
    cal = Calendar()
    cal.add("prodid", "-//RecStaff Sync//")
    cal.add("version", "2.0")

    now = datetime.now(TIMEZONE)

    for item in sorted(events, key=lambda e: e["start"]):
        ev = Event()
        ev.add("uid", item["uid"])
        ev.add("summary", item["summary"])
        ev.add("description", item["description"])
        ev.add("dtstart", item["start"])
        ev.add("dtend", item["end"])
        ev.add("dtstamp", now)
        cal.add_component(ev)

    output_path.write_bytes(cal.to_ical())


def ensure_session_and_schedule_url(playwright) -> str:
    need_login = not STATE_FILE.exists() or not SCHEDULE_URL_FILE.exists()

    if not need_login:
        return SCHEDULE_URL_FILE.read_text(encoding="utf-8").strip()

    print("No saved session found.")
    print("A browser window will open.")
    print("Log in to RecStaff and navigate to your schedule page.")
    print("When the schedule is fully visible, come back here and press Enter.")
    input()

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE_URL)

    print("Finish logging in and open your schedule page now.")
    print("Then press Enter in this terminal.")
    input()

    page.wait_for_selector(MONTH_SELECT, timeout=45000)

    context.storage_state(path=str(STATE_FILE))
    schedule_url = page.url
    SCHEDULE_URL_FILE.write_text(schedule_url, encoding="utf-8")

    print(f"Saved session to {STATE_FILE}")
    print(f"Saved schedule URL to {SCHEDULE_URL_FILE}: {schedule_url}")

    browser.close()
    return schedule_url


def main() -> None:
    with sync_playwright() as p:
        schedule_url = ensure_session_and_schedule_url(p)

        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(STATE_FILE))
        page = context.new_page()
        page.goto(schedule_url)

        page.wait_for_selector(MONTH_SELECT, timeout=45000)
        page.wait_for_selector(DAY_CELLS, timeout=45000)
        page.wait_for_timeout(1000)

        options = month_options(page)
        if not options:
            raise RuntimeError("No month options found in #selectGridMonth")

        deduped: dict[str, dict] = {}

        for option in options:
            value = option["value"]
            label = option["label"]

            print(f"Scraping {label} ...")
            select_month(page, value, label)
            month_events = scrape_current_month(page)

            for ev in month_events:
                deduped[ev["uid"]] = ev

        events = list(deduped.values())
        build_ics(events, OUTPUT_ICS)

        print(f"Done. Wrote {len(events)} unique events to {OUTPUT_ICS.resolve()}")

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
