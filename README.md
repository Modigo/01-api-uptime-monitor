# API Uptime Monitor

A small service that periodically checks registered URLs, measures how fast they respond, and keeps an outage history so you can see when a site went down and for how long.

Built by a five-person team as a Learn2Earn project (Backend & APIs, advanced beginner).

> **Status:** MVP in progress. Items marked **TODO** are waiting on the team and must be filled in before the final demo.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Team and responsibilities](#team-and-responsibilities)
3. [How it works](#how-it-works)
4. [Project structure](#project-structure)
5. [Setup](#setup)
6. [Environment variables](#environment-variables)
7. [Running the app](#running-the-app)
8. [API endpoints](#api-endpoints)
9. [Data model](#data-model)
10. [Check results and error types](#check-results-and-error-types)
11. [Testing](#testing)
12. [Deployment](#deployment)
13. [Git workflow](#git-workflow)
14. [Known limitations](#known-limitations)
15. [Demo script](#demo-script)
16. [Next improvements](#next-improvements)

---

## What it does

- Users register URLs to monitor.
- A background worker checks every registered URL on a fixed interval.
- Each check records whether the site answered, the HTTP status code, and the response time in milliseconds.
- Failed checks are classified (timeout, DNS failure, TLS error, HTTP error, and so on).
- A dashboard shows the current status of each URL, response-time history, and outage history.

## Team and responsibilities

| Team member | Responsibility |
|---|---|
| Chidom Nwoke | Scheduler and monitoring worker |
| Togenu Precious | Backend API with FastAPI |
| Lemmy MG | Database and persistence |
| David Nwaigwe | React dashboard and frontend/backend integration |
| Boma | Testing, QA, deployment coordination, and documentation |

## How it works

```
 Scheduler / worker  --->  checker  --->  result dictionary
        |                                        |
        |                                        v
        |                                  Database (saves each result)
        |                                        ^
        v                                        |
   repeats every N seconds               FastAPI backend (reads and serves data)
                                                 |
                                                 v
                                         React dashboard
```

1. **Scheduler** gets the list of URLs and runs `check_url(url)` on all of them at the same time, then hands each result to a save function. One failing check never stops the cycle.
2. **Checker** sends an HTTP GET request, measures the time, and always returns a dictionary with the same keys, whether the site answered or not.
3. **Database** stores every result so outage history can be built.
4. **API** lets the frontend add and list URLs and read results.
5. **Dashboard** displays status and history.

The checker does not know about the database, and the scheduler does not know about the API. Each part only talks to the next through plain function calls and dictionaries, so they can be built and tested separately.

## Project structure

**TODO:** update this to match the merged scaffold.

```
API-Uptime-Monitor/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI app, /health endpoint
│       ├── checker.py       # check_url(): checks one URL (no database code)
│       ├── scheduler.py     # runs checks on a schedule
│       └── database.py      # saving and reading results  (TODO: confirm file name)
├── frontend/                # React dashboard
├── tests/                   # pytest tests
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Setup

### Requirements

- Python 3.11 or newer (the project has been run on 3.14)
- Git
- Node.js (for the frontend) **TODO: confirm version**

### Backend

```bash
git clone <repo-url>
cd API-Uptime-Monitor

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

The `(.venv)` marker at the start of your terminal prompt means the virtual environment is active. Reactivate it with `source .venv/bin/activate` every time you open a new terminal.

**TODO:** confirm `requirements.txt` lists at least `requests`, `fastapi`, `uvicorn`, `python-dotenv` and `supabase`.

### Frontend

**TODO (David):** add the install and start commands, for example:

```bash
cd frontend
npm install
npm run dev
```

## Environment variables

Copy the template and fill it in:

```bash
cp .env.example .env
```

Never commit `.env`. It is listed in `.gitignore`. Only `.env.example` is committed, and it must contain placeholders only, never real keys.

**TODO:** each owner confirms the real names. The two Supabase names below are the ones used in the current database code.

| Variable | Used by | Description |
|---|---|---|
| `SUPABASE_URL` | Database, API, scheduler | Address of the Supabase project |
| `SUPABASE_KEY` | Database, API, scheduler | Secret key for the Supabase project. **Server side only.** Never put it in the frontend, in a commit, or in chat |
| `CHECK_INTERVAL_SECONDS` | Scheduler | Seconds between check cycles (proposal, default 60) |
| `VITE_API_BASE_URL` | Frontend | Address of the backend API (proposal) |

If the Supabase keys are missing, the database code should fail with a clear message when it is first used, and not when the file is imported.

## Running the app

**TODO:** confirm commands with the scheduler and API owners.

```bash
# Backend API
uvicorn backend.app.main:app --reload

# Scheduler on its own (demo mode)
python backend/app/scheduler.py

# Checker on its own (runs a few sample URLs)
python backend/app/checker.py
```

Check that the API is alive: open `http://localhost:8000/health`.

FastAPI also generates interactive documentation at `http://localhost:8000/docs`, where every endpoint can be tried from the browser.

## API endpoints

**TODO (Precious):** replace with the approved API contract. Proposed shape:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Is the API running? |
| POST | `/monitors` | Register a URL to monitor |
| GET | `/monitors` | List monitored URLs with current status |
| DELETE | `/monitors/{id}` | Stop monitoring a URL |
| GET | `/monitors/{id}/checks` | Check history for one URL |
| GET | `/monitors/{id}/incidents` | Outage history for one URL |

## Data model

**TODO (Lemmy):** confirm this matches the real Supabase tables. These names come from the current database code.

**monitored_urls**

| Column | Description |
|---|---|
| id | Unique identifier |
| url | The address being monitored |
| is_active | Whether the scheduler should check it |

**check_results** (one row per check)

| Column | Description |
|---|---|
| url_id | Which monitored URL this check belongs to (links to `monitored_urls.id`) |
| checked_at | UTC timestamp |
| is_success | True if the site answered with a status below 400 |
| status_code | HTTP status code, empty if nothing answered |
| response_time_ms | Time taken in milliseconds, empty if nothing answered |
| error_type | Category of failure, empty on success |
| error_message | Short human-readable message, empty on success |

The checker's `status` field (`UP` or `DOWN`) is not stored, because it can be worked out from `is_success`. The checker's `error` field is stored as `error_message`.

An **incident** is a run of consecutive failed checks, from the first failure to the next success. **TODO:** decide whether incidents are calculated when read, or stored in their own table.

**TODO (Lemmy):** a unique constraint on `monitored_urls.url`, so the same address cannot be added twice.

## Check results and error types

`check_url(url)` always returns a dictionary with the same keys. It never raises an error to the caller.

```python
{
    "url": "https://example.com",
    "is_success": True,
    "status": "UP",                        # "UP" or "DOWN"
    "status_code": 200,                    # None if nothing answered
    "response_time_ms": 182,               # None if nothing answered
    "checked_at": "2026-10-20T15:09:22Z",  # UTC
    "error_type": None,                    # see table below
    "error": None
}
```

**Rule:** a status code below 400 is `UP`. A code of 400 or above, or no answer at all, is `DOWN`.

| `error_type` | Meaning |
|---|---|
| `timeout` | The site took longer than the timeout (5 seconds) |
| `dns` | The hostname could not be resolved |
| `tls` | Certificate or secure-connection error |
| `http_error` | The site answered with a status of 400 or above |
| `connection` | A connection could not be made (server off, refused) |
| `blocked` | The URL points to a private or internal address and was refused |
| `invalid_url` | Not an `http` or `https` URL, no hostname, an invalid port, or credentials inside the URL |
| `redirect_limit` | More than 3 redirects |
| `request_error` | Any other error from the HTTP library, or a redirect with no destination |
| `internal_error` | The check itself crashed (reported by the scheduler) |

### Security checks built into the checker

- Only `http` and `https` URLs are allowed, and URLs containing a username or password are refused.
- The hostname is looked up **once** per request. Every address returned is checked, and the URL is refused if any of them is private, loopback, link-local or multicast (for example `localhost`, `127.0.0.1`, `169.254.169.254`).
- The request is then sent to **that exact validated address**, with the original hostname kept for the `Host` header and the TLS certificate check. This closes the DNS rebinding gap: a second lookup never happens, so a hostile DNS server cannot swap in an internal address.
- Redirects are followed manually, at most 3, and every redirect target goes through the same lookup and checks.
- Proxy settings from the environment are ignored, because a proxy would do its own lookup and bypass the pinning.
- All timestamps are UTC.

## Testing

**TODO (Boma):** automated tests are being written. The brief requires the happy path and at least one important failure path.

```bash
pip install pytest
pytest
```

Planned coverage:

- **Checker:** site up, HTTP error (404), timeout, DNS failure, blocked address, invalid URL. Tests use fake responses so they do not depend on the internet.
- **Scheduler:** one crashing check does not stop the cycle.
- **API:** adding a URL, listing URLs, rejecting an invalid URL.
- **Integration (manual QA):** register a URL, wait one cycle, confirm the dashboard shows it. Register a made-up URL and confirm it shows DOWN with a `dns` error.

### Manual checker results

Results from running `python checker.py` against live addresses (response times depend on the tester's connection and are not fixed):

| URL | Expected `status` | Expected `error_type` | Result |
|---|---|---|---|
| `https://www.google.com` | UP | none | Matched |
| `http://github.com` (redirects to HTTPS) | UP | none | Matched |
| `https://github.com/this-page-is-fake-12345` | DOWN | `http_error` (404) | Matched |
| `https://this-site-does-not-exist-12345.com` | DOWN | `dns` | Matched |
| `https://expired.badssl.com` | DOWN | `tls` | Matched |
| `http://localhost:8000` | DOWN | `blocked` | Matched |
| `http://127.0.0.1` | DOWN | `blocked` | Matched |
| `http://169.254.169.254` | DOWN | `blocked` | Matched |
| `ftp://example.com` | DOWN | `invalid_url` | Matched |

**TODO (Boma):** re-run this table against the final merged checker (with IP pinning) and note any differences.

A `dns` result means the name could not be resolved. It does not prove the domain never existed: the same result appears when the tester's own internet connection is down.

## Deployment

**TODO:** the team has not chosen a host yet. Options from the project brief:

- Backend: Render, Railway or Fly.io
- Database: Supabase (already used by the database code), Neon, or SQLite for a simple MVP
- Frontend: Vercel, Netlify or GitHub Pages

Before deploying, check that:

- [ ] All environment variables are set on the host, including `SUPABASE_URL` and `SUPABASE_KEY`
- [ ] The Supabase tables exist and the key has the access the app needs
- [ ] Seed data (a few sample URLs, including one that is down) is loaded for the demo
- [ ] The deployed `/health` endpoint responds
- [ ] The frontend points at the deployed API address
- [ ] No secret appears in the repository, including its history

Deployed URL: **TODO**

## Git workflow

1. `main` is the shared branch. Do not push directly to it.
2. Each person works on their own branch, for example `feat/scheduler`, `feat/api-monitors`, `feat/db-models`, `feat/dashboard`, `feat/tests-docs`.
3. Push your branch and open a pull request.
4. The team reviews and merges approved pull requests into `main`.
5. After a merge, everyone updates with `git checkout main` then `git pull`.
6. Keep pull requests small, and never commit `.venv`, `.env` or `node_modules`.

## Known limitations

These are honest limits of the current MVP, and they should be said out loud in the demo.

- **False outages on slow connections.** Each URL is checked once per cycle. A slow connection can cause a timeout that is reported as DOWN. Re-checking a failed URL before declaring an outage would reduce this.
- **Response time includes a safety lookup.** The measured time includes the hostname lookup and validation done before the request, so it is slightly longer than the site's own response time.
- **Only the first address is tried.** If a hostname returns several addresses, the checker connects to the first validated one and does not fall back to the others.
- **Rule for DOWN.** Any status of 400 or above counts as DOWN, even when the site itself is reachable (for example a missing page).
- **`dns` is not proof a domain does not exist.** It also appears when the checking machine has no working DNS.
- **HTTP library.** The checker uses `requests`. The project brief mentions HTTPX, and the team has not decided whether to switch.
- **Network-level protection.** The checker blocks internal addresses itself. If the app is deployed for untrusted users, outgoing connections to private ranges should also be blocked at the host or firewall level, and the server should hold no unnecessary cloud credentials.

## Demo script

**TODO:** adjust once the app is deployed. A suggested flow of about five minutes:

1. **The problem (30 seconds).** Websites go down, and nobody notices until a user complains.
2. **Architecture (1 minute).** Show the diagram above: scheduler, checker, database, API, dashboard.
3. **Live flow (2 minutes).** Register a working URL and a broken URL. Wait for a check cycle. Show the dashboard: one UP, one DOWN with its error type and the outage history.
4. **Decisions and trade-offs (1 minute).** Checks run in parallel so a slow site does not delay the others. Failed checks return the same shape as successful ones so no part of the system needs special cases. The checker blocks internal addresses and connects only to the address it validated.
5. **Limits and next steps (30 seconds).** The known limitations above and the improvements below.

## Next improvements

- Re-check failed URLs before opening an incident, to avoid false outages
- Authentication and per-user monitors
- Notifications (email or chat message) when a site goes down
- Uptime percentage and average response time per monitor
- Network-level blocking of private ranges on the deployment host
- More tests and monitoring of the monitor itself