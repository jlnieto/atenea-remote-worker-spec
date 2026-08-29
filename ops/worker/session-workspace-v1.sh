#!/usr/bin/env bash

set -Eeuo pipefail
umask 0007
export GIT_TERMINAL_PROMPT=0

ACTION="${1:-}"
SESSION_ID="${2:-}"
PROJECT_ID="${3:-}"
CANONICAL_REMOTE="${4:-}"
BASE_BRANCH="${5:-}"
WORKSPACE_BRANCH="${6:-}"
TEST_MODE="${ATENEA_WORKSPACE_TEST_MODE:-0}"
SERVICE_USER="${ATENEA_WORKER_SERVICE_USER:-atenea-worker}"
GIT_TIMEOUT_SECONDS="${ATENEA_GIT_TIMEOUT_SECONDS:-120}"
PINNED_BASE_COMMIT="${ATENEA_PINNED_BASE_COMMIT:-}"

fail() {
  local code="$1" message="$2" action="$3"
  printf '%s: %s\nNext action: %s\n' "${code}" "${message}" "${action}" >&2
  exit 65
}

usage() {
  cat >&2 <<EOF
Usage:
  $0 ensure <session-uuid> <project-id> <https-github-remote> <base-branch> <workspace-branch>
EOF
  exit 64
}

[[ "${ACTION}" == "ensure" ]] || usage
for command in flock git jq realpath timeout; do
  command -v "${command}" >/dev/null ||
    fail "OPERATION_FAILED" "Required command is unavailable: ${command}" \
      "Install the version-pinned worker prerequisites and retry."
done
[[ "${GIT_TIMEOUT_SECONDS}" =~ ^[0-9]+$ &&
      "${GIT_TIMEOUT_SECONDS}" -ge 1 &&
      "${GIT_TIMEOUT_SECONDS}" -le 600 ]] ||
  fail "OPERATION_FAILED" "Git timeout must be between 1 and 600 seconds." \
    "Correct ATENEA_GIT_TIMEOUT_SECONDS and retry."
[[ -z "${PINNED_BASE_COMMIT}" || "${PINNED_BASE_COMMIT}" =~ ^[0-9a-f]{40}$ ]] ||
  fail "WORKTREE_CONFLICT" "Pinned base commit must be an exact lowercase Git SHA." \
    "Use the reviewed commit from the project onboarding decision."

