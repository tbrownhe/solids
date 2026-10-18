# Anonymous usage reporting

Solids follows the Turing Pattern reporter: a small local SQLite database and an
optional one-shot email digest. No additional database service or browser tracking
script is used. Cloudflare and SMTP are contacted only by the reporter, outside
web requests. Collection starts with this version; earlier downloads cannot be
reconstructed from application counters.

## What is recorded

The app increments hourly UTC counters on POST requests to the PDF, individual
SVG and calibration export endpoints. Successful generation, rejected requests
(4xx) and server errors (5xx) are counted separately. Preview requests, control
changes, catalog requests and health checks are not counted. A generated response
does not prove the browser saved the file or that someone printed it. Repeats and
automated clients can contribute; these are not unique-user counts.

Successful PDF/SVG counts reference normalized, allowlisted settings: solid,
effective face transforms, fired edge length, working slab thickness, shrinkage,
paper size and angle precision. SVGs also reference the reusable panel ID. Unused
recipe offsets and flat-face offsets are omitted. Equivalent preset/manual
constructions share a setup record. Recipe-level rankings combine dimensions;
complete-setup rankings distinguish them. Coupons and rejected requests retain
no setup. Hourly totals contain no individual event timestamps or visitor links.

No IP addresses, headers, user agents, cookies, visitor identifiers, project files,
or browsing histories enter this database. Cloudflare and existing proxy/access
logs may independently process connection metadata. Keep their existing policies
separate from these application analytics.

The digest summarizes the preceding complete day in `America/Los_Angeles`:
traffic estimates, format totals, rejections/errors, busiest export hours, top PDF
constructions for the day and trailing seven days, and complete setups for the
week, common dimensions, and separate SVG panel rankings. The clock label includes
PST/PDT so repeated daylight-saving hours remain
distinct. Cloudflare is filtered to the Solids hostname and queried for matching
local-day UTC boundaries. Its figures can be sampled and are presented as estimates.

## Storage and failure behavior

Both Compose configurations mount the `usage-data` volume at `/var/lib/solids`.
The image initializes that directory for UID/GID 65532. The container root remains
read-only. The application needs no reporting credentials. Outside Docker,
collection is disabled unless `SOLIDS_USAGE_DATA_DIR` is set.

Analytics initialization/write failures are logged by exception type and never
disable a valid export. Failed writes can leave a gap in counts; they are not
silently retried as extra exports. Inspect `docker compose logs studio` if counts
stop changing. The database uses WAL and short transactions so reporting can run
alongside downloads. Aggregates are retained until the owner removes them.
The reporter imports only standard-library code and construction metadata; it
does not initialize geometry or numerical worker threads.

Normal restarts, recreation and image updates preserve the named volume. Do not
use `docker compose down -v` unless deliberately discarding usage history. Include
the database in server backups using SQLite's backup API (Python `connection.backup`)
or SQLite's `.backup`; copying only an active WAL database file is not a consistent
backup. The database is not served over HTTP and has no public statistics endpoint.

## Configure the optional reporter

Merge the non-secret values from [.env.reporting.example](../.env.reporting.example)
into the existing `.env`. Set the recipient, sender, SMTP server/account, and the
Cloudflare zone ID for `tobiasbrownheft.xyz`. Reporting can run without Cloudflare;
the email will mark traffic as unavailable and still include application counts.

Reuse the Turing reporter's SMTP account and analytics token if their existing
permissions cover this zone. Otherwise create an analytics-read token with scope
limited to this zone. No DNS-edit permissions are required. Credentials belong in
`secrets/reporting/cloudflare-token` and `secrets/reporting/smtp-password`, one raw
value per file. Alternatively point `SOLIDS_REPORT_SECRETS_DIR` at an existing
directory containing these two names that is readable by UID/GID 65532. Only the
reporter mounts it, read-only. Docker does not create the credential files, and
they are deliberately absent from Git.

