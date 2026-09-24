#!/usr/bin/env bash
# Deploy the Death Plateau server. Link it as /opt/deathplateau/deploy.sh and use it instead of
# the by-hand chain - every step below exists because leaving it out broke something.
#
#   ./deploy.sh                  normal deploy: restarts the moment the build is done
#   ./deploy.sh --countdown      ...but warns players first: the "System update in" timer, 60 seconds
#   ./deploy.sh --countdown=300  ...5 minutes
#   ./deploy.sh --force-engine   deploy even if the engine has commits GitHub does not
#
# The options go in any order. With --countdown the build is done while the world is still up on the
# old code, and the timer starts only once it has succeeded, so players are warned about a restart
# that is certain to happen - and a build that fails leaves them playing, unwarned.
set -euo pipefail

# This script is tracked in the content repo, and it pulls that repo while running.
# bash reads a script lazily, so a file that changes mid-run has undefined behaviour -
# re-exec from a private copy first.
if [ "${DEPLOY_REEXEC:-}" != "1" ]; then
    SELF_COPY=$(mktemp /tmp/deathplateau-deploy.XXXXXX.sh)
    cp "$0" "$SELF_COPY"
    trap 'rm -f "$SELF_COPY"' EXIT
    DEPLOY_REEXEC=1 exec bash "$SELF_COPY" "$@"
fi

# /opt/deathplateau and deathplateau.service since the server was named (2026-09-23); a server not
# yet moved over still has /opt/lostcity and lostcity.service, and deploys the same.
ROOT=/opt/deathplateau
[ -d "$ROOT" ] || ROOT=/opt/lostcity
CONTENT=$ROOT/content
ENGINE=$ROOT/engine
BRANCH=377-wip
SERVICE=deathplateau.service
systemctl cat "$SERVICE" >/dev/null 2>&1 || SERVICE=lostcity.service
KEEP_BACKUPS=10
PORT=${WEB_MANAGEMENT_PORT:-8898}

FORCE_ENGINE=
COUNTDOWN=
for arg in "$@"; do
    case "$arg" in
        --force-engine) FORCE_ENGINE=1 ;;
        --countdown)    COUNTDOWN=60 ;;
        --countdown=*)  COUNTDOWN=${arg#--countdown=} ;;
        *) printf 'unknown option: %s\n' "$arg" >&2; exit 1 ;;
    esac
done
case "$COUNTDOWN" in
    ''|*[!0-9]*) [ -z "$COUNTDOWN" ] || { printf 'bad --countdown: %s\n' "$COUNTDOWN" >&2; exit 1; } ;;
esac

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!!! %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. save backup
# Save format v8 is ONE WAY: once the new engine writes a save, the old engine refuses
# it ("Unsupported save version"). Backing up is not optional and must happen before
# anything else, because a failed build can still leave a restarted server.
say "Backing up player saves"
STAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP=$ROOT/players-backup-$STAMP
cp -r "$ENGINE/data/players" "$BACKUP"
printf '  %s (%s files)\n' "$BACKUP" "$(find "$BACKUP" -type f | wc -l)"
ls -1dt "$ROOT"/players-backup-* 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | while read -r old; do
    printf '  pruning %s\n' "$old"; rm -rf "$old"
done

# ---------------------------------------------------------------- 2. pull both repos
# content/ and engine/ are SEPARATE repos. Pushing one does not push the other, and it
# is easy to deploy content while the engine silently stays behind.
say "Updating repositories"

# pack/inv.pack is tracked but a build appends to it, so the server always has a local
# edit that blocks the pull. The committed version is the right one.
if ! git -C "$CONTENT" diff --quiet -- pack/inv.pack 2>/dev/null; then
    printf '  discarding local edit to pack/inv.pack (a build appended to it)\n'
    git -C "$CONTENT" checkout -- pack/inv.pack
fi

LOCK_BEFORE=$(git -C "$ENGINE" rev-parse HEAD:package-lock.json 2>/dev/null || echo none)
git -C "$ENGINE"  pull origin "$BRANCH"
git -C "$CONTENT" pull origin "$BRANCH"

# A pull that changes the engine's dependencies needs them installed before the build, or the
# server dies at startup on an import (discord.js, when the Discord relay arrived). npm ci only
# when package-lock.json actually changed - it reinstalls everything and takes a minute.
LOCK_AFTER=$(git -C "$ENGINE" rev-parse HEAD:package-lock.json)
if [ "$LOCK_BEFORE" != "$LOCK_AFTER" ] || [ ! -d "$ENGINE/node_modules" ]; then
    say "Engine dependencies changed - installing"
    (cd "$ENGINE" && npm ci)
