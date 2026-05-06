#!/usr/bin/env python3
"""
Airfare drop monitor: SFO -> PVG, business and first class, 15-30 days out.

Polls the Amadeus Flight Offers Search API for the cheapest one-way fare in each
cabin class on each sampled departure date, compares against a rolling price
history, and sends an alert on a "big drop" via SMTP email and/or Twilio SMS.

Configuration is via environment variables (typically GitHub Actions secrets).
See tools/airfare-monitor/README.md for the full list.
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

ORIGIN = "SFO"
DESTINATION = "PVG"
CABIN_CLASSES = ("BUSINESS", "FIRST")
LOOKAHEAD_MIN_DAYS = 15
LOOKAHEAD_MAX_DAYS = 30
SAMPLE_STEP_DAYS = 3  # sample every Nth day in the window to stay under rate limits

# A drop must beat BOTH thresholds vs. the recent low to alert.
DROP_PCT_THRESHOLD = float(os.environ.get("DROP_PCT_THRESHOLD", "0.15"))   # 15%
DROP_ABS_THRESHOLD = float(os.environ.get("DROP_ABS_THRESHOLD", "300"))    # $300

HISTORY_PATH = Path(__file__).parent / "price_history.json"
HISTORY_RETENTION_DAYS = 60

AMADEUS_HOST = os.environ.get("AMADEUS_HOST", "https://test.api.amadeus.com")


@dataclass
class FareSample:
    cabin: str
    depart_date: str
    price: float
    currency: str
    carrier: str | None


def get_amadeus_token(client_id: str, client_secret: str) -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        f"{AMADEUS_HOST}/v1/security/oauth2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    return payload["access_token"]


def search_cheapest(token: str, depart_date: str, cabin: str) -> FareSample | None:
    params = urllib.parse.urlencode({
        "originLocationCode": ORIGIN,
        "destinationLocationCode": DESTINATION,
        "departureDate": depart_date,
        "adults": 1,
        "travelClass": cabin,
        "currencyCode": "USD",
        "max": 5,
        "nonStop": "false",
    })
    req = urllib.request.Request(
        f"{AMADEUS_HOST}/v2/shopping/flight-offers?{params}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # 400 from Amadeus often means "no offers for this combo"; treat as None.
        sys.stderr.write(f"  HTTP {e.code} for {depart_date} {cabin}: {e.read()[:200]!r}\n")
        return None

    offers = payload.get("data") or []
    if not offers:
        return None

    cheapest = min(offers, key=lambda o: float(o["price"]["grandTotal"]))
    carrier = None
    try:
        carrier = cheapest["itineraries"][0]["segments"][0]["carrierCode"]
    except (KeyError, IndexError):
        pass
    return FareSample(
        cabin=cabin,
        depart_date=depart_date,
        price=float(cheapest["price"]["grandTotal"]),
        currency=cheapest["price"].get("currency", "USD"),
        carrier=carrier,
    )


def collect_samples(token: str) -> list[FareSample]:
    today = date.today()
    samples: list[FareSample] = []
    days = list(range(LOOKAHEAD_MIN_DAYS, LOOKAHEAD_MAX_DAYS + 1, SAMPLE_STEP_DAYS))
    for offset in days:
        depart = (today + timedelta(days=offset)).isoformat()
        for cabin in CABIN_CLASSES:
            print(f"  Querying {depart} / {cabin} ...")
            sample = search_cheapest(token, depart, cabin)
            if sample:
                samples.append(sample)
    return samples


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {"observations": []}
    with HISTORY_PATH.open() as f:
        return json.load(f)


def save_history(history: dict) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    history["observations"] = [
        o for o in history.get("observations", []) if o["checked_at"] >= cutoff
    ]
    HISTORY_PATH.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n")


def detect_drops(history: dict, new_samples: list[FareSample]) -> list[dict]:
    """Compare each new sample against the prior minimum for the same (date, cabin)."""
    by_key: dict[tuple[str, str], list[float]] = {}
    for obs in history.get("observations", []):
        key = (obs["depart_date"], obs["cabin"])
        by_key.setdefault(key, []).append(obs["price"])

    drops = []
    for s in new_samples:
        key = (s.depart_date, s.cabin)
        prior_prices = by_key.get(key, [])
        if not prior_prices:
            continue
        prior_min = min(prior_prices)
        delta = prior_min - s.price
        pct = delta / prior_min if prior_min > 0 else 0
        if delta >= DROP_ABS_THRESHOLD and pct >= DROP_PCT_THRESHOLD:
            drops.append({
                "cabin": s.cabin,
                "depart_date": s.depart_date,
                "carrier": s.carrier,
                "new_price": s.price,
                "prior_min": prior_min,
                "delta": delta,
                "pct": pct,
            })
    return drops


def format_alert(drops: list[dict]) -> tuple[str, str, str]:
    lines = [f"Airfare drop alert: {ORIGIN} -> {DESTINATION}", ""]
    for d in drops:
        lines.append(
            f"  {d['depart_date']}  {d['cabin']:8s}  "
            f"${d['new_price']:.0f}  (was ${d['prior_min']:.0f}, "
            f"-${d['delta']:.0f} / -{d['pct']*100:.0f}%)"
            + (f"  [{d['carrier']}]" if d['carrier'] else "")
        )
    body = "\n".join(lines)
    subject = f"Fare drop: {ORIGIN}->{DESTINATION} {len(drops)} alert(s)"
    # SMS-friendly short version: cap at ~300 chars.
    short = " | ".join(
        f"{d['depart_date']} {d['cabin'][:3]} ${d['new_price']:.0f} (-${d['delta']:.0f})"
        for d in drops[:4]
    )
    sms = f"{ORIGIN}->{DESTINATION} drop: {short}"[:300]
    return subject, body, sms


def send_email(subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addr = os.environ.get("ALERT_EMAIL_TO", "huangq@gmail.com")
    from_addr = os.environ.get("SMTP_FROM", user)
    if not (host and user and password):
        return False
    port = int(os.environ.get("SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Email sent to {to_addr}")
    return True


def send_sms(text: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_num = os.environ.get("TWILIO_FROM_NUMBER")
    to_num = os.environ.get("ALERT_SMS_TO", "+14082193562")
    if not (sid and token and from_num):
        return False
    body = urllib.parse.urlencode({"From": from_num, "To": to_num, "Body": text}).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=body,
        method="POST",
    )
    auth = f"{sid}:{token}".encode()
    import base64
    req.add_header("Authorization", "Basic " + base64.b64encode(auth).decode())
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Twilio status {resp.status}: {resp.read()[:200]!r}")
    print(f"SMS sent to {to_num}")
    return True


def main() -> int:
    client_id = os.environ.get("AMADEUS_CLIENT_ID")
    client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
    if not (client_id and client_secret):
        sys.stderr.write("AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET must be set.\n")
        return 2

    print(f"Fetching Amadeus token from {AMADEUS_HOST} ...")
    token = get_amadeus_token(client_id, client_secret)

    print(f"Searching {ORIGIN}->{DESTINATION}, "
          f"{LOOKAHEAD_MIN_DAYS}-{LOOKAHEAD_MAX_DAYS} days ahead, "
          f"cabins={CABIN_CLASSES} ...")
    samples = collect_samples(token)
    print(f"Collected {len(samples)} fare samples.")

    history = load_history()
    drops = detect_drops(history, samples)

    now = datetime.now(timezone.utc).isoformat()
    for s in samples:
        history.setdefault("observations", []).append({
            "checked_at": now,
            "cabin": s.cabin,
            "depart_date": s.depart_date,
            "price": s.price,
            "currency": s.currency,
            "carrier": s.carrier,
        })
    save_history(history)

    if not drops:
        print("No qualifying drops detected.")
        return 0

    print(f"{len(drops)} drop(s) detected:")
    subject, body, sms = format_alert(drops)
    print(body)

    sent_email = sent_sms = False
    try:
        sent_email = send_email(subject, body)
    except Exception as e:
        sys.stderr.write(f"Email send failed: {e}\n")
    try:
        sent_sms = send_sms(sms)
    except Exception as e:
        sys.stderr.write(f"SMS send failed: {e}\n")

    if not (sent_email or sent_sms):
        sys.stderr.write(
            "WARNING: drops detected but no notification channel is configured.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
