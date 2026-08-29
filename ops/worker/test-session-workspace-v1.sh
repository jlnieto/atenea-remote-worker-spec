#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HELPER="${SCRIPT_DIR}/session-workspace-v1.sh"
TEST_ROOT="$(mktemp -d /tmp/atenea-workspace-test.XXXXXX)"

cleanup() {
  case "${TEST_ROOT}" in
    /tmp/atenea-workspace-test.*)
      chmod -R u+w "${TEST_ROOT}" 2>/dev/null || true
      rm -rf -- "${TEST_ROOT}"
      ;;
  esac
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

expect_failure() {
  local expected_code="$1"
  shift
  local output
  if output="$("$@" 2>&1)"; then
    fail "command unexpectedly succeeded: $*"
  fi
  grep -q "^${expected_code}:" <<<"${output}" ||
    fail "expected ${expected_code}, got: ${output}"
}

MIRROR_ROOT="${TEST_ROOT}/repositories"
WORKSPACE_ROOT="${TEST_ROOT}/workspaces"
LOCK_ROOT="${TEST_ROOT}/locks"
SEED="${TEST_ROOT}/seed"
ORIGIN="${TEST_ROOT}/origin.git"
REMOTE="file://${ORIGIN}"
SESSION_ONE="018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e"
SESSION_TWO="018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9f"
SESSION_THREE="018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da0"
SESSION_FOUR="018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da1"
SESSION_FIVE="018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da6"
PROJECT="dummy-compose"
BRANCH_ONE="atenea/session-${SESSION_ONE}"
BRANCH_FOUR="atenea/session-${SESSION_FOUR}"
BRANCH_FIVE="atenea/session-${SESSION_FIVE}"

git init -q -b main "${SEED}"
git -C "${SEED}" config user.name "Atenea fixture"
git -C "${SEED}" config user.email "fixture@example.invalid"
printf 'synthetic fixture\n' >"${SEED}/README.md"
git -C "${SEED}" add README.md
git -C "${SEED}" commit -q -m "fixture: initial"
git clone -q --bare "${SEED}" "${ORIGIN}"
initial_commit="$(git -C "${SEED}" rev-parse HEAD)"

run_helper() {
  ATENEA_WORKSPACE_TEST_MODE=1 \
  ATENEA_MIRROR_ROOT="${MIRROR_ROOT}" \
  ATENEA_WORKSPACE_ROOT="${WORKSPACE_ROOT}" \
  ATENEA_WORKSPACE_LOCK_ROOT="${LOCK_ROOT}" \
    "${HELPER}" "$@"
}

run_helper_pinned() {
  local pinned="$1"
  shift
  ATENEA_PINNED_BASE_COMMIT="${pinned}" \
  ATENEA_WORKSPACE_TEST_MODE=1 \
  ATENEA_MIRROR_ROOT="${MIRROR_ROOT}" \
  ATENEA_WORKSPACE_ROOT="${WORKSPACE_ROOT}" \
  ATENEA_WORKSPACE_LOCK_ROOT="${LOCK_ROOT}" \
    "${HELPER}" "$@"
}

run_helper ensure "${SESSION_ONE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_ONE}" \
  >"${TEST_ROOT}/first.json"
[[ "$(stat -c %a "${WORKSPACE_ROOT}/sessions")" == "2770" ]] ||
  fail "session workspace collection is not isolated with mode 2770"
WORKTREE_ONE="${WORKSPACE_ROOT}/sessions/${SESSION_ONE}/${PROJECT}"
RECORD_ONE="${WORKSPACE_ROOT}/sessions/${SESSION_ONE}/workspace-v1.json"
MIRROR="${MIRROR_ROOT}/${PROJECT}.git"

jq -e \
  --arg session "${SESSION_ONE}" \
  --arg worktree "${WORKTREE_ONE}" \
  '.state == "ready" and .sessionId == $session and
   .worktreePath == $worktree and .headCommit == .expectedBaseCommit' \
  "${TEST_ROOT}/first.json" >/dev/null
[[ "$(git -C "${WORKTREE_ONE}" rev-parse HEAD)" == "${initial_commit}" ]] ||
  fail "first worktree did not start at canonical main"
[[ "$(git --git-dir="${MIRROR}" config remote.origin.fetch)" == "+refs/heads/*:refs/remotes/origin/*" ]] ||
  fail "canonical refs are not separated from session branches"
[[ "$(git --git-dir="${MIRROR}" config --get core.sharedRepository)" == 0660 ]] ||
  fail "canonical mirror is not configured for group-confined sharing"
