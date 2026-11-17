#!/usr/bin/env bash
# ship.sh <ssh-host> [env]: build lectern at HEAD, bundle it and deploy it on <ssh-host>.
#
#   scripts/ship.sh h4aiqem2 prod     # runs /opt/lectern/bin/deploy-prod there
#
# The bundle is manifest.env + image.tar + compose.yml (see deploy/bin/deploy-host). The working
# tree must be clean, so the tag (the commit) says exactly what runs. Safe to re-run: deploying
# the same commit again is a no-op restart with a health check.
set -euo pipefail

host="${1:?usage: scripts/ship.sh <ssh-host> [env]}"
env="${2:-prod}"
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
[[ -z "$(git status --porcelain)" ]] || { echo "ship.sh: commit or stash your changes first" >&2; exit 1; }
tag="$(git rev-parse --short=12 HEAD)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

echo "building lectern:$tag"
docker build -q -t "lectern:$tag" . >/dev/null
printf 'LECTERN_TAG=%s\n' "$tag" >"$work/manifest.env"
cp deploy/compose.yml "$work/compose.yml"
docker save "lectern:$tag" -o "$work/image.tar"
echo "shipping to $host ($env)"
tar -czf - -C "$work" manifest.env image.tar compose.yml | ssh -o BatchMode=yes "$host" "/opt/lectern/bin/deploy-$env deploy"
ssh -o BatchMode=yes "$host" "/opt/lectern/bin/deploy-$env status"
