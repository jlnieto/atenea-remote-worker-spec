#!/usr/bin/env bash

set -Eeuo pipefail
umask 0077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  if sudo -n true 2>/dev/null; then
    exec sudo -n -- "$0"
  fi
  printf '%s\n' 'SKIP: shared Git multi-identity sandbox requires root' >&2
  exit 0
fi

TEST_ROOT="$(mktemp -d /tmp/shared-git-object-store.XXXXXX)"
cleanup() {
  case "$TEST_ROOT" in
    /tmp/shared-git-object-store.*)
      chmod -R u+w "$TEST_ROOT" 2>/dev/null || true
      rm -rf -- "$TEST_ROOT"
      ;;
  esac
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

source "${SCRIPT_DIR}/install-agent-run-worker-v1.sh"

SHARED_GROUP="$(getent group nogroup >/dev/null && printf nogroup || printf nobody)"
SHARED_GID="$(getent group "$SHARED_GROUP" | cut -d: -f3)"
WORKER_UID=12001
OUTSIDER_UID=12002
OUTSIDER_GID=12003
PROJECT_MIRROR="${TEST_ROOT}/atenea.git"
PROJECT_MIRROR_GROUP="$SHARED_GROUP"
PROJECT_REPOSITORY="file://${TEST_ROOT}/upstream.git"
SEED="${TEST_ROOT}/seed"
WORKTREE="${TEST_ROOT}/change-worktree"
WORKER_HOME="${TEST_ROOT}/worker-home"
TEMP_INDEX="${WORKER_HOME}/index"
EMPTY_TEMPLATE="${TEST_ROOT}/empty-template"

chgrp "$SHARED_GROUP" "$TEST_ROOT"
chmod 0710 "$TEST_ROOT"
mkdir "$EMPTY_TEMPLATE"

git init -q --bare "${TEST_ROOT}/upstream.git"
git init -q -b main "$SEED"
git -C "$SEED" config user.name Test
git -C "$SEED" config user.email test@example.invalid
printf 'base\n' >"${SEED}/tracked.txt"
git -C "$SEED" add tracked.txt
git -C "$SEED" commit -qm base
git --git-dir="${TEST_ROOT}/upstream.git" fetch -q "$SEED" main:main

git init -q --bare --template="$EMPTY_TEMPLATE" "$PROJECT_MIRROR"
git --git-dir="$PROJECT_MIRROR" remote add origin "$PROJECT_REPOSITORY"
git --git-dir="$PROJECT_MIRROR" fetch -q origin main:refs/heads/change
git --git-dir="$PROJECT_MIRROR" worktree add -q "$WORKTREE" change
WORKTREE_GIT_DIR="$(git -C "$WORKTREE" rev-parse --absolute-git-dir)"
chgrp "$SHARED_GROUP" "$PROJECT_MIRROR"
chmod 2770 "$PROJECT_MIRROR"
chgrp "$SHARED_GROUP" "$PROJECT_MIRROR/objects"
chmod 2770 "$PROJECT_MIRROR/objects"
mkdir -p "$PROJECT_MIRROR/info"
chgrp "$SHARED_GROUP" "$PROJECT_MIRROR/info"
chmod 2750 "$PROJECT_MIRROR/info"
find "$PROJECT_MIRROR/refs" -type d -exec chgrp "$SHARED_GROUP" {} +
find "$PROJECT_MIRROR/refs" -type d -exec chmod 2770 {} +
chown "$WORKER_UID:$SHARED_GID" "$PROJECT_MIRROR/refs/heads/change"
chmod 0660 "$PROJECT_MIRROR/refs/heads/change"
chown -R "$WORKER_UID:$SHARED_GID" "$WORKTREE_GIT_DIR"
chgrp "$SHARED_GROUP" "$PROJECT_MIRROR/worktrees"
chmod 2770 "$PROJECT_MIRROR/worktrees"
find "$WORKTREE_GIT_DIR" -type d -exec chmod 0770 {} +
find "$WORKTREE_GIT_DIR" -type f -exec chmod 0660 {} +

worker_content='worker-owned publication content'
worker_object="$(printf '%s\n' "$worker_content" | git hash-object --stdin)"
worker_fanout="${worker_object:0:2}"
for attempt in $(seq 1 4096); do
  root_content="root-authorized object ${attempt}"
  root_object="$(printf '%s\n' "$root_content" | git hash-object --stdin)"
  if [[ "${root_object:0:2}" == "$worker_fanout" \
      && "$root_object" != "$worker_object" ]]; then
    break
  fi