! find "${MIRROR}/objects" -type d ! -perm 2770 -print -quit | grep -q . ||
  fail "canonical mirror object directories are not shared with setgid"
! find "${MIRROR}/objects" -type f \( ! -perm -0040 -o -perm /0007 \) \
  -print -quit | grep -q . ||
  fail "canonical mirror objects are not group-readable and other-confined"

GIT_CONFIG_COUNT=1 \
GIT_CONFIG_KEY_0="url.${ORIGIN}.insteadOf" \
GIT_CONFIG_VALUE_0="${REMOTE}" \
  run_helper ensure "${SESSION_ONE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_ONE}" \
    >"${TEST_ROOT}/rewritten-transport.json"
cmp -s "${TEST_ROOT}/first.json" "${TEST_ROOT}/rewritten-transport.json" ||
  fail "transport URL rewrite changed persisted remote identity"
[[ "$(git --git-dir="${MIRROR}" config --get remote.origin.url)" == "${REMOTE}" ]] ||
  fail "transport URL rewrite replaced the stored remote identity"

printf 'preserve me\n' >"${WORKTREE_ONE}/uncommitted.txt"
first_git_file_hash="$(sha256sum "${WORKTREE_ONE}/.git" | cut -d' ' -f1)"
printf 'canonical update\n' >>"${SEED}/README.md"
git -C "${SEED}" add README.md
git -C "${SEED}" commit -q -m "fixture: canonical update"
git -C "${SEED}" push -q "${REMOTE}" main
run_helper ensure "${SESSION_ONE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_ONE}" \
  >"${TEST_ROOT}/second.json"
[[ -f "${WORKTREE_ONE}/uncommitted.txt" ]] ||
  fail "idempotent ensure removed uncommitted work"
[[ "$(sha256sum "${WORKTREE_ONE}/.git" | cut -d' ' -f1)" == "${first_git_file_hash}" ]] ||
  fail "idempotent ensure re-registered a healthy worktree"
cmp -s "${TEST_ROOT}/first.json" "${TEST_ROOT}/second.json" ||
  fail "idempotent ensure changed allocation output"
[[ "$(git -C "${WORKTREE_ONE}" rev-parse HEAD)" == "${initial_commit}" ]] ||
  fail "canonical fetch overwrote the session branch"

run_helper_pinned "${initial_commit}" ensure \
  "${SESSION_FIVE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_FIVE}" \
  >"${TEST_ROOT}/five.json"
WORKTREE_FIVE="${WORKSPACE_ROOT}/sessions/${SESSION_FIVE}/${PROJECT}"
[[ "$(git -C "${WORKTREE_FIVE}" rev-parse HEAD)" == "${initial_commit}" ]] ||
  fail "pinned workspace did not start at its reviewed ancestor"
jq -e --arg commit "${initial_commit}" \
  '.expectedBaseCommit == $commit and .headCommit == $commit' \
  "${TEST_ROOT}/five.json" >/dev/null ||
  fail "pinned workspace did not persist its reviewed ancestor"
run_helper_pinned "${initial_commit}" ensure \
  "${SESSION_FIVE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_FIVE}" \
  >"${TEST_ROOT}/five-repeat.json"
cmp -s "${TEST_ROOT}/five.json" "${TEST_ROOT}/five-repeat.json" ||
  fail "idempotent pinned ensure changed ownership"
canonical_commit="$(git -C "${SEED}" rev-parse HEAD)"
expect_failure SESSION_IDENTITY_CONFLICT \
  run_helper_pinned "${canonical_commit}" ensure \
    "${SESSION_FIVE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_FIVE}"

jq '.state = "provisioning"' "${RECORD_ONE}" >"${TEST_ROOT}/record.tmp"
chmod 0640 "${TEST_ROOT}/record.tmp"
mv "${TEST_ROOT}/record.tmp" "${RECORD_ONE}"
run_helper ensure "${SESSION_ONE}" "${PROJECT}" "${REMOTE}" main "${BRANCH_ONE}" \
  >"${TEST_ROOT}/recovered.json"
jq -e '.state == "ready"' "${RECORD_ONE}" >/dev/null ||
  fail "matching provisioning record was not reconciled"
[[ -f "${WORKTREE_ONE}/uncommitted.txt" ]] ||
  fail "reconciliation removed dirty work"

expect_failure WORKTREE_CONFLICT \
  run_helper ensure "${SESSION_TWO}" "${PROJECT}" "${REMOTE}" main "${BRANCH_ONE}"
