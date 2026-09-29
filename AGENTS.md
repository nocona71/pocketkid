# PocketKid fork

This repository is a fork of `pernastefano/pocketkid`.

## Project goal

Adapt PocketKid into a lightweight family ledger.

The application should support children having their own accounts and
allow balances to become positive or negative.

Parents should retain administrative control.

## Upstream compatibility

Keep divergence from upstream as small as reasonably possible.

- Preserve the existing architecture and coding style.
- Prefer small, isolated changes.
- Do not refactor unrelated code.
- Do not rename or move files without a concrete need.
- Prefer changes that remain easy to rebase onto upstream.
- Do not modify the upstream production Docker setup unless required.

## Existing architecture

PocketKid is a small Flask application using:

- Python 3.12
- Flask
- Flask-SQLAlchemy
- SQLite
- Jinja templates
- vanilla JavaScript
- Docker

Important application files include:

- `pocketkid/models.py` — database models
- `pocketkid/routes.py` — routes and request handling
- `pocketkid/services.py` — application/business logic
- `pocketkid/config.py` — configuration
- `templates/` — Jinja templates
- `static/` — frontend assets

## Development environment

Development is performed inside the VS Code Dev Container in
`.devcontainer/`.

Use the Python environment provided by the Dev Container.

Run PocketKid locally with:

    python app.py

The local development database is stored below `data/` and must never
be committed.

Secrets are stored in `.env` and must never be committed.

## Development rules

Before changing behavior:

1. Inspect the existing implementation.
2. Identify the relevant code path.
3. Prefer the smallest viable change.
4. Preserve existing authorization boundaries.
5. Add or update tests for behavioral changes where practical.
6. Run relevant tests or checks before declaring work complete.

Do not silently change unrelated behavior.

## Security

- Never commit secrets, VAPID private keys, passwords, or `.env`.
- Never use production data for development or testing.
- Treat authorization changes as security-sensitive.
- A child must not gain access to another child's account or transactions.

## Current product goals

The current direction is:

1. Allow account balances below zero.
2. Represent negative balances clearly as debt.
3. Preserve parent/child account isolation.
4. Allow children to view their own account.
5. Potentially allow children to create or edit their own transactions.
6. Add a reliable audit history for transaction changes.
7. Keep the application lightweight and mobile-friendly.

These goals describe direction, not permission to implement all of them
in one change.

## Git workflow

- Do not develop directly on `master`.
- Use one logical feature per branch.
- Keep commits small and focused.
- Do not rewrite shared history.
- Do not force-push.
- Do not create commits unless explicitly requested.
- Do not push unless explicitly requested.

## Working style for agents

For analysis requests, do not modify files unless explicitly asked.

When asked to implement something:

- explain the affected code path first when useful;
- keep the diff minimal;
- report files changed;
- report tests or checks run;
- mention unresolved risks or assumptions.