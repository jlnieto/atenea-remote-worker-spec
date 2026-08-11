#!/usr/bin/env bash

set -Eeuo pipefail
umask 0077

ACTION="${1:-}"
[[ "$#" -gt 0 ]] && shift
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEST_MODE="${ATENEA_BEAUTIPS_INSTALL_TEST_MODE:-0}"
TEST_ROOT="${ATENEA_BEAUTIPS_INSTALL_TEST_ROOT:-}"

fail() {
  printf 'BEAUTIPS_INSTALL_REJECTED: %s\n' "$1" >&2
  exit 65
}

usage() {
  printf 'Usage: %s plan|apply|verify|selection-enable|enable|disable|rollback\n' "$0" >&2
  printf '       %s register|unregister SESSION_ID WORKSPACE_IDENTITY\n' "$0" >&2
  exit 64
}

case "${ACTION}" in
  plan|apply|verify|selection-enable|enable|disable|rollback)
    [[ "$#" -eq 0 ]] || usage
    ;;
  register|unregister)
    [[ "$#" -eq 2 ]] || usage
    ;;
  *) usage ;;
esac

if [[ "${TEST_MODE}" == 1 ]]; then
  [[ "${TEST_ROOT}" == /tmp/* && "${TEST_ROOT}" != *'..'* ]] ||
    fail 'test root must be an explicit path beneath /tmp'
  PREFIX="${TEST_ROOT}"
  EXPECTED_OWNER="$(id -un):$(id -gn)"
else
  [[ "${EUID}" -eq 0 ]] || fail 'installation actions require root'
  PREFIX=''
  EXPECTED_OWNER='root:root'
fi

LIBEXEC="${PREFIX}/usr/local/libexec/atenea"
CONFIG_ROOT="${PREFIX}/etc/atenea-worker"
CONFIG="${CONFIG_ROOT}/beautips-project-codex-v1.json"
SUDOERS="${PREFIX}/etc/sudoers.d/92-atenea-beautips-project-v1"
BASE_RUNNER="${LIBEXEC}/project-codex-runner-v1.py"
INSTALLED_INSTALLER="${LIBEXEC}/install-beautips-project-v1.sh"

declare -A HASHES=(
  [beautips-operation-mediator-v1.py]='8dea2cb1fbabf126b61aef720f8076d18425aa111e426aefa4317f181e1101f9'
  [beautips-project-codex-runner-v1.py]='e3d5402fbdb4245ddfa47b1a190f8be5fa2599c81b3ab6206f70cab66bad138f'
  [beautips-secret-boundary-v1.py]='6f79b5f4cfae1924a479d541e4189c3db9cc8abcb0357a38603bdc7d7d4d21b1'
  [beautips-runtime-operations-v1.json]='a334708bb1a052b413f7b3068408d17472099a439d7afb6117d4d86dce342350'
  [project-codex-allowlist-v1.json]='b26f66203f83e77fde377f0e8f9dad2d82c7ba80636ecd169f18f354a3138c62'
)
BASE_RUNNER_SHA256='669f2f58d27a0bf829ba269abd0b8f3d61dbf3401f12cb836dcf93ebac3e3780'

source_path() {
  printf '%s/%s\n' "${SCRIPT_DIR}" "$1"
}

installed_path() {
  printf '%s/%s\n' "${LIBEXEC}" "$1"
}

validate_sources() {
  local name source
  for name in "${!HASHES[@]}"; do
    source="$(source_path "${name}")"
    [[ -f "${source}" && ! -L "${source}" ]] ||
      fail "reviewed source is missing: ${name}"
    [[ "$(sha256sum "${source}" | cut -d' ' -f1)" == "${HASHES[${name}]}" ]] ||
      fail "reviewed source hash differs: ${name}"
  done
  python3 - \
    "$(source_path beautips-operation-mediator-v1.py)" \
    "$(source_path beautips-project-codex-runner-v1.py)" \
    "$(source_path beautips-secret-boundary-v1.py)" <<'PY'
from pathlib import Path
import sys

for source in sys.argv[1:]:
    compile(Path(source).read_bytes(), source, "exec")
PY
  jq -e '
    .schemaVersion == "project-codex-allowlist-v1" and
    (.projects | keys) == ["beautips"] and
    .projects.beautips.selectionEnabled == false and
    .projects.beautips.executionEnabled == false and
    .projects.beautips.workspaces == {}
  ' "$(source_path project-codex-allowlist-v1.json)" >/dev/null ||
    fail 'source allowlist is not default-disabled'
}

sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --config %s\n' \
    "${LIBEXEC}/beautips-project-codex-runner-v1.py" "${CONFIG}"
}

default_config() {
  jq -c --arg runner "${LIBEXEC}/beautips-project-codex-runner-v1.py" '
    .projects.beautips | {
      schemaVersion: "project-codex-v1",
      selectionEnabled,
      executionEnabled,
      projectId,
      repository,
      branch,
      commit,
      manifestSha256,
      runner: $runner,
      workspaces
    }
  ' "$(source_path project-codex-allowlist-v1.json)"
}

plan() {
  validate_sources
  jq -cn \
    --arg config "${CONFIG}" \
    --arg installer "${INSTALLED_INSTALLER}" \
    --arg runner "${LIBEXEC}/beautips-project-codex-runner-v1.py" \
    --arg mediator "${LIBEXEC}/beautips-operation-mediator-v1.py" \
    --arg secrets "${LIBEXEC}/beautips-secret-boundary-v1.py" '{
      schemaVersion: "beautips-project-install-plan-v1",
      defaultState: {
        selectionEnabled: false,
        executionEnabled: false,
        workspaceCount: 0
      },
      paths: {
        config: $config,
        installer: $installer,
        runner: $runner,
        mediator: $mediator,
        secretBoundary: $secrets
      },
      publicListenerChanges: false,
      firewallChanges: false,
      serviceRestarts: false
    }'
}

verify_config() {
  [[ -f "${CONFIG}" && ! -L "${CONFIG}" ]] ||
    fail 'installed Beautips config is missing or unsafe'
  jq -e --arg runner "${LIBEXEC}/beautips-project-codex-runner-v1.py" '
    .schemaVersion == "project-codex-v1" and
    .projectId == "beautips" and
    .repository == "https://github.com/jlnieto/beautips.git" and
    .branch == "main" and
    .commit == "e9e0b3c319c518363d4135f5378ebbddced96dfb" and
    .manifestSha256 ==
      "365f1c66c51c9018c2c6f48deddbaa619b4588cae2dd463dcd916cde884e2e82" and
    .runner == $runner and
    (.selectionEnabled | type == "boolean") and
    (.executionEnabled | type == "boolean") and
    (.workspaces | type == "object")
  ' "${CONFIG}" >/dev/null || fail 'installed Beautips config is not exact'
}

verify() {
  validate_sources
  [[ -f "${BASE_RUNNER}" && ! -L "${BASE_RUNNER}" &&
      "$(sha256sum "${BASE_RUNNER}" | cut -d' ' -f1)" == "${BASE_RUNNER_SHA256}" ]] ||
    fail 'accepted base runner is absent or changed'
  [[ -f "${INSTALLED_INSTALLER}" && ! -L "${INSTALLED_INSTALLER}" &&
      "$(stat -c %U:%G:%a "${INSTALLED_INSTALLER}")" == "${EXPECTED_OWNER}:755" &&
      "$(sha256sum "${INSTALLED_INSTALLER}" | cut -d' ' -f1)" == \
        "$(sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)" ]] ||
    fail 'installed lifecycle tool is absent or changed'
  local name installed mode
  for name in "${!HASHES[@]}"; do
    installed="$(installed_path "${name}")"
    [[ -f "${installed}" && ! -L "${installed}" &&
        "$(sha256sum "${installed}" | cut -d' ' -f1)" == "${HASHES[${name}]}" ]] ||
      fail "installed artifact is absent or changed: ${name}"
    case "${name}" in
      *.py) mode=755 ;;
      *) mode=644 ;;
    esac
    [[ "$(stat -c %U:%G:%a "${installed}")" == "${EXPECTED_OWNER}:${mode}" ]] ||
      fail "installed artifact ownership differs: ${name}"
  done
  verify_config
  [[ "$(stat -c %U:%G:%a "${CONFIG}")" == "${EXPECTED_OWNER}:644" ]] ||
    fail 'installed config ownership differs'
  [[ -f "${SUDOERS}" && ! -L "${SUDOERS}" &&
      "$(stat -c %U:%G:%a "${SUDOERS}")" == "${EXPECTED_OWNER}:440" &&
      "$(cat "${SUDOERS}")" == "$(sudoers_content)" ]] ||
    fail 'installed sudoers boundary differs'
  if [[ "${TEST_MODE}" != 1 ]]; then
    visudo -cf "${SUDOERS}" >/dev/null ||
      fail 'installed sudoers boundary is invalid'
  fi
  jq -cn --slurpfile config "${CONFIG}" '{
    state: "verified",
    selectionEnabled: $config[0].selectionEnabled,
    executionEnabled: $config[0].executionEnabled,
    workspaceCount: ($config[0].workspaces | length),
    publicListenerChanges: false
  }'
}

apply_install() {
  validate_sources
  install -d -m 0755 "${LIBEXEC}" "${CONFIG_ROOT}" "$(dirname -- "${SUDOERS}")"
  [[ -f "${BASE_RUNNER}" && ! -L "${BASE_RUNNER}" &&
      "$(sha256sum "${BASE_RUNNER}" | cut -d' ' -f1)" == "${BASE_RUNNER_SHA256}" ]] ||
    fail 'accepted base runner is absent or changed'
  if [[ -e "${INSTALLED_INSTALLER}" || -L "${INSTALLED_INSTALLER}" ]]; then
    [[ -f "${INSTALLED_INSTALLER}" && ! -L "${INSTALLED_INSTALLER}" &&
        "$(sha256sum "${INSTALLED_INSTALLER}" | cut -d' ' -f1)" == \
          "$(sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)" ]] ||
      fail 'existing lifecycle tool is foreign'
  else
    install -m 0755 "${BASH_SOURCE[0]}" "${INSTALLED_INSTALLER}"
  fi
  local name destination mode
  for name in \
    beautips-operation-mediator-v1.py \
    beautips-project-codex-runner-v1.py \
    beautips-secret-boundary-v1.py \
    beautips-runtime-operations-v1.json \
    project-codex-allowlist-v1.json; do
    destination="$(installed_path "${name}")"
    case "${name}" in
      *.py) mode=0755 ;;
      *) mode=0644 ;;
    esac
    if [[ -e "${destination}" || -L "${destination}" ]]; then
      [[ -f "${destination}" && ! -L "${destination}" &&
          "$(sha256sum "${destination}" | cut -d' ' -f1)" == "${HASHES[${name}]}" ]] ||
        fail "existing installed artifact is foreign: ${name}"
    else
      install -m "${mode}" "$(source_path "${name}")" "${destination}"
    fi
  done
  if [[ -e "${CONFIG}" || -L "${CONFIG}" ]]; then
    verify_config
  else
    config_temporary="${CONFIG}.new"
    [[ ! -e "${config_temporary}" && ! -L "${config_temporary}" ]] ||
      fail 'config temporary path is occupied'
    default_config >"${config_temporary}"
    chmod 0644 "${config_temporary}"
    mv "${config_temporary}" "${CONFIG}"
  fi
  if [[ -e "${SUDOERS}" || -L "${SUDOERS}" ]]; then
    [[ -f "${SUDOERS}" && ! -L "${SUDOERS}" &&
        "$(cat "${SUDOERS}")" == "$(sudoers_content)" ]] ||
      fail 'existing sudoers boundary is foreign'
  else
    sudoers_temporary="${SUDOERS}.new"
    [[ ! -e "${sudoers_temporary}" && ! -L "${sudoers_temporary}" ]] ||
      fail 'sudoers temporary path is occupied'
    sudoers_content >"${sudoers_temporary}"
    chmod 0440 "${sudoers_temporary}"
    if [[ "${TEST_MODE}" != 1 ]]; then
      visudo -cf "${sudoers_temporary}" >/dev/null
    fi
    mv "${sudoers_temporary}" "${SUDOERS}"
  fi
  verify
}

write_state() {
  local selection="$1" execution="$2"
  verify_config
  temporary="${CONFIG}.new"
  [[ ! -e "${temporary}" && ! -L "${temporary}" ]] ||
    fail 'config temporary path is occupied'
  jq \
    --argjson selection "${selection}" \
    --argjson execution "${execution}" '
      .selectionEnabled = $selection |
      .executionEnabled = $execution
    ' "${CONFIG}" >"${temporary}"
  chmod 0644 "${temporary}"
  mv "${temporary}" "${CONFIG}"
  verify
}

selection_enable() {
  write_state true false
}

enable_execution() {
  verify_config
  jq -e '
    .selectionEnabled == true and
    (.workspaces | length) == 1
  ' "${CONFIG}" >/dev/null ||
    fail 'execution enable requires selection and one exact persisted workspace'
  write_state true true
}

disable_all() {
  write_state false false
}

register_workspace() {
  local session_id="$1" workspace_identity="$2"
  [[ "${session_id}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] ||
    fail 'workspace registration session is not a canonical UUID'
  [[ "${workspace_identity}" == "remote:ax42-01:work-session:${session_id}" ]] ||
    fail 'workspace registration identity is not exact'
  verify_config

  local session_root worktree mirror workspace_record allocation manifest
  session_root="${PREFIX}/srv/atenea/workspaces/sessions/${session_id}"
  worktree="${session_root}/beautips"
  mirror="${PREFIX}/srv/atenea/repositories/beautips.git"
  workspace_record="${session_root}/workspace-v1.json"
  allocation="${session_root}/runtime-allocation-v1.json"
  manifest="${worktree}/ops/atenea-runtime.json"
  for path in "${workspace_record}" "${allocation}" "${manifest}"; do
    [[ -f "${path}" && ! -L "${path}" ]] ||
      fail 'persisted workspace registration input is missing or unsafe'
  done
  [[ -d "${worktree}" && ! -L "${worktree}" &&
      -d "${mirror}" && ! -L "${mirror}" ]] ||
    fail 'persisted workspace Git identity is missing or unsafe'
  local workspace_owner
  if [[ "${TEST_MODE}" == 1 ]]; then
    workspace_owner="$(id -u)"
  else
    workspace_owner="$(id -u atenea-worker)"
  fi
  [[ "$(stat -c %u "${session_root}")" == "${workspace_owner}" &&
      "$(stat -c %u "${worktree}")" == "${workspace_owner}" &&
      "$(stat -c %u "${mirror}")" == "${workspace_owner}" &&
      "$(stat -c %u "${workspace_record}")" == "${workspace_owner}" &&
      "$(stat -c %u "${allocation}")" == "${workspace_owner}" &&
      "$(stat -c %u "${manifest}")" == "${workspace_owner}" &&
      "$(stat -c %a "${workspace_record}")" =~ ^6[04]0$ &&
      "$(stat -c %a "${allocation}")" =~ ^6[04]0$ ]] ||
    fail 'persisted workspace registration ownership is unsafe'

  local expected_commit expected_manifest
  expected_commit='e9e0b3c319c518363d4135f5378ebbddced96dfb'
  expected_manifest='365f1c66c51c9018c2c6f48deddbaa619b4588cae2dd463dcd916cde884e2e82'
  if [[ "${TEST_MODE}" == 1 ]]; then
    expected_commit="${ATENEA_BEAUTIPS_INSTALL_TEST_COMMIT:-}"
    expected_manifest="${ATENEA_BEAUTIPS_INSTALL_TEST_MANIFEST_SHA256:-}"
    [[ "${expected_commit}" =~ ^[0-9a-f]{40}$ &&
        "${expected_manifest}" =~ ^[0-9a-f]{64}$ ]] ||
      fail 'test registration identity is incomplete'
  fi

  jq -e \
    --arg session "${session_id}" \
    --arg worktree "${worktree}" \
    --arg mirror "${mirror}" \
    --arg commit "${expected_commit}" '
      .schemaVersion == 1 and .state == "ready" and
      .sessionId == $session and .projectId == "beautips" and
      .canonicalRemote == "https://github.com/jlnieto/beautips.git" and
      .baseBranch == "main" and
      .branch == ("atenea/session-" + $session) and
      .mirrorPath == $mirror and .worktreePath == $worktree and
      .expectedBaseCommit == $commit and .headCommit == $commit
    ' "${workspace_record}" >/dev/null ||
    fail 'workspace ownership record is not exact'
  jq -e \
    --arg session "${session_id}" \
    --arg worktree "${worktree}" \
    --arg mirror "${mirror}" '
      .schemaVersion == 1 and .state == "allocated" and
      .sessionId == $session and .projectId == "beautips" and
      .workloadClass == "normal" and
      .branch == ("atenea/session-" + $session) and
      (.slot == "slot2" or .slot == "slot3" or .slot == "slot4") and
      .mirrorPath == $mirror and .worktreePath == $worktree and
      .manifestRelativePath == "ops/atenea-runtime.json" and
      (.allocatedPorts | type == "array" and length == 3) and
      all(.allocatedPorts[]; .bindAddress == "127.0.0.1")
    ' "${allocation}" >/dev/null ||
    fail 'runtime allocation is not exact'
  local actual_remote actual_head actual_common expected_common actual_manifest
  actual_remote="$(git -c safe.directory="${worktree}" -C "${worktree}" remote get-url origin)"
  actual_head="$(git -c safe.directory="${worktree}" -C "${worktree}" rev-parse HEAD)"
  actual_common="$(realpath -e "$(git -c safe.directory="${worktree}" -C "${worktree}" \
    rev-parse --path-format=absolute --git-common-dir)")"
  expected_common="$(realpath -e "${mirror}")"
  actual_manifest="$(sha256sum "${manifest}" | cut -d' ' -f1)"
  [[ "${actual_remote}" == 'https://github.com/jlnieto/beautips.git' &&
      "${actual_head}" == "${expected_commit}" &&
      "${actual_common}" == "${expected_common}" &&
      "${actual_manifest}" == "${expected_manifest}" ]] ||
    fail 'workspace Git or manifest fingerprint is not exact'

  local allocation_sha record workspaces temporary
  allocation_sha="$(sha256sum "${allocation}" | cut -d' ' -f1)"
  record="$(
    jq -cn \
      --arg session "${session_id}" \
      --arg worktree "${worktree}" \
      --arg allocation "${allocation_sha}" '{
        sessionId: $session,
        worktree: $worktree,
        allocationSha256: $allocation
      }'
  )"
  jq -e \
    --arg identity "${workspace_identity}" \
    --argjson record "${record}" '
      (.workspaces == {} or .workspaces == {($identity): $record}) and
      .executionEnabled == false
    ' "${CONFIG}" >/dev/null ||
    fail 'another workspace is already registered or execution is active'
  workspaces="$(jq -cn --arg identity "${workspace_identity}" --argjson record "${record}" \
    '{($identity): $record}')"
  temporary="${CONFIG}.new"
  [[ ! -e "${temporary}" && ! -L "${temporary}" ]] ||
    fail 'config temporary path is occupied'
  jq --argjson workspaces "${workspaces}" '
    .selectionEnabled = true |
    .executionEnabled = false |
    .workspaces = $workspaces
  ' "${CONFIG}" >"${temporary}"
  chmod 0644 "${temporary}"
  mv "${temporary}" "${CONFIG}"
  verify
}

unregister_workspace() {
  local session_id="$1" workspace_identity="$2"
  verify_config
  jq -e \
    --arg session "${session_id}" \
    --arg identity "${workspace_identity}" '
      .executionEnabled == false and
      (.workspaces | keys) == [$identity] and
      .workspaces[$identity].sessionId == $session
    ' "${CONFIG}" >/dev/null ||
    fail 'exact disabled workspace registration does not match'
  temporary="${CONFIG}.new"
  [[ ! -e "${temporary}" && ! -L "${temporary}" ]] ||
    fail 'config temporary path is occupied'
  jq '
    .selectionEnabled = false |
    .executionEnabled = false |
    .workspaces = {}
  ' "${CONFIG}" >"${temporary}"
  chmod 0644 "${temporary}"
  mv "${temporary}" "${CONFIG}"
  verify
}

rollback() {
  verify
  jq -e '
    .selectionEnabled == false and
    .executionEnabled == false and
    .workspaces == {}
  ' "${CONFIG}" >/dev/null ||
    fail 'rollback requires disabled empty Beautips ownership'
  [[ "$(sha256sum "${INSTALLED_INSTALLER}" | cut -d' ' -f1)" == \
      "$(sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)" ]] ||
    fail 'rollback lifecycle tool identity differs'
  local name installed
  for name in \
    beautips-operation-mediator-v1.py \
    beautips-project-codex-runner-v1.py \
    beautips-secret-boundary-v1.py \
    beautips-runtime-operations-v1.json \
    project-codex-allowlist-v1.json; do
    installed="$(installed_path "${name}")"
    [[ -f "${installed}" && ! -L "${installed}" &&
        "$(sha256sum "${installed}" | cut -d' ' -f1)" == "${HASHES[${name}]}" ]] ||
      fail "rollback artifact identity differs: ${name}"
  done
  rm -f -- \
    "${LIBEXEC}/beautips-operation-mediator-v1.py" \
    "${LIBEXEC}/beautips-project-codex-runner-v1.py" \
    "${LIBEXEC}/beautips-secret-boundary-v1.py" \
    "${LIBEXEC}/beautips-runtime-operations-v1.json" \
    "${LIBEXEC}/project-codex-allowlist-v1.json" \
    "${CONFIG}" \
    "${SUDOERS}" \
    "${INSTALLED_INSTALLER}"
  printf 'BEAUTIPS_PROJECT_V1_ROLLED_BACK\n'
}

case "${ACTION}" in
  plan) plan ;;
  apply) apply_install ;;
  verify) verify ;;
  selection-enable) selection_enable ;;
  register) register_workspace "$@" ;;
  enable) enable_execution ;;
  disable) disable_all ;;
  unregister) unregister_workspace "$@" ;;
  rollback) rollback ;;
esac
