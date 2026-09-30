# PocketKid

# Introduction

PocketKid is a mobile-first family ledger for keeping a shared tally of money
parents and children owe one another. Each child has a signed account balance
and a chronological history of entries; a negative balance is a normal ledger
state, not an invalid wallet condition.

Fork repository: https://github.com/nocona71/pocketkid

Upstream project: https://github.com/pernastefano/pocketkid

Parents and children access the same app with role-based features:
- Children can propose reward, credit, and debit entries for their own account.
- Parents can approve/reject proposals, set per-child minimum balances, choose the ledger currency and date display format, record direct or recurring entries, manage users, and review full history.
- Transaction creation and approval actors are retained as identity snapshots, even if the user account is later removed.

The signed balance is expressed from the child's perspective: a positive value
is owed or credited to the child, zero is settled, and a negative value is owed
by the child to the family. See the [family-ledger product decision](docs/decisions/0002-family-ledger-product-model.md)
for the preferred terminology and compatibility boundaries.

The app is installable as a Progressive Web App (PWA) and supports real Web Push notifications (VAPID) for system-level alerts.

## Screens

<p>
  <a href="screens/parent-dashboard.png"><img src="screens/parent-dashboard.png" alt="Parent Dashboard" width="240"></a>
  <a href="screens/challenge-config.png"><img src="screens/challenge-config.png" alt="Challenge Configuration" width="240"></a>
  <a href="screens/parent-deposit.png"><img src="screens/parent-deposit.png" alt="Parent credit entry" width="240"></a>
</p>
<p>
  <a href="screens/recurring-config.png"><img src="screens/recurring-config.png" alt="Recurring Configuration" width="240"></a>
  <a href="screens/child-dashboard.png"><img src="screens/child-dashboard.png" alt="Child Dashboard" width="240"></a>
  <a href="screens/child-request.png"><img src="screens/child-request.png" alt="Child Request" width="240"></a>
</p>

---

# Stack

PocketKid uses a simple, production-friendly stack:

- **Backend**: Python + Flask
  - Server-side rendered pages
  - Session-based authentication
  - Role-based access (parent/child)
  - Production container runtime via Gunicorn
- **Database**: SQLite (local file under `data/`)
- **ORM**: Flask-SQLAlchemy
- **Frontend**:
  - Jinja templates
  - Custom CSS (mobile-first layout)
  - Vanilla JavaScript for dynamic UI, polling, auto-refresh, and push registration
- **PWA Layer**:
  - Web App Manifest
  - Service Worker (offline static caching + push event handling)
- **Notifications**:
  - In-app notifications
  - Real Web Push (VAPID) via `pywebpush`
- **Containerization**:
  - Docker + Docker Compose
- **Internationalization (i18n)**:
  - English, Italian, and German locale files
  - Per-user preferred language setting

---

# Local Run

## Prerequisites
- Python 3.12+
- `pip`

## Steps
```bash
cp .env.example .env
# edit .env with VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY (or VAPID_PRIVATE_KEY_B64)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:
- `http://localhost:8000`

## First Boot Behavior
- No demo users are auto-created.
- The app opens the setup screen to create the first parent account.
- You can optionally create the first child during setup.

---

# Run with Docker

## Build image
```bash
docker build -t pocketkid .
```

## Run container
Before running, provide VAPID keys via environment variables:

```bash
cp .env.example .env
# edit .env with real VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY (or VAPID_PRIVATE_KEY_B64)
```

```bash
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  pocketkid
```

Open:
- `http://localhost:8000`

---

# Run with Docker Compose

Prepare env file first:
```bash
cp .env.example .env
# edit .env with real VAPID keys
# optional: set host user/group for container process
# PUID=1000
# PGID=1000
# optional: pin a published fork image, for example 0.1.0
# POCKETKID_IMAGE_TAG=0.1.0
```

```bash
docker compose up -d --build
```

The default compose file:
- maps port `8000`
- persists app data in `./data`
- restarts container automatically (`unless-stopped`)
- supports optional `PUID`/`PGID` to run the container as a specific host UID/GID (default `1000:1000`)

---

# Releases

This fork uses an independent semantic version from the upstream project. The
current fork version is stored in `VERSION`, and release tags use the form
`fork-v<version>`.

See [`docs/RELEASING.md`](docs/RELEASING.md) for the tested GitHub Release and
GHCR publishing process.

---

# Main Features and How It Works

## Roles

### Parent
- Manage children (create/delete with double confirmation)
- Manage other parents (create/delete with safety constraints)
- Configure challenges with predefined reward amounts
- Review and approve/reject proposed child entries
- Record direct credit and debit entries
- Create recurring entries with configurable frequency:
  - daily
  - weekly
  - biweekly
  - monthly
- Reset child passwords
- Configure the ledger currency and family-wide date display format
- Configure personal language and password

### Child
- View their signed balance and ledger history with the resulting balance after each entry
- Submit reward request (linked to configured challenge)
- Propose debit and credit entries
- Change personal language and password

## Proposed Entry Workflow
1. Child proposes a reward, credit, or debit entry.
2. Parent receives notification and sees pending request.
3. Parent approves or rejects:
   - **Approve reward/credit** → the signed account balance increases.
   - **Approve debit** → the balance decreases down to the configured minimum and may become negative.
   - **Reject** → request state updates to rejected.
4. An approved entry is saved in ledger history and notifications are generated.

