#!/usr/bin/env bash
# Deploy the Lost City server. Put this at /opt/lostcity/deploy.sh and use it instead of
# the by-hand chain - every step below exists because leaving it out broke something.
#
#   ./deploy.sh            normal deploy
#   ./deploy.sh --force-engine   deploy even if the engine has commits GitHub does not
#
set -euo pipefail

# This script is tracked in the content repo, and it pulls that repo while running.
# bash reads a script lazily, so a file that changes mid-run has undefined behaviour -
# re-exec from a private copy first.
if [ "${DEPLOY_REEXEC:-}" != "1" ]; then
    SELF_COPY=$(mktemp /tmp/lostcity-deploy.XXXXXX.sh)
    cp "$0" "$SELF_COPY"
    trap 'rm -f "$SELF_COPY"' EXIT
    DEPLOY_REEXEC=1 exec bash "$SELF_COPY" "$@"
fi

ROOT=/opt/lostcity
CONTENT=$ROOT/content
ENGINE=$ROOT/engine
BRANCH=377-wip
SERVICE=lostcity.service
KEEP_BACKUPS=10

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

git -C "$ENGINE"  pull origin "$BRANCH"
git -C "$CONTENT" pull origin "$BRANCH"

# The engine running here must exist on GitHub. It has not, twice - commits applied by
# hand on the server are invisible to everyone else and are lost the moment this
# directory is re-cloned.
say "Checking the engine is not ahead of GitHub"
git -C "$ENGINE" fetch origin "$BRANCH" --quiet
AHEAD=$(git -C "$ENGINE" rev-list --count "origin/$BRANCH..HEAD")
if [ "$AHEAD" -gt 0 ]; then
    printf '  \033[1;33mThis engine has %s commit(s) that are NOT on GitHub:\033[0m\n' "$AHEAD"
    git -C "$ENGINE" log --oneline "origin/$BRANCH..HEAD" | sed 's/^/    /'
    if [ "${1:-}" != "--force-engine" ]; then
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

say "Restarting $SERVICE"
# systemctl, never a manual npm start - that starts a second unsupervised world that
# collides on port 43594 and dies with the SSH session.
systemctl restart "$SERVICE"

say "Deployed. Tailing the log - Ctrl-C to stop (the server keeps running)."
journalctl -u "$SERVICE" -f