[[ "${SESSION_ID}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] ||
  fail "SESSION_REQUIRED" "Session identity is not a canonical lowercase UUID." \
    "Retry with the persisted WorkSession UUID."
[[ "${PROJECT_ID}" =~ ^[a-z][a-z0-9-]{1,62}$ ]] ||
  fail "SESSION_IDENTITY_CONFLICT" "Project identity is invalid." \
    "Use the registered lowercase project identifier."
git check-ref-format --branch "${BASE_BRANCH}" >/dev/null 2>&1 ||
  fail "WORKTREE_CONFLICT" "Base branch is not a valid Git branch name." \
    "Correct the registered canonical base branch."
git check-ref-format --branch "${WORKSPACE_BRANCH}" >/dev/null 2>&1 ||
  fail "WORKTREE_CONFLICT" "Workspace branch is not a valid Git branch name." \
    "Correct the persisted WorkSession branch."
[[ "${BASE_BRANCH}" != "${WORKSPACE_BRANCH}" ]] ||
  fail "WORKTREE_CONFLICT" "Workspace branch must differ from the canonical base branch." \
    "Use the persisted session-owned branch."

if [[ "${TEST_MODE}" == "1" ]]; then
  MIRROR_ROOT="${ATENEA_MIRROR_ROOT:-}"
  WORKSPACE_ROOT="${ATENEA_WORKSPACE_ROOT:-}"
  LOCK_ROOT="${ATENEA_WORKSPACE_LOCK_ROOT:-}"
  for root in "${MIRROR_ROOT}" "${WORKSPACE_ROOT}" "${LOCK_ROOT}"; do
    [[ "${root}" == /tmp/* && "${root}" != *".."* ]] ||
      fail "OPERATION_FAILED" "Test roots must be explicit paths beneath /tmp." \
        "Set all ATENEA_*_ROOT test variables to a fresh temporary directory."
  done
  [[ "${CANONICAL_REMOTE}" == file:///tmp/* ]] ||
    fail "WORKTREE_CONFLICT" "Test mode accepts only a file URL beneath /tmp." \
      "Use an isolated synthetic Git remote."
else
  [[ "$(id -un)" == "${SERVICE_USER}" ]] ||
    fail "OPERATION_FAILED" "Workspace provisioning must run as ${SERVICE_USER}." \
      "Invoke the versioned helper through the worker service identity."
  MIRROR_ROOT="/srv/atenea/repositories"
  WORKSPACE_ROOT="/srv/atenea/workspaces"
  LOCK_ROOT="/srv/atenea/worker/workspace-locks"
  [[ "${CANONICAL_REMOTE}" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$ ]] ||
    fail "WORKTREE_CONFLICT" "Canonical remote must be an HTTPS GitHub repository without credentials." \
      "Use the reviewed GitHub repository URL ending in .git."
fi

MIRROR_PATH="${MIRROR_ROOT}/${PROJECT_ID}.git"
SESSIONS_ROOT="${WORKSPACE_ROOT}/sessions"
SESSION_ROOT="${WORKSPACE_ROOT}/sessions/${SESSION_ID}"
WORKTREE_PATH="${SESSION_ROOT}/${PROJECT_ID}"
RECORD_PATH="${SESSION_ROOT}/workspace-v1.json"
LOCK_PATH="${LOCK_ROOT}/${PROJECT_ID}.lock"
WORKER_HOST="$(hostname)"
TEMP_MIRROR=""

cleanup() {
  if [[ -n "${TEMP_MIRROR}" &&
        "${TEMP_MIRROR}" == "${MIRROR_ROOT}/.${PROJECT_ID}.git.clone."* &&
        -d "${TEMP_MIRROR}" ]]; then
    rm -rf -- "${TEMP_MIRROR}"
  fi
}
trap cleanup EXIT

for root in "${MIRROR_ROOT}" "${WORKSPACE_ROOT}" "${LOCK_ROOT}"; do
  if [[ -e "${root}" || -L "${root}" ]]; then
    [[ -d "${root}" && ! -L "${root}" && "$(stat -c %u "${root}")" == "$(id -u)" ]] ||
      fail "WORKTREE_CONFLICT" "A workspace control root is unsafe or owned by another identity." \
        "Reconcile the worker-owned root before provisioning."
  else
    parent="$(dirname -- "${root}")"
    [[ -d "${parent}" && ! -L "${parent}" && "$(stat -c %u "${parent}")" == "$(id -u)" ]] ||
      fail "WORKTREE_CONFLICT" "A workspace control root has no safe worker-owned parent." \
        "Reconcile the worker filesystem skeleton before provisioning."
  fi
done
install -d -m 2770 "${MIRROR_ROOT}" "${WORKSPACE_ROOT}" "${LOCK_ROOT}"
for root in "${MIRROR_ROOT}" "${WORKSPACE_ROOT}" "${LOCK_ROOT}"; do
  [[ -d "${root}" && ! -L "${root}" && "$(stat -c %u "${root}")" == "$(id -u)" ]] ||
    fail "WORKTREE_CONFLICT" "A workspace control root is unsafe or owned by another identity." \
      "Reconcile the worker-owned root before provisioning."
done
if [[ -e "${SESSIONS_ROOT}" || -L "${SESSIONS_ROOT}" ]]; then
  [[ -d "${SESSIONS_ROOT}" && ! -L "${SESSIONS_ROOT}" &&
      "$(stat -c %u "${SESSIONS_ROOT}")" == "$(id -u)" ]] ||
    fail "WORKTREE_CONFLICT" "The session workspace collection is unsafe or owned by another identity." \
      "Reconcile the worker-owned sessions root before provisioning."
fi
install -d -m 2770 "${SESSIONS_ROOT}"
[[ "$(stat -c %a "${SESSIONS_ROOT}")" == "2770" ]] ||
  fail "WORKTREE_CONFLICT" "The session workspace collection has an unsafe mode." \
    "Restore mode 2770 on the worker-owned sessions root before provisioning."
[[ ! -L "${LOCK_PATH}" ]] ||
  fail "WORKTREE_CONFLICT" "The project workspace lock is a symbolic link." \
    "Inspect the lock path before retrying."
exec {lock_fd}>"${LOCK_PATH}"
[[ -f "${LOCK_PATH}" && ! -L "${LOCK_PATH}" &&
      "$(stat -c %u "${LOCK_PATH}")" == "$(id -u)" ]] ||
  fail "WORKTREE_CONFLICT" "The project workspace lock is not worker-owned." \
    "Inspect the lock path before retrying."
flock -w 30 "${lock_fd}" ||
  fail "RECONCILIATION_REQUIRED" "Timed out waiting for the project workspace lock." \
    "Retry after the current provisioning operation finishes."

if [[ -L "${SESSION_ROOT}" || -L "${WORKTREE_PATH}" || -L "${RECORD_PATH}" ]]; then
  fail "WORKTREE_CONFLICT" "A session workspace path is a symbolic link." \
    "Inspect the path and remove the conflict only after proving ownership."
fi
if [[ -e "${SESSION_ROOT}" && ! -d "${SESSION_ROOT}" ]]; then
  fail "WORKTREE_CONFLICT" "The session workspace root is not a directory." \
    "Inspect the path and reconcile it without overwriting user state."
fi
if [[ -d "${SESSION_ROOT}" &&
      "$(stat -c %u "${SESSION_ROOT}")" != "$(id -u)" ]]; then
  fail "WORKTREE_CONFLICT" "The session workspace root is owned by another identity." \
    "Reconcile ownership without modifying project files."
fi

record_exists=false
if [[ -e "${WORKTREE_PATH}" && ! -f "${RECORD_PATH}" ]]; then
  fail "WORKTREE_CONFLICT" "An existing workspace has no persisted ownership record." \
    "Reconcile its owner explicitly; do not reset, clean or overwrite it."
fi

if [[ -f "${RECORD_PATH}" ]]; then
  record_exists=true
  [[ "$(stat -c %u "${RECORD_PATH}")" == "$(id -u)" &&
        "$(stat -c %a "${RECORD_PATH}")" =~ ^6[04]0$ ]] ||
    fail "RECONCILIATION_REQUIRED" "The persisted workspace record has unsafe ownership or mode." \
      "Restore the worker-owned record permissions before retrying."
  jq -e '
    .schemaVersion == 1 and
    (.state == "provisioning" or .state == "ready") and
    (.sessionId | type == "string") and
    (.projectId | type == "string") and
    (.canonicalRemote | type == "string") and
    (.baseBranch | type == "string") and
    (.branch | type == "string") and
    (.mirrorPath | type == "string") and
    (.worktreePath | type == "string") and
    (.workerHost | type == "string") and
    (.expectedBaseCommit | test("^[0-9a-f]{40}$")) and
    (.headCommit == null or (.headCommit | test("^[0-9a-f]{40}$")))
  ' "${RECORD_PATH}" >/dev/null ||
    fail "RECONCILIATION_REQUIRED" "The persisted workspace record is invalid." \
      "Inspect and repair the worker-owned record without modifying project files."

  record_matches="$(
    jq -r \
      --arg session "${SESSION_ID}" \
      --arg project "${PROJECT_ID}" \
      --arg remote "${CANONICAL_REMOTE}" \
      --arg base "${BASE_BRANCH}" \
      --arg branch "${WORKSPACE_BRANCH}" \
      --arg mirror "${MIRROR_PATH}" \
      --arg worktree "${WORKTREE_PATH}" \
      --arg worker "${WORKER_HOST}" \
      '[
        .sessionId == $session,
        .projectId == $project,
        .canonicalRemote == $remote,
        .baseBranch == $base,
        .branch == $branch,
        .mirrorPath == $mirror,
        .worktreePath == $worktree,
        .workerHost == $worker
      ] | all' \
      "${RECORD_PATH}"
  )"
  [[ "${record_matches}" == "true" ]] ||
    fail "SESSION_IDENTITY_CONFLICT" "The session already owns a different workspace identity." \
      "Use the persisted project, branch and execution target or reconcile the session in Atenea."
elif [[ -d "${SESSION_ROOT}" ]] &&
     find "${SESSION_ROOT}" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  fail "WORKTREE_CONFLICT" "The session directory contains unowned state." \
    "Inspect the directory and reconcile ownership before provisioning."
fi

if [[ -e "${MIRROR_PATH}" ]]; then
  [[ -d "${MIRROR_PATH}" && ! -L "${MIRROR_PATH}" ]] ||
    fail "WORKTREE_CONFLICT" "The canonical mirror path is not a regular directory." \
      "Inspect the mirror path without replacing it automatically."
  [[ "$(stat -c %u "${MIRROR_PATH}")" == "$(id -u)" ]] ||
    fail "WORKTREE_CONFLICT" "The canonical mirror is owned by another identity." \
      "Reconcile mirror ownership through an approved operator action."
  [[ "$(git --git-dir="${MIRROR_PATH}" rev-parse --is-bare-repository 2>/dev/null)" == "true" ]] ||
    fail "WORKTREE_CONFLICT" "The canonical mirror path is not a bare Git repository." \
      "Move or repair the conflicting path only after review."
  existing_remote="$(
    git --git-dir="${MIRROR_PATH}" config --get remote.origin.url 2>/dev/null || true
  )"
  [[ "${existing_remote}" == "${CANONICAL_REMOTE}" ]] ||
    fail "SESSION_IDENTITY_CONFLICT" "The project mirror points to a different canonical remote." \
      "Use the registered remote or reconcile the project mirror explicitly."
  mapfile -t fetch_specs < <(
    git --git-dir="${MIRROR_PATH}" config --get-all remote.origin.fetch
  )
  [[ "${#fetch_specs[@]}" -eq 1 &&
        "${fetch_specs[0]}" == "+refs/heads/*:refs/remotes/origin/*" &&
        "$(git --git-dir="${MIRROR_PATH}" config --bool --get remote.origin.mirror || true)" != "true" ]] ||
    fail "WORKTREE_CONFLICT" "The mirror fetch policy could overwrite session-owned refs." \
      "Restore the canonical refs/remotes/origin fetch mapping before retrying."
  timeout "${GIT_TIMEOUT_SECONDS}s" \
    git --git-dir="${MIRROR_PATH}" fetch --prune origin ||
    fail "OPERATION_FAILED" "Fetching canonical refs failed." \
      "Restore GitHub connectivity or authentication and retry."
else
  [[ ! -f "${RECORD_PATH}" ]] ||
    fail "RECONCILIATION_REQUIRED" "The session record exists but its canonical mirror is missing." \
      "Restore the mirror from GitHub and reconcile the persisted session branch."
  TEMP_MIRROR="${MIRROR_ROOT}/.${PROJECT_ID}.git.clone.$$"
  [[ ! -e "${TEMP_MIRROR}" ]] ||
    fail "WORKTREE_CONFLICT" "A provisioning temporary path already exists." \
      "Inspect the stale temporary path before retrying."
  git init -q --bare --shared=0660 "${TEMP_MIRROR}"
  git --git-dir="${TEMP_MIRROR}" remote add origin "${CANONICAL_REMOTE}"
  git --git-dir="${TEMP_MIRROR}" config remote.origin.fetch \
    '+refs/heads/*:refs/remotes/origin/*'
  timeout "${GIT_TIMEOUT_SECONDS}s" \
    git --git-dir="${TEMP_MIRROR}" fetch --prune origin ||
    fail "OPERATION_FAILED" "Initial canonical mirror fetch failed." \
      "Restore GitHub connectivity or authentication and retry."
  chmod 2770 "${TEMP_MIRROR}"
  mv -- "${TEMP_MIRROR}" "${MIRROR_PATH}"
  TEMP_MIRROR=""
fi

BASE_REF="refs/remotes/origin/${BASE_BRANCH}"
git --git-dir="${MIRROR_PATH}" show-ref --verify --quiet "${BASE_REF}" ||
  fail "WORKTREE_CONFLICT" "The canonical base branch does not exist in the fetched remote." \
    "Correct the registered base branch or publish it to GitHub."

registered_branch_path="$(
  git --git-dir="${MIRROR_PATH}" worktree list --porcelain |
    awk -v ref="refs/heads/${WORKSPACE_BRANCH}" '
      $1 == "worktree" { path = $2 }
      $1 == "branch" && $2 == ref { print path }
    '
)"
if [[ -n "${registered_branch_path}" &&
      "${registered_branch_path}" != "${WORKTREE_PATH}" ]]; then
  fail "WORKTREE_CONFLICT" "The workspace branch is checked out by another worktree." \
    "Use the persisted session branch or reconcile the conflicting worktree."
fi

write_record() {
  local state="$1" head_commit="${2:-}" expected_base="$3"
  local temporary
  temporary="$(mktemp "${SESSION_ROOT}/.workspace-v1.json.XXXXXX")"
  jq -n \
    --arg session "${SESSION_ID}" \
    --arg project "${PROJECT_ID}" \
    --arg remote "${CANONICAL_REMOTE}" \
    --arg base "${BASE_BRANCH}" \
    --arg branch "${WORKSPACE_BRANCH}" \
    --arg mirror "${MIRROR_PATH}" \
    --arg worktree "${WORKTREE_PATH}" \
    --arg worker "${WORKER_HOST}" \
    --arg state "${state}" \
    --arg expectedBase "${expected_base}" \
    --arg head "${head_commit}" \
    '{
      schemaVersion: 1,
      sessionId: $session,
      projectId: $project,
      canonicalRemote: $remote,
      baseBranch: $base,
      branch: $branch,
      mirrorPath: $mirror,
      worktreePath: $worktree,
      workerHost: $worker,
      state: $state,
      expectedBaseCommit: $expectedBase,
      headCommit: (if $head == "" then null else $head end)
    }' >"${temporary}"
  chmod 0640 "${temporary}"
  mv -- "${temporary}" "${RECORD_PATH}"
}

canonical_base_commit="$(git --git-dir="${MIRROR_PATH}" rev-parse "${BASE_REF}^{commit}")"
if "${record_exists}"; then
  expected_base_commit="$(jq -r '.expectedBaseCommit' "${RECORD_PATH}")"
  [[ -z "${PINNED_BASE_COMMIT}" || "${PINNED_BASE_COMMIT}" == "${expected_base_commit}" ]] ||
    fail "SESSION_IDENTITY_CONFLICT" "Pinned base commit conflicts with persisted workspace ownership." \
      "Use the persisted onboarding commit or reconcile the WorkSession explicitly."
else
  expected_base_commit="${PINNED_BASE_COMMIT:-${canonical_base_commit}}"
fi
git --git-dir="${MIRROR_PATH}" cat-file -e "${expected_base_commit}^{commit}" 2>/dev/null ||
  fail "WORKTREE_CONFLICT" "Pinned base commit is absent from the canonical mirror." \
    "Fetch the reviewed commit from the credential-free canonical remote."
git --git-dir="${MIRROR_PATH}" merge-base --is-ancestor \
  "${expected_base_commit}" "${canonical_base_commit}" ||
  fail "WORKTREE_CONFLICT" "Pinned base commit is not an ancestor of the canonical base branch." \
    "Review the canonical branch or correct the onboarding commit."
install -d -m 2770 "${SESSION_ROOT}"

if [[ -e "${WORKTREE_PATH}" ]]; then
  [[ -d "${WORKTREE_PATH}" && -f "${WORKTREE_PATH}/.git" &&
        "$(stat -c %u "${WORKTREE_PATH}")" == "$(id -u)" ]] ||
    fail "WORKTREE_CONFLICT" "The workspace path is not a linked Git worktree." \
      "Inspect the path and reconcile it without deleting user files."
  top_candidate="$(
    git -C "${WORKTREE_PATH}" rev-parse \
      --path-format=absolute --show-toplevel 2>/dev/null || true
  )"
  common_candidate="$(
    git -C "${WORKTREE_PATH}" rev-parse \
      --path-format=absolute --git-common-dir 2>/dev/null || true
  )"
  actual_top="$(realpath -e "${top_candidate}" 2>/dev/null || true)"
  actual_common="$(realpath -e "${common_candidate}" 2>/dev/null || true)"
  actual_branch="$(git -C "${WORKTREE_PATH}" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  [[ "${actual_top}" == "$(realpath -e "${WORKTREE_PATH}")" &&
        "${actual_common}" == "$(realpath -e "${MIRROR_PATH}")" &&
        "${actual_branch}" == "${WORKSPACE_BRANCH}" ]] ||
    fail "WORKTREE_CONFLICT" "The existing worktree does not match its persisted mirror and branch." \
      "Reconcile the Git registration without resetting or cleaning the worktree."
else
  if ! "${record_exists}" &&
     git --git-dir="${MIRROR_PATH}" show-ref --verify --quiet \
       "refs/heads/${WORKSPACE_BRANCH}"; then
    fail "WORKTREE_CONFLICT" "The workspace branch exists without a persisted session owner." \
      "Reconcile the orphan branch explicitly before assigning it."
  fi
  write_record "provisioning" "" "${expected_base_commit}"
  if git --git-dir="${MIRROR_PATH}" show-ref --verify --quiet \
    "refs/heads/${WORKSPACE_BRANCH}"; then
    git --git-dir="${MIRROR_PATH}" worktree add \
      "${WORKTREE_PATH}" "${WORKSPACE_BRANCH}" >/dev/null ||
      fail "RECONCILIATION_REQUIRED" "The persisted workspace branch could not be reattached." \
        "Inspect Git worktree registration and retry without resetting the branch."
  else
    git --git-dir="${MIRROR_PATH}" worktree add \
      -b "${WORKSPACE_BRANCH}" "${WORKTREE_PATH}" "${expected_base_commit}" >/dev/null ||
      fail "OPERATION_FAILED" "The session worktree could not be created." \
        "Inspect the provisioning record and Git error before retrying."
  fi
fi

head_commit="$(git -C "${WORKTREE_PATH}" rev-parse HEAD)"
write_record "ready" "${head_commit}" "${expected_base_commit}"
cat "${RECORD_PATH}"