done
[[ "${root_object:0:2}" == "$worker_fanout" ]] \
  || fail "could not construct a root-owned collision fanout"
( umask 0022
  printf '%s\n' "$root_content" \
    | git --git-dir="$PROJECT_MIRROR" hash-object -w --stdin >/dev/null
)
[[ "$(stat -c '%U:%G:%a' "$PROJECT_MIRROR/objects/$worker_fanout")" \
    == "root:${SHARED_GROUP}:2755" ]] \
  || fail "legacy root-created fanout did not reproduce the blocker"

prepare_project_mirror_shared_permissions
[[ "$(stat -c '%g:%a' "$PROJECT_MIRROR/objects/$worker_fanout")" \
    == "${SHARED_GID}:2770" ]] \
  || fail "root-created fanout was not normalized for the worker group"

mkdir -p "$WORKER_HOME"
chown -R "$WORKER_UID:$SHARED_GID" "$WORKTREE" "$WORKER_HOME"
printf '%s\n' "$worker_content" >"${WORKTREE}/tracked.txt"
chown "$WORKER_UID:$SHARED_GID" "${WORKTREE}/tracked.txt"
setpriv --reuid="$WORKER_UID" --regid="$SHARED_GID" --groups="$SHARED_GID" \
  env HOME="$WORKER_HOME" GIT_INDEX_FILE="$TEMP_INDEX" \
  git -C "$WORKTREE" read-tree HEAD
setpriv --reuid="$WORKER_UID" --regid="$SHARED_GID" --groups="$SHARED_GID" \
  env HOME="$WORKER_HOME" GIT_INDEX_FILE="$TEMP_INDEX" \
  git -C "$WORKTREE" add -A
tree="$(setpriv --reuid="$WORKER_UID" --regid="$SHARED_GID" --groups="$SHARED_GID" \
  env HOME="$WORKER_HOME" GIT_INDEX_FILE="$TEMP_INDEX" \
  git -C "$WORKTREE" write-tree)"
[[ "$tree" =~ ^[0-9a-f]{40}$ \
    && -f "$PROJECT_MIRROR/objects/${worker_object:0:2}/${worker_object:2}" ]] \
  || fail "change-owned git add did not create the expected shared objects"

new_content='worker-created independent fanout'
for attempt in $(seq 1 4096); do
  candidate_content="${new_content} ${attempt}"
  candidate_object="$(printf '%s\n' "$candidate_content" | git hash-object --stdin)"
  [[ ! -e "$PROJECT_MIRROR/objects/${candidate_object:0:2}" ]] && break
done
[[ ! -e "$PROJECT_MIRROR/objects/${candidate_object:0:2}" ]] \
  || fail "could not construct a new worker-owned fanout"
printf '%s\n' "$candidate_content" >"${WORKTREE}/new.txt"
chown "$WORKER_UID:$SHARED_GID" "${WORKTREE}/new.txt"
setpriv --reuid="$WORKER_UID" --regid="$SHARED_GID" --groups="$SHARED_GID" \
  env HOME="$WORKER_HOME" GIT_INDEX_FILE="$TEMP_INDEX" \
  git -C "$WORKTREE" add -A
[[ "$(stat -c '%u:%g:%a' "$PROJECT_MIRROR/objects/${candidate_object:0:2}")" \
    == "${WORKER_UID}:${SHARED_GID}:2770" ]] \
  || fail "new worker object fanout did not inherit shared group permissions"
[[ "$(stat -c '%u:%g:%a' \
    "$PROJECT_MIRROR/objects/${candidate_object:0:2}/${candidate_object:2}")" \
    == "${WORKER_UID}:${SHARED_GID}:440" ]] \
  || fail "new worker object is not group-readable and other-confined"

if setpriv --reuid="$OUTSIDER_UID" --regid="$OUTSIDER_GID" \
    --clear-groups touch "$PROJECT_MIRROR/objects/outsider-write" 2>/dev/null; then
  fail "an identity outside the shared group wrote to the object store"
fi
verify_project_mirror_shared_permissions

printf '%s\n' 'shared Git object store multi-identity sandbox passed'
