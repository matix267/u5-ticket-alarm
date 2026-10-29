#!/usr/bin/env python3
"""Prüft die Verfügbarkeit der U5-Tunneltour (pretix) und schickt bei freien
Tickets eine Push-Nachricht über ntfy.sh ans iPhone."""
import datetime
import json
import os
import sys
import time
import urllib.request

EVENT_URL = "https://pretix.eu/u5/begehung/"
API_URL = EVENT_URL + "widget/product_list?lang=de"
LAST_DAY = datetime.date(2026, 11, 14)


def fetch_events():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "u5-ticket-alarm"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("events", [])


def is_free(event):
    avail = event.get("availability") or {}
    return avail.get("color") != "red" and avail.get("reason") not in ("full", "soldout")


def notify(topic, title, message, click_url):
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": "urgent", "Tags": "ticket,metro", "Click": click_url},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30).read()


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def check_once(topic, last_free):
    events = fetch_events()
    free = [e for e in events if is_free(e)]
    free_ids = tuple(e.get("subevent") for e in free)
    if not free:
        print(f"{now()} Nichts frei.")
        return ()
    if free_ids == last_free:
        print(f"{now()} Weiterhin frei: {len(free)} Zeitfenster (schon gemeldet).")
        return free_ids
    first = free[0]
    url = f"{EVENT_URL}{first.get('subevent')}/" if first.get("subevent") else EVENT_URL
    lines = [f"{e.get('date_range')}: {(e.get('availability') or {}).get('text', 'frei')}" for e in free]
    notify(topic, "U5-Tunneltour: Tickets frei!", "Jetzt schnell buchen:\n" + "\n".join(lines), url)
    print(f"{now()} Benachrichtigung gesendet ({len(free)} Zeitfenster frei).")
    return free_ids


def main():
    if datetime.date.today() > LAST_DAY:
        print("Veranstaltung ist vorbei - nichts zu tun.")
        return 0
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("Fehler: NTFY_TOPIC ist nicht gesetzt.", file=sys.stderr)
        return 1
    duration = int(os.environ.get("CHECK_DURATION_SEC", "0"))
    interval = int(os.environ.get("CHECK_INTERVAL_SEC", "30"))
    deadline = time.monotonic() + duration
    last_free = None
    while True:
        try:
            last_free = check_once(topic, last_free)
        except Exception as exc:
            print(f"{now()} Fehler: {exc}", file=sys.stderr)
        if time.monotonic() + interval > deadline:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
