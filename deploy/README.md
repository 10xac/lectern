# Deploying lectern

One container serves the web app and the API (and MCP at `/mcp/`) from a single uvicorn process.
A host nginx in front terminates TLS. The container listens on `127.0.0.1` only.

```
browser / AI tool ──https──▶ nginx (host, :443) ──▶ 127.0.0.1:${LECTERN_PORT:-8790} ──▶ container :8000
                                                                                     /data/lectern.db
                                                                                     /data/blobs
```

## Before the first deploy

You need Docker with the compose plugin, nginx on the host, and a TLS certificate for the host name.

Create `.env` in the repository root (never commit it). Everything from `.env.example` applies;
for a public deployment, set at least:

| Variable | Why |
|---|---|
| `LECTERN_HOSTS` | **Required.** The public host name(s), comma-separated (e.g. `lectern.example.org`); MCP refuses other `Host` headers |
| `LECTERN_PUBLIC_URL` | The public address (`https://lectern.example.org`), used in invite links |
| `LECTERN_SECRET_KEY` | A Fernet key that encrypts the API keys admins store in the web app. Generate one with `docker compose … run --rm lectern python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep it safe: without it the stored keys cannot be read |
| `LECTERN_PORT` | The local port nginx forwards to (default 8790); use a different one per instance on a host |
| `LECTERN_MAX_ASKS_PER_DAY` | The daily question budget across all users and surfaces (default 200): asks spend your API keys |
| `LECTERN_ASKS_PER_MINUTE`, `LECTERN_UPLOADS_PER_MINUTE` | Per-IP limits (defaults 10 and 20) |
| `LECTERN_MAX_UPLOAD_MB` | Request body cap (default 20) |
| `LECTERN_PROVIDER`, `LECTERN_API_KEY`, `LECTERN_MODEL`, `LECTERN_BASE_URL`, `EXA_API_KEY`, `OPENROUTER_API_KEY` | Optional defaults: admins can set the model and keys in the web app (**Account → Models and keys**), which then take precedence |

Keys set in the web app are stored encrypted with `LECTERN_SECRET_KEY`. Keys are never returned by
the API (only set or unset, and their last four characters), and lectern removes the values of
`*_KEY`, `*_TOKEN` and `*_PASSWORD` variables from its logs.

## Users

Only invited people can sign in. Seed the first admin once the container runs; the command
prints a one-time link (valid 7 days) to open and choose a password:

```bash
docker compose --env-file .env -f deploy/compose.yml exec lectern lectern users create-admin you@example.org
```

Admins then invite others from **Account → Users** (each invite is a one-time link to send them),
change roles, disable accounts and issue new links (which is also how a forgotten password is
reset). Each person creates their own **MCP tokens** under **Account**: a token is shown once,
lasts up to 90 days, and stops working when it is revoked or its owner is disabled.

For an S3 (or MinIO, R2) blob store instead of the `/data/blobs` volume, set
`LECTERN_EXTRAS=s3`, `LECTERN_BLOBS_IN_CONTAINER=s3://bucket/prefix` and the `AWS_*` variables in `.env`.

## Deploy

From the repository root:

```bash
docker compose --env-file .env -f deploy/compose.yml up -d --build
docker compose --env-file .env -f deploy/compose.yml ps     # wait for "healthy"
curl -s http://127.0.0.1:${LECTERN_PORT:-8790}/health
```

Then the nginx site (see the header of `deploy/nginx.conf.template`):

```bash
SERVER_NAME=lectern.example.org \
TLS_CERT=/etc/letsencrypt/live/lectern.example.org/fullchain.pem \
TLS_KEY=/etc/letsencrypt/live/lectern.example.org/privkey.pem \
LECTERN_PORT=8790 \
envsubst '${SERVER_NAME} ${TLS_CERT} ${TLS_KEY} ${LECTERN_PORT}' \
  < deploy/nginx.conf.template | sudo tee /etc/nginx/sites-available/lectern.example.org
sudo ln -s /etc/nginx/sites-available/lectern.example.org /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

The template listens on IPv4 only and has no `http2` on its listen lines: on a host whose other
sites share `0.0.0.0:443`, `http2` on one listen line turns it on for all of them.

To run two instances (say a dev and a production host name) on one machine, use a separate
checkout, `.env`, `LECTERN_PORT` and compose project name (`docker compose -p lectern-dev …`)
for each.

Connect an AI tool to the deployment with a personal token from **Account → MCP tokens**:
`claude mcp add --transport http lectern https://lectern.example.org/mcp/ --header "Authorization: Bearer lectern_pat_…"`.

## Upgrade

```bash
git pull
docker compose --env-file .env -f deploy/compose.yml up -d --build
```

The database migrates itself on start (new tables and columns are added in place). Back up first.

## Back up

The database (a consistent copy, even while lectern runs) and the blobs:

```bash
mkdir -p backups && stamp=$(date +%Y%m%d-%H%M)
docker compose --env-file .env -f deploy/compose.yml exec -T lectern python -c \
  "import sqlite3; s = sqlite3.connect('/data/lectern.db'); d = sqlite3.connect('/data/backup.db'); s.backup(d); d.close()"
docker compose --env-file .env -f deploy/compose.yml cp lectern:/data/backup.db backups/lectern-$stamp.db
docker compose --env-file .env -f deploy/compose.yml exec -T lectern tar -C /data -czf - blobs > backups/blobs-$stamp.tgz
```

(That is SQLite's online `.backup`, through Python because the slim image has no `sqlite3` tool.)

## Restore

```bash
docker compose --env-file .env -f deploy/compose.yml stop
docker compose --env-file .env -f deploy/compose.yml cp backups/lectern-<stamp>.db lectern:/data/lectern.db
docker compose --env-file .env -f deploy/compose.yml run --rm -T lectern \
  sh -c 'rm -rf /data/blobs/* && tar -C /data -xzf -' < backups/blobs-<stamp>.tgz
docker compose --env-file .env -f deploy/compose.yml start
```

After restoring blobs and database from different moments, open the web app's **DNA → Check
files** (or `POST /files/reconcile`) to find files that no longer match.