fi

# The engine running here must exist on GitHub. It has not, twice - commits applied by
# hand on the server are invisible to everyone else and are lost the moment this
# directory is re-cloned.
say "Checking the engine is not ahead of GitHub"
git -C "$ENGINE" fetch origin "$BRANCH" --quiet
AHEAD=$(git -C "$ENGINE" rev-list --count "origin/$BRANCH..HEAD")
if [ "$AHEAD" -gt 0 ]; then
    printf '  \033[1;33mThis engine has %s commit(s) that are NOT on GitHub:\033[0m\n' "$AHEAD"
    git -C "$ENGINE" log --oneline "origin/$BRANCH..HEAD" | sed 's/^/    /'
    if [ -z "$FORCE_ENGINE" ]; then
        die "Push these from whichever machine has them, or re-run with --force-engine.
    From the server itself:  cd $ENGINE && git push origin $BRANCH"
    fi
    printf '  --force-engine given, continuing anyway\n'
fi

# ---------------------------------------------------------------- 3. clear stale packs
# Generated packs are name maps rebuilt from the configs. A stale one silently keeps the
# old name list, and the error it produces names the config value, not the pack - so it
# reads as a data problem. Clearing costs a few seconds; not clearing costs a debug round.
# map.pack / midi.pack / animset.pack are deliberately NOT cleared (media indexes, and
# animset regeneration has a known anim_0 bug). varp.pack is TRACKED - never delete it.
say "Clearing generated packs"
cd "$CONTENT"
rm -f pack/script.pack pack/param.pack pack/category.pack pack/enum.pack \
      pack/struct.pack pack/mesanim.pack pack/dbtable.pack pack/dbrow.pack \
      pack/hunt.pack pack/varn.pack pack/vars.pack

# Trips shouldRebuildInterfacePack()'s mtime check. Without it the server reports
# "World ready" while serving stale interface data.
touch pack/interface.pack

# Trips the outer rebuild gate in app.ts.
rm -f "$ENGINE/data/pack/server/script.dat"

# THE ONE THAT BIT HARDEST. packConfigs() saves each type's SERVER .dat as it goes, but
# only writes the CLIENT config jag at the very end. A build that throws part-way leaves
# the jag permanently behind: the next build sees server/seq.dat is newer than every
# .seq source, skips seq, and reuses the old jag. The client then runs a stale seq table
# and throws ArrayIndexOutOfBounds on any new animation. Deleting it forces a full
# client-config rebuild and costs seconds.
rm -f "$ENGINE/data/pack/client/config"

# ---------------------------------------------------------------- 4. build, then restart
# Chained so a compile error stops the deploy with the live world still up on old code.
# npm run build is its own step; npm start packs as a side effect of booting, which makes
# a content compile error indistinguishable from a failed start.
say "Building"
cd "$ENGINE"
npm run build

# systemctl, never a manual npm start - that starts a second unsupervised world that
# collides on port 43594 and dies with the SSH session.
if [ -n "$COUNTDOWN" ] && systemctl is-active --quiet "$SERVICE"; then
    # The world's own reboot (engine/src/web.ts, POST /reboot, this machine only): the "System update
    # in" countdown, then every player saved and a clean shutdown - restart.sh's way. systemd's
    # Restart=always, or the start below, brings it back on what was just built.
    say "Warning players: restart in ${COUNTDOWN}s"
    curl -sS -f -X POST "http://127.0.0.1:${PORT}/reboot?seconds=${COUNTDOWN}" \
        || die "the server did not accept the countdown (is one already under way?) - the build is done; restart with: systemctl restart $SERVICE"
    say "Waiting for the world to save and shut down"
    # the process, not the unit: with Restart=always the unit can be back before is-active is asked
    pid=$(systemctl show -p MainPID --value "$SERVICE")
    deadline=$(( $(date +%s) + COUNTDOWN + 120 ))
    while [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; do
        [ "$(date +%s)" -le "$deadline" ] \
            || die "still running two minutes after the countdown - check: journalctl -u $SERVICE -n 50"
        sleep 2
    done
    systemctl is-active --quiet "$SERVICE" || systemctl start "$SERVICE"
else
    say "Restarting $SERVICE"
    systemctl restart "$SERVICE"
fi

say "Deployed. Tailing the log - Ctrl-C to stop (the server keeps running)."
journalctl -u "$SERVICE" -f