## Notifications and Auto-Refresh
- In-app notifications are available in the top-right mail icon.
- System notifications are sent via Web Push when supported.
- Pages auto-refresh on incoming events to keep dashboards synchronized without manual actions.

## PWA and Offline Behavior
- Static assets are cached by the Service Worker.
- Navigation is network-first to avoid stale pages after submit/approval actions.

---

# SSL Configuration

HTTPS is required for full PWA + Push behavior in real devices/environments (except localhost during development).

## Why SSL is required
- Service Worker reliability in production
- Web Push delivery on iOS/Android/browser
- Proper installability and secure context

## Recommended production setup
Use a reverse proxy with TLS termination (Nginx/Caddy/Traefik) in front of the Flask app/container.

Example architecture:
- `https://your-domain` → reverse proxy (TLS certificate)
- proxy forwards to PocketKid (Gunicorn) on internal port `8000`

## VAPID keys (environment-based)
PocketKid reads VAPID keys from environment variables:
- `VAPID_PUBLIC_KEY` (required)
- `VAPID_PRIVATE_KEY` (required if `VAPID_PRIVATE_KEY_B64` is not set)
- `VAPID_PRIVATE_KEY_B64` (optional alternative to `VAPID_PRIVATE_KEY`)
- `VAPID_SUBJECT` (optional, default: `mailto:pocketkid@example.com`)

For Docker, set these in `.env` and load them via `--env-file` or Docker Compose.

### Generate VAPID keys (recommended)

Run from the project root after creating the virtual environment:

```bash
source .venv/bin/activate
python - <<'PY'
import base64
from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

v = Vapid()
v.generate_keys()

public_bytes = v.public_key.public_bytes(
  encoding=Encoding.X962,
  format=PublicFormat.UncompressedPoint,
)
public_key = base64.urlsafe_b64encode(public_bytes).decode().rstrip('=')
private_key = v.private_pem().decode('utf-8').replace('\n', '\\n')

print(f"VAPID_PUBLIC_KEY={public_key}")
print(f"VAPID_PRIVATE_KEY={private_key}")
print("VAPID_SUBJECT=mailto:pocketkid@example.com")
PY
```

Copy the output lines into your `.env` file.

### Alternative: generate PEM files with `py_vapid` CLI

```bash
source .venv/bin/activate
python -m py_vapid --gen
python -m py_vapid --applicationServerKey -k private_key.pem
```

- Use the `Application Server Key` value as `VAPID_PUBLIC_KEY`.
- Put the full PEM private key into `VAPID_PRIVATE_KEY` using escaped newlines (`\n`), or encode it to base64 and use `VAPID_PRIVATE_KEY_B64`.

### Generate VAPID keys when running with Docker

You can generate keys inside the same Docker image used by the app.

```bash
docker compose run --rm pocketkid python - <<'PY'
import base64
from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

v = Vapid()
v.generate_keys()

public_bytes = v.public_key.public_bytes(
  encoding=Encoding.X962,
  format=PublicFormat.UncompressedPoint,
)
public_key = base64.urlsafe_b64encode(public_bytes).decode().rstrip('=')
private_key = v.private_pem().decode('utf-8').replace('\n', '\\n')

print(f"VAPID_PUBLIC_KEY={public_key}")
print(f"VAPID_PRIVATE_KEY={private_key}")
print("VAPID_SUBJECT=mailto:pocketkid@example.com")
PY
```

Then paste these lines into `.env` and restart:

```bash
docker compose up -d --build
```

### Local helper script

PocketKid includes a helper script to generate `.env`-ready VAPID values:

```bash
source .venv/bin/activate
python scripts/generate_vapid.py
```

Optional subject:

```bash
python scripts/generate_vapid.py --subject mailto:admin@example.com
```

Write directly to `.env`:

```bash
python scripts/generate_vapid.py --write-env
```

Custom env file:

```bash
python scripts/generate_vapid.py --write-env --env-file .env.production
```

---

# Install PWA on iOS and Android

## iOS (Safari)
1. Open the app URL in Safari.
2. Tap **Share**.
3. Tap **Add to Home Screen**.
4. Confirm installation.

Notes:
- Push notifications on iOS require HTTPS and supported iOS versions.
- User must allow notification permissions.

## Android (Chrome/Edge)
1. Open the app URL.
2. Tap browser menu.
3. Tap **Install app** / **Add to Home screen**.
4. Confirm installation.

Notes:
- Push notifications require HTTPS in production.
- User must grant notification permission.

---

## Project Structure (Quick Reference)
- `app.py` → minimal application entrypoint
- `pocketkid/config.py` → configuration and paths
- `pocketkid/extensions.py` → shared extensions (SQLAlchemy)
- `pocketkid/models.py` → database models
- `pocketkid/services.py` → support/business utilities (auth helpers, i18n, push, recurring)
- `pocketkid/routes.py` → HTTP routes
- `pocketkid/__init__.py` → app factory and bootstrap
- `templates/` → UI views
- `static/` → CSS, JS, Service Worker, manifest, icons
- `locales/` → i18n files (`en.json`, `it.json`)
- `data/` → SQLite DB
- `.env.example` → template for VAPID environment variables
- `VERSION` → fork release version
- `docs/decisions/0002-family-ledger-product-model.md` → product model and terminology
- `docs/RELEASING.md` → release and container publishing process
- `Dockerfile`, `docker-compose.yml` → container setup

---

## Credits
Stefano Perna

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.
