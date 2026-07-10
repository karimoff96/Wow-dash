# Reliability rollout runbook

This release is backward compatible, but migrations and operational canaries
must precede any destructive archive action or polling-to-webhook cutover.

## 1. Pre-deploy gates

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements-dev.txt
DJANGO_SETTINGS_MODULE=WowDash.settings_test venv/bin/python manage.py test
DJANGO_SETTINGS_MODULE=WowDash.settings_test venv/bin/python manage.py makemigrations --check --dry-run
DJANGO_SETTINGS_MODULE=WowDash.settings_production venv/bin/python manage.py check --deploy
```

CI repeats these checks with PostgreSQL 16 and Redis 7. Outbound test DNS and
network connections are rejected except loopback PostgreSQL/Redis connections.
The current legacy-monolith coverage ratchet is 28%; payment, archive deletion,
webhook idempotency, and the shared tenant boundary are gated at 90%, while the
workflow service is gated at 80%. Keep these critical-path gates at or above
their current thresholds before expanding production feature flags.

## 2. Service account and permissions

Create a dedicated `wowdash` system account. It needs read access to the
application and environment file, read/write access only to `media/`, `logs/`,
`run/`, and `backups/`, and no interactive shell. Keep `.env` mode `0640` and
place the service account in its owning group. Copy `deployment/wowdash.conf`
only after adjusting paths and creating `/var/log/wowdash` with mode `0750`.

Install the database/media backup units from `deployment/`, then enable their
timers. Database backups require `BACKUP_ENCRYPTION_PASSWORD` and a private
`PLATFORM_BACKUP_CHANNEL_ID`; never reuse customer archive channels.

## 3. Database and workers

```bash
venv/bin/python manage.py migrate --plan
venv/bin/python manage.py migrate
venv/bin/python manage.py check
```

The fixed process layout is one Gunicorn service, one default/broadcast Celery
worker, one Telegram worker, one single-concurrency maintenance worker, and one
Beat scheduler. Center count no longer changes process count. The existing
polling manager remains a per-center rollback path during the 30-day soak.

## 4. Archive rollout

Follow `docs/ARCHIVE_ROLLOUT.md`. The scheduled default is `inventory`; it never
uploads or deletes. Subscription expiry disables customer bot/Mini App behavior
but does not disable a center's `maintenance_archive_enabled` permission.
Never set `ARCHIVE_OPERATION_MODE=live` until a canary ZIP has been downloaded,
checksum-checked, restored in isolation, and recorded. Disk alerts trigger at
70%, 80%, and 90%.

## 5. Webhook canary and rollback

For one active center, use `setup_webhooks --action setup --center-id ID` and
confirm that Telegram reports the random v2 URL and secret header. Watch
`TelegramUpdateReceipt` in Django admin for duplicates, retries, and dead-letter
updates. Confirm acknowledgements and queue latency before expanding the canary.

Rollback a center with `setup_webhooks --action remove --center-id ID`; the
command switches `bot_delivery_mode` to `polling`, and the single polling
manager will discover it. Do not remove the
polling manager/watcher until all centers have completed a 30-day webhook soak.

## 6. Health and acceptance

Use `/health/live/` for process liveness and `/health/ready/` for database,
cache, disk, Celery queue, backup age, archive-run, and cached Telegram checks.
Readiness returns 503 only for serving-critical failures; stale operational jobs
are returned as `degraded` and trigger rate-limited admin alerts.

Before removing rollback paths, test 100 centers, 100 dashboard users, bursty
Telegram updates, broadcasts, and archive work. Acceptance requires no tenant
leakage, duplicate financial mutation, or deletion after upload/verification
failure, plus graceful Redis and Telegram recovery.

Workflow automation is disabled by default. Enable
`workflow_automation_enabled` for only the two pilot centers, collect two weeks
of assignment and overdue metrics, and expand only after the improvement and
tenant-isolation targets are met.

## Credential incident note

An admin-bot token previously appeared in source documentation. The value must
be revoked and replaced in the environment before this release is deployed;
removing it from the current tree does not remove it from Git history.