[[ ! -e "${WORKSPACE_ROOT}/sessions/${SESSION_TWO}/workspace-v1.json" ]] ||
  fail "branch conflict persisted a second owner"

expect_failure SESSION_IDENTITY_CONFLICT \
  run_helper ensure "${SESSION_ONE}" "${PROJECT}" "${REMOTE}" main \
    "atenea/other-branch"
[[ -f "${WORKTREE_ONE}/uncommitted.txt" ]] ||
  fail "identity conflict modified the original worktree"

UNOWNED="${WORKSPACE_ROOT}/sessions/${SESSION_THREE}/${PROJECT}"
mkdir -p "${UNOWNED}"
printf 'unowned\n' >"${UNOWNED}/keep.txt"
expect_failure WORKTREE_CONFLICT \
  run_helper ensure "${SESSION_THREE}" "${PROJECT}" "${REMOTE}" main \
    "atenea/session-${SESSION_THREE}"
[[ "$(cat "${UNOWNED}/keep.txt")" == "unowned" ]] ||
  fail "unowned path was modified"

ORPHAN_BRANCH="atenea/orphan"
git --git-dir="${MIRROR}" branch "${ORPHAN_BRANCH}" \
  "refs/remotes/origin/main"
expect_failure WORKTREE_CONFLICT \
  run_helper ensure \
    "018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da3" "${PROJECT}" "${REMOTE}" main \
    "${ORPHAN_BRANCH}"

run_helper ensure "${SESSION_FOUR}" "${PROJECT}" "${REMOTE}" main "${BRANCH_FOUR}" \
  >"${TEST_ROOT}/four.json"
WORKTREE_FOUR="${WORKSPACE_ROOT}/sessions/${SESSION_FOUR}/${PROJECT}"
git --git-dir="${MIRROR}" worktree remove "${WORKTREE_FOUR}"
[[ ! -e "${WORKTREE_FOUR}" ]] || fail "synthetic worktree removal failed"
run_helper ensure "${SESSION_FOUR}" "${PROJECT}" "${REMOTE}" main "${BRANCH_FOUR}" \
  >"${TEST_ROOT}/four-recovered.json"
[[ "$(git -C "${WORKTREE_FOUR}" symbolic-ref --short HEAD)" == "${BRANCH_FOUR}" ]] ||
  fail "persisted branch was not reattached"

OTHER_ORIGIN="${TEST_ROOT}/other.git"
git clone -q --bare "${SEED}" "${OTHER_ORIGIN}"
expect_failure SESSION_IDENTITY_CONFLICT \
  env \
    ATENEA_WORKSPACE_TEST_MODE=1 \
    ATENEA_MIRROR_ROOT="${MIRROR_ROOT}" \
    ATENEA_WORKSPACE_ROOT="${WORKSPACE_ROOT}" \
    ATENEA_WORKSPACE_LOCK_ROOT="${LOCK_ROOT}" \
    "${HELPER}" ensure \
      "018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da2" "${PROJECT}" \
      "file://${OTHER_ORIGIN}" main \
      "atenea/session-018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da2"

git --git-dir="${MIRROR}" config --add remote.origin.fetch '+refs/*:refs/*'
expect_failure WORKTREE_CONFLICT \
  run_helper ensure \
    "018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da4" "${PROJECT}" "${REMOTE}" main \
    "atenea/session-018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da4"

CONCURRENT_SESSION="018f47a2-6b0c-7a31-9c2d-4f5a6b7c8da5"
CONCURRENT_PROJECT="dummy-concurrent"
CONCURRENT_BRANCH="atenea/session-${CONCURRENT_SESSION}"
run_helper ensure \
  "${CONCURRENT_SESSION}" "${CONCURRENT_PROJECT}" "${REMOTE}" main \
  "${CONCURRENT_BRANCH}" >"${TEST_ROOT}/concurrent-one.json" &
first_pid=$!
run_helper ensure \
  "${CONCURRENT_SESSION}" "${CONCURRENT_PROJECT}" "${REMOTE}" main \
  "${CONCURRENT_BRANCH}" >"${TEST_ROOT}/concurrent-two.json" &
second_pid=$!
wait "${first_pid}"
wait "${second_pid}"
cmp -s "${TEST_ROOT}/concurrent-one.json" "${TEST_ROOT}/concurrent-two.json" ||
  fail "serialized concurrent ensure returned different ownership records"

echo "Session workspace v1 tests passed."
