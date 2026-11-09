#!/bin/bash
# Root-owned forced command for the production deployment SSH key.
set -euo pipefail
umask 077
root=/opt/signapse-prod/mdg
read -r image
read -r revision
read -r registry_user
read -r registry_token
[[ "$image" =~ ^dgminhtam/signapse-mdg@sha256:[a-f0-9]{64}$ ]]
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
[[ "$registry_user" =~ ^[a-z0-9][a-z0-9_-]*$ ]]
test -n "$registry_token"

exec 9>"$root/.deploy.lock"
flock -w 300 9
main_revision=$(curl -fsS --max-time 20 https://api.github.com/repos/dgminhtam/signapse-mdg/git/ref/heads/main |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["object"]["sha"])')
if [[ "$revision" != "$main_revision" ]]; then
  echo 'Refusing to deploy a revision that is no longer at main HEAD.' >&2
  exit 1
fi
release="$root/releases/$revision"
install -d -m 700 "$release"
source="https://raw.githubusercontent.com/dgminhtam/signapse-mdg/$revision/deploy"
for file in prod.py docker-compose.prod.yml; do
  curl -fsS --max-time 20 "$source/$file" -o "$release/$file"
done
printf '%s' "$registry_token" | python3 "$release/prod.py" "$image" "$revision" "$registry_user"