On silicide, copy the working Turing credentials into Solids' own directory:

```bash
cd /srv/solids
sudo install -d -o "$(id -u)" -g 65532 -m 750 secrets secrets/reporting
sudo install -o "$(id -u)" -g 65532 -m 640 /srv/turing/secrets/reporting/cloudflare-token secrets/reporting/cloudflare-token
sudo install -o "$(id -u)" -g 65532 -m 640 /srv/turing/secrets/reporting/smtp-password secrets/reporting/smtp-password
```

These commands create the files with Solids' permissions while retaining the
source credentials' Turing permissions. If Turing uses a custom secret directory,
substitute that source path. Keep the SMTP account and Cloudflare zone settings
in `.env` consistent with the copied credentials.

For new credentials, create the directory above and enter the values privately
in Bash. The prompts hide input and keep values out of shell history:

```bash
umask 077
read -r -s -p 'Cloudflare analytics token: ' solids_cf_token
printf '\n'
printf '%s' "$solids_cf_token" > secrets/reporting/cloudflare-token
unset solids_cf_token
read -r -s -p 'SMTP app password: ' solids_smtp_password
printf '\n'
printf '%s' "$solids_smtp_password" > secrets/reporting/smtp-password
unset solids_smtp_password
sudo chgrp 65532 secrets/reporting/cloudflare-token secrets/reporting/smtp-password
chmod 640 secrets/reporting/cloudflare-token secrets/reporting/smtp-password
```

Verify existence and permissions without displaying the credentials:

```bash
ls -l secrets/reporting/cloudflare-token secrets/reporting/smtp-password
```

The secret directory, `.env`, local `.usage` and SQLite files are excluded from
Git and the Docker build context. StartTLS on port 587 is the default; SMTP over
TLS is supported with `SOLIDS_SMTP_SECURITY=ssl` and the appropriate port.

## Preview and schedule

For local review (the optional reporter profile stays stopped by default):

```bash
docker compose up -d --build
docker compose --profile reporting run --rm --no-deps reporter --dry-run
```

For production, use the production Compose file consistently:

```bash
docker compose -f compose.production.yaml up -d --build studio
docker compose -f compose.production.yaml --profile reporting run --rm --no-deps reporter --dry-run
docker compose -f compose.production.yaml --profile reporting run --rm --no-deps reporter --dry-run --date 2026-10-17
```

Dry runs neither send email nor claim delivery. They may initialize an empty
database and query Cloudflare if configured. They do not require SMTP settings.
Dates must be complete days before today in the reporting timezone. A day before
collection started will have empty application counts.

When ready to send, an explicit `--test-email` sends an SMTP configuration test
without touching the database or claiming a report day. Running without either
flag sends the daily digest. No emails are sent by app startup or normal Compose
startup.

After deployment and a successful preview, install the supplied timer:

```bash
sudo install -m 0644 deploy/systemd/solids-report.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/solids-report.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now solids-report.timer
systemctl list-timers solids-report.timer
```

The service uses `/srv/solids`. The timer runs at 08:15 Pacific time with up to ten
minutes' random delay, independent of the host timezone, and catches up after a
reboot. Inspect it with `journalctl -u solids-report.service -n 100 --no-pager`.

A database claim permits at most one delivery attempt per local report date,
including concurrent invocations. Configuration is validated before claiming.
An SMTP error after the claim marks delivery failed and prevents automatic resend:
the mail server may already have accepted the message. Inspect the data with
`--dry-run --date ...` before considering a deliberate manual retry. Cloudflare
failures do not suppress the application digest. Scheduling is separate from
outage alerts; app health checks do not depend on analytics or mail.

References: [Cloudflare analytics authentication](https://developers.cloudflare.com/analytics/graphql-api/getting-started/authentication/api-token-auth/),
[Cloudflare sampling](https://developers.cloudflare.com/analytics/graphql-api/sampling/),
[SQLite backup API](https://www.sqlite.org/backup.html).
