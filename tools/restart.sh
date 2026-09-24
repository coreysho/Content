#!/usr/bin/env bash
# Restart the Death Plateau server WITH WARNING. Link it as /opt/deathplateau/restart.sh.
#
#   ./restart.sh          warn everyone, restart in 60 seconds
#   ./restart.sh 300      ...in 5 minutes
#
# Players see the "System update in" countdown and a red chat line; when it runs out the world saves
# everyone and shuts down cleanly, and this starts it again. `systemctl restart` on its own does
# none of that - it stops the world at once.
#
# The countdown is started by the engine's management server (engine/src/web.ts, POST /reboot),
# which only answers requests from this machine.
set -euo pipefail

SECONDS_LEFT=${1:-60}
# deathplateau.service since the server was named; lostcity.service on a server not yet moved over
SERVICE=deathplateau.service
systemctl cat "$SERVICE" >/dev/null 2>&1 || SERVICE=lostcity.service
PORT=${WEB_MANAGEMENT_PORT:-8898}

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!!! %s\033[0m\n' "$*" >&2; exit 1; }

systemctl is-active --quiet "$SERVICE" || die "$SERVICE is not running - just start it: systemctl start $SERVICE"

say "Warning players: restart in ${SECONDS_LEFT}s"
curl -sS -f -X POST "http://127.0.0.1:${PORT}/reboot?seconds=${SECONDS_LEFT}" || die "the server did not accept the restart (is one already under way?)"

say "Waiting for the world to save and shut down"
# Watch the process, not the unit: with Restart=always systemd brings the unit straight back, and a
# check of is-active alone could miss the moment it was down.
pid=$(systemctl show -p MainPID --value "$SERVICE")
deadline=$(( $(date +%s) + SECONDS_LEFT + 120 ))   # the countdown, plus two minutes to save everyone
while [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; do
    if [ "$(date +%s)" -gt "$deadline" ]; then
        die "still running two minutes after the countdown - check: journalctl -u $SERVICE -n 50"
    fi
    sleep 2
done

if systemctl is-active --quiet "$SERVICE"; then
    say "systemd has already restarted it"
else
    say "Starting $SERVICE"
    systemctl start "$SERVICE"
fi
say "Back up. Tailing the log - Ctrl-C to stop (the server keeps running)."
journalctl -u "$SERVICE" -f
