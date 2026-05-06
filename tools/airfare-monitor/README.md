# Airfare monitor: SFO → PVG (business / first class)

A small utility that watches business- and first-class fares from **SFO → PVG**
for departures **15–30 days out**, and sends an alert when the cheapest
observed fare for a given (date, cabin) drops significantly versus its prior
recorded minimum.

The site itself is static (GitHub Pages), so everything here runs as a
**scheduled GitHub Actions workflow** — no server required.

---

## How it works

- `check_fares.py` queries the [Amadeus Flight Offers Search](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search) API for one-way flights on each sampled day in the 15–30 day window, in both `BUSINESS` and `FIRST` cabins.
- Each (date, cabin) cheapest fare is appended to `price_history.json`.
- A drop fires an alert only if it beats **both** thresholds vs. the prior minimum:
  - default `≥ 15%` cheaper, **and**
  - default `≥ $300` cheaper.
- Alerts are dispatched via SMTP email (default: `huangq@gmail.com`) and/or Twilio SMS (default: `+1 408-219-3562`). Either or both can be configured; if neither is configured, the workflow logs a warning.
- `.github/workflows/airfare-monitor.yml` runs the script daily at 14:00 UTC and commits the updated history back to the branch.

History is automatically trimmed to the last 60 days so the JSON file stays small.

---

## One-time setup

### 1. Get an Amadeus API key (free tier)

1. Sign up at <https://developers.amadeus.com/>.
2. Create a self-service app to get a **Client ID** and **Client Secret**.
3. The free "test" environment (`https://test.api.amadeus.com`) is enough to
   develop and verify; switch to `https://api.amadeus.com` once you've upgraded
   to a production app.

### 2. Add repo secrets

In **Settings → Secrets and variables → Actions**, add:

| Type        | Name                    | Value                                                |
| ----------- | ----------------------- | ---------------------------------------------------- |
| Secret      | `AMADEUS_CLIENT_ID`     | from Amadeus                                         |
| Secret      | `AMADEUS_CLIENT_SECRET` | from Amadeus                                         |
| Variable    | `AMADEUS_HOST`          | `https://api.amadeus.com` (only when using prod)     |

Email channel (optional but recommended):

| Type   | Name            | Notes                                                       |
| ------ | --------------- | ----------------------------------------------------------- |
| Secret | `SMTP_HOST`     | e.g. `smtp.gmail.com`                                       |
| Secret | `SMTP_PORT`     | typically `587`                                             |
| Secret | `SMTP_USER`     | sending account, e.g. a Gmail address                       |
| Secret | `SMTP_PASSWORD` | a Gmail **App Password**, not the account password          |
| Secret | `SMTP_FROM`     | optional; defaults to `SMTP_USER`                           |
| Variable | `ALERT_EMAIL_TO` | optional override; defaults to `huangq@gmail.com`         |

Gmail app password setup:
<https://support.google.com/accounts/answer/185833>

SMS channel (optional):

| Type   | Name                  | Notes                                          |
| ------ | --------------------- | ---------------------------------------------- |
| Secret | `TWILIO_ACCOUNT_SID`  | from <https://console.twilio.com/>             |
| Secret | `TWILIO_AUTH_TOKEN`   | from Twilio                                    |
| Secret | `TWILIO_FROM_NUMBER`  | a Twilio-owned number, E.164, e.g. `+15551234567` |
| Variable | `ALERT_SMS_TO`      | optional override; defaults to `+14082193562`  |

### 3. Tune thresholds (optional)

The defaults are 15% **and** $300. To change them permanently, edit the
`DROP_PCT_THRESHOLD` / `DROP_ABS_THRESHOLD` values in
`.github/workflows/airfare-monitor.yml`. To change them for a single run, use
the "Run workflow" button on the Actions tab — both thresholds are exposed as
manual inputs.

---

## Running locally

```bash
export AMADEUS_CLIENT_ID=...
export AMADEUS_CLIENT_SECRET=...
# Optional notification config:
export SMTP_HOST=smtp.gmail.com SMTP_PORT=587
export SMTP_USER=you@gmail.com SMTP_PASSWORD='app-password'
# export TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_FROM_NUMBER=+1...

python3 tools/airfare-monitor/check_fares.py
```

The script uses only the Python 3 standard library, so no `pip install` is
needed.

---

## Files

- `check_fares.py` — main script (Amadeus client, drop detection, SMTP + Twilio dispatch).
- `price_history.json` — rolling 60-day history of observed fares; committed back by the workflow.
- `../../.github/workflows/airfare-monitor.yml` — scheduled runner.

---

## Caveats

- Amadeus prices are indicative and may differ from what you see at booking time on the airline / OTA. Use this as an alerting trigger, then verify on the carrier's site.
- The free Amadeus test environment has limited inventory and rate limits. If you see no results for several dates in a row, switch to the production API.
- GitHub-scheduled workflows can be delayed or skipped during high load on the runner pool. If you need tighter SLAs, swap the cron for a self-hosted runner or move to a small cloud function.
