#!/usr/bin/env bash

set -Eeuo pipefail
umask 0077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEST_ROOT="$(mktemp -d /tmp/agent-run-worker-install.XXXXXX)"

cleanup() {
  case "${TEST_ROOT}" in
    /tmp/agent-run-worker-install.*)
      chmod -R u+w "${TEST_ROOT}" 2>/dev/null || true
      rm -rf -- "${TEST_ROOT}"
      ;;
  esac
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

source "${SCRIPT_DIR}/install-agent-run-worker-v1.sh"
require_root() { :; }
chown() { :; }

MODE_FIXTURE="${TEST_ROOT}/mode-fixture"
mkdir -p "${MODE_FIXTURE}"
chmod 2770 "${MODE_FIXTURE}"
install_exact_directory "$(id -un)" "$(id -gn)" 0750 "${MODE_FIXTURE}/release"
[[ "$(stat -c '%a' "${MODE_FIXTURE}/release")" == 750 ]] \
  || fail "exact directory mode retained a setgid parent bit"

[[ "$(sha256sum "${SCRIPT_DIR}/templates/atenea-agent-run-worker-v1.service" | cut -d' ' -f1)" \
    == "${SERVICE_TEMPLATE_SHA256}" ]] || fail "service template fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/codex-platform-instructions-v1.md" | cut -d' ' -f1)" \
    == "${PLATFORM_INSTRUCTIONS_SHA256}" ]] || fail "platform instruction fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/agent-run-worker-v1.py" | cut -d' ' -f1)" \
    == "${PROGRAM_SHA256}" ]] || fail "worker program fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/development-change-workspace-v1.py" | cut -d' ' -f1)" \
    == "${DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR_SHA256}" ]] \
  || fail "development-change workspace mediator fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/project-codex-runner-v1.py" | cut -d' ' -f1)" \
    == "${PROJECT_RUNNER_SHA256}" ]] || fail "project runner fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/beautips-project-codex-runner-v1.py" | cut -d' ' -f1)" \
    == "${BEAUTIPS_PROJECT_RUNNER_SHA256}" ]] \
  || fail "Beautips compatibility runner fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/atenea-validation-v1.py" | cut -d' ' -f1)" \
    == "${VALIDATION_MEDIATOR_SHA256}" ]] \
  || fail "validation mediator fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/atenea-playwright-validation-v1.js" | cut -d' ' -f1)" \
    == "${PLAYWRIGHT_CHECK_SHA256}" ]] \
  || fail "Playwright check fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/atenea-workspace-activation-v1.sh" | cut -d' ' -f1)" \
    == "${WORKSPACE_ACTIVATOR_SHA256}" ]] \
  || fail "Atenea workspace activator fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/atenea-workspace-release-v1.py" | cut -d' ' -f1)" \
    == "${WORKSPACE_RELEASER_SHA256}" ]] \
  || fail "Atenea workspace releaser fingerprint is stale"
[[ "${PROJECT_PINNED_WORKSPACE_SESSION_ID}" == "6547081d-895e-4be1-a8fd-d115b7743cdf" \
    && "${PROJECT_PINNED_WORKSPACE_COMMIT}" == "e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5" \
    && "${PROJECT_PINNED_SOURCE_TARGET_COMMIT}" == "96220cd4eb0cf2f6ec985588d086f159eb2baebc" \
    && "${PROJECT_PINNED_WORKSPACE_RECORD_SHA256}" == "3cde263630712c311c2c951900ca3d5b4f3d35b54a54ad06bae9c5b7ba580ec7" \
    && "${PROJECT_PINNED_ALLOCATION_SHA256}" == "08db92551da4cdf7cc2d082cf43150b41cd118a7ed0602a54945747495f26d87" \
    && "${PROJECT_PINNED_DIRTY_PATH}" == "android/core-console/src/main/java/com/atenea/android/coreconsole/AteneaShell.kt" \
    && "${PROJECT_PINNED_DIRTY_CONTENT_SHA256}" == "c50a9aa5b07cd394b85a51c65aff3a9eff37844cd071a9c53a070ff945e07563" ]] \
  || fail "reviewed WS19 pinned source identity changed"
[[ "$(workspace_activation_sudoers_content | wc -l)" -eq 5 ]] \
  || fail "workspace lifecycle sudo authority count is not exact"
[[ "$(workspace_activation_sudoers_content | grep -Fxc \
    "atenea-worker ALL=(root) NOPASSWD: ${WORKSPACE_RELEASER}")" -eq 1 ]] \
  || fail "workspace release sudo authority without arguments is missing"
[[ "$(workspace_activation_sudoers_content | grep -Fxc \
    "atenea-worker ALL=(root) NOPASSWD: ${WORKSPACE_RELEASER} --diagnose-capacity-owner")" \
    -eq 1 ]] || fail "read-only capacity diagnosis sudo authority is not exact"
[[ "$(workspace_activation_sudoers_content | grep -Fxc \
    "atenea-worker ALL=(root) NOPASSWD: ${WORKSPACE_RELEASER} --diagnose-release-preflight")" \
    -eq 1 ]] || fail "read-only release preflight sudo authority is not exact"
[[ "$(workspace_activation_sudoers_content | grep -Fxc \
    "atenea-worker ALL=(root) NOPASSWD: ${WORKSPACE_RELEASER} --diagnose-unactivated")" \
    -eq 1 ]] || fail "unactivated absence diagnosis sudo authority is not exact"
! workspace_activation_sudoers_content | grep -F "${WORKSPACE_RELEASER} *" >/dev/null \
  || fail "workspace release sudo authority is broadened"
[[ "$(sha256sum "${SCRIPT_DIR}/session-workspace-v1.sh" | cut -d' ' -f1)" \
    == "${SESSION_WORKSPACE_SHA256}" ]] \
  || fail "workspace dependency fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/runtime-admission-v1.sh" | cut -d' ' -f1)" \
    == "${RUNTIME_ADMISSION_SHA256}" ]] \
  || fail "admission dependency fingerprint is stale"
[[ "$(sha256sum "${SCRIPT_DIR}/session-runtime-allocation-v1.sh" | cut -d' ' -f1)" \
    == "${SESSION_ALLOCATION_SHA256}" ]] \
  || fail "allocation dependency fingerprint is stale"
dependency_preflight_line="$(grep -n -m1 '^  verify_workspace_activation_dependency$' \
  "${SCRIPT_DIR}/install-agent-run-worker-v1.sh" | cut -d: -f1)"
service_stop_line="$(grep -n -m1 '^  systemctl stop "\$SERVICE"$' \
  "${SCRIPT_DIR}/install-agent-run-worker-v1.sh" | cut -d: -f1)"
project_config_preflight_line="$(grep -n -m1 \
  'retained_project_config_sha256="\$(project_config_install_preflight)"' \
  "${SCRIPT_DIR}/install-agent-run-worker-v1.sh" | cut -d: -f1)"
[[ -n "${dependency_preflight_line}" && -n "${service_stop_line}" \
    && "${dependency_preflight_line}" -lt "${service_stop_line}" ]] \
  || fail "activation dependency is not checked before the worker stops"
[[ -n "${project_config_preflight_line}" \
    && "${project_config_preflight_line}" -lt "${service_stop_line}" ]] \
  || fail "project configuration is not checked before the worker stops"
[[ "$(grep -Fc '  verify_workspace_activation_dependency' \
  "${SCRIPT_DIR}/install-agent-run-worker-v1.sh")" -eq 2 ]] \
  || fail "activation dependency is not checked by both apply and verify"
[[ "$(sha256sum "${SCRIPT_DIR}/templates/${MATERIALIZATION_SERVICE}" | cut -d' ' -f1)" \
    == "${MATERIALIZATION_SERVICE_TEMPLATE_SHA256}" ]] \
  || fail "materialization service fingerprint is stale"
grep -Fqx 'ExecStart=/usr/local/libexec/atenea/install-agent-run-worker-v1.sh prepare-materialization-root' \
  "${SCRIPT_DIR}/templates/${MATERIALIZATION_SERVICE}" \
  || fail "materialization preparation command is not exact"
grep -Fqx "Requires=${MATERIALIZATION_SERVICE}" \
  "${SCRIPT_DIR}/templates/${SERVICE}" \
  || fail "worker does not require exact materialization preparation"
grep -Fqx 'RemainAfterExit=yes' "${SCRIPT_DIR}/templates/${MATERIALIZATION_SERVICE}" \
  || fail "materialization preparation is not retained for the worker lifetime"

SERVICE_TEMPLATE="${SCRIPT_DIR}/templates/atenea-agent-run-worker-v1.service"
[[ "$(grep -Fxc \
  'LoadCredential=atenea-publication-deploy-key:/etc/atenea-worker/atenea-publication-deploy-key' \
  "${SERVICE_TEMPLATE}")" -eq 1 ]] \
  || fail "publication deploy key systemd credential is not exact"
grep -Fqx 'RuntimeDirectory=atenea-publication' "${SERVICE_TEMPLATE}" \
  || fail "publication runtime directory is not exact"
grep -Fqx 'RuntimeDirectoryMode=0700' "${SERVICE_TEMPLATE}" \
  || fail "publication runtime directory mode is not private"
! grep -E 'Environment=.*(publication-deploy-key|CREDENTIALS_DIRECTORY|PRIVATE.KEY)' \
  "${SERVICE_TEMPLATE}" >/dev/null \
  || fail "publication credential is projected through the service environment"
! grep -F 'atenea-publication-deploy-key' \
  "${SCRIPT_DIR}/install-agent-run-worker-v1.sh" >/dev/null \
  || fail "installer must not create or install the publication deploy key"
[[ "$(grep -Fxc 'ReadOnlyPaths=/srv/atenea/attachments-v1' "${SERVICE_TEMPLATE}")" -eq 1 ]] \
  || fail "service does not expose only the fixed retained root read-only"
[[ "$(grep -Fc '/run/atenea/codex-images' "${SERVICE_TEMPLATE}")" -eq 1 ]] \
  || fail "service materialization write boundary is not exact"
[[ "$(grep -Fc '/srv/atenea/worker/workspace-release-v1' "${SERVICE_TEMPLATE}")" -eq 1 ]] \
  || fail "service release journal write boundary is not exact"
[[ "$(grep -Fc '/srv/atenea/worker/validation-broker-v1' "${SERVICE_TEMPLATE}")" -eq 1 ]] \
  || fail "service validation journal write boundary is not exact"
! grep -E '^ReadWritePaths=.*attachments-v1' "${SERVICE_TEMPLATE}" >/dev/null \
  || fail "service grants attachment write access"
grep -F -- '--project-readiness-enabled --unactivated-release-enabled' \
  "${SERVICE_TEMPLATE}" >/dev/null \
  || fail "fresh-session worker gates are not both explicit"
grep -F -- '--development-change-workspace-mediator /usr/local/libexec/atenea/development-change-workspace-v1.py' \
  "${SERVICE_TEMPLATE}" >/dev/null \
  || fail "development-change workspace mediator boundary is not explicit"
[[ "$(grep -Fc '/srv/atenea/workspaces/changes' "${SERVICE_TEMPLATE}")" -eq 1 ]] \
  || fail "development-change workspace write boundary is not exact"
grep -F -- 'capabilities: [$synthetic_capability, $development_change_capability, $development_change_publication_capability, $validation_capability]' \
  "${SCRIPT_DIR}/install-agent-run-worker-v1.sh" >/dev/null \
  || fail "installer plan does not advertise the durable worker capabilities"

SESSION_ID=11111111-1111-4111-8111-111111111111
WORKSPACE_IDENTITY="remote:ax42-01:work-session:${SESSION_ID}"
WORKTREE="${TEST_ROOT}/srv/atenea/workspaces/sessions/${SESSION_ID}/atenea"
PROJECT_MIRROR="${TEST_ROOT}/srv/atenea/repositories/atenea.git"
PROJECT_REF="refs/remotes/origin/${PROJECT_BRANCH}"
PROJECT_WORKSPACES_ROOT="${TEST_ROOT}/srv/atenea/workspaces/sessions"
PROJECT_CONFIG="${TEST_ROOT}/etc/atenea-worker/project-codex-v1.json"
mkdir -p "${WORKTREE}" "$(dirname -- "${PROJECT_MIRROR}")" "$(dirname -- "${PROJECT_CONFIG}")"

git init -q --bare "${PROJECT_MIRROR}"
git init -q -b "${PROJECT_BRANCH}" "${WORKTREE}"
git -C "${WORKTREE}" config user.name Test
git -C "${WORKTREE}" config user.email test@example.invalid
git -C "${WORKTREE}" remote add origin "${PROJECT_REPOSITORY}"
mkdir -p "${WORKTREE}/ops"
printf '{}\n' >"${WORKTREE}/ops/atenea-runtime.json"
PROJECT_MANIFEST_SHA256="$(sha256sum "${WORKTREE}/ops/atenea-runtime.json" | cut -d' ' -f1)"
PINNED_DIRTY_RELATIVE_PATH="android/core-console/src/main/java/com/atenea/android/coreconsole/AteneaShell.kt"
PINNED_OLD_DIRTY_RELATIVE_PATH="android/core-console/src/main/java/com/atenea/android/coreconsole/WorkSessionConversationScreen.kt"
mkdir -p "${WORKTREE}/$(dirname -- "${PINNED_DIRTY_RELATIVE_PATH}")"
printf 'shell base\n' >"${WORKTREE}/${PINNED_DIRTY_RELATIVE_PATH}"
printf 'screen base\n' >"${WORKTREE}/${PINNED_OLD_DIRTY_RELATIVE_PATH}"
printf 'base\n' >"${WORKTREE}/tracked.txt"
git -C "${WORKTREE}" add .
git -C "${WORKTREE}" commit -qm base
RETAINED_COMMIT="$(git -C "${WORKTREE}" rev-parse HEAD)"
git --git-dir="${PROJECT_MIRROR}" fetch -q "${WORKTREE}" \
  "${RETAINED_COMMIT}:refs/remotes/origin/${PROJECT_BRANCH}"
printf 'canonical\n' >>"${WORKTREE}/tracked.txt"
git -C "${WORKTREE}" add tracked.txt
git -C "${WORKTREE}" commit -qm canonical
CANONICAL_COMMIT="$(git -C "${WORKTREE}" rev-parse HEAD)"
git --git-dir="${PROJECT_MIRROR}" fetch -q "${WORKTREE}" \
  "+${CANONICAL_COMMIT}:refs/remotes/origin/${PROJECT_BRANCH}"
git -C "${WORKTREE}" reset -q "${RETAINED_COMMIT}"
printf 'draft\n' >>"${WORKTREE}/tracked.txt"
printf 'owned\n' >"${TEST_ROOT}/allocation"
mkdir -p "$(dirname -- "${WORKTREE}")"
cp "${TEST_ROOT}/allocation" "$(dirname -- "${WORKTREE}")/runtime-allocation-v1.json"

ATTACHMENT_ROOT="/srv/atenea/attachments-v1"
write_project_config false false '{}' "${CANONICAL_COMMIT}"
[[ "$(jq -r '.attachmentRoot' "${PROJECT_CONFIG}")" == "${ATTACHMENT_ROOT}" ]] \
  || fail "project configuration omitted the fixed attachment root"
if jq '.attachmentRoot = "/srv/foreign"' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.foreign" \
    && mv "${PROJECT_CONFIG}.foreign" "${PROJECT_CONFIG}" \
    && ( verify_project_config_content ) >/dev/null 2>&1; then
  fail "foreign attachment root was accepted"
fi
write_project_config false false '{}' "${CANONICAL_COMMIT}"
verify_project_config_file_identity() { :; }
cp "${PROJECT_CONFIG}" "${TEST_ROOT}/current-project-config.json"
for field in repository branch manifestSha256 runner; do
  jq --arg field "${field}" '.[$field] = "foreign"' \
    "${TEST_ROOT}/current-project-config.json" >"${PROJECT_CONFIG}"
  if ( verify_project_config_content ) >/dev/null 2>&1; then
    fail "foreign current project authority was accepted: ${field}"
  fi
done
cp "${TEST_ROOT}/current-project-config.json" "${PROJECT_CONFIG}"
BEAUTIPS_PROJECT_RUNNER="${TEST_ROOT}/beautips-project-codex-runner-v1.py"
printf 'accepted predecessor\n' >"${BEAUTIPS_PROJECT_RUNNER}"
BEAUTIPS_PROJECT_RUNNER_PREDECESSOR_SHA256="$(
  sha256sum "${BEAUTIPS_PROJECT_RUNNER}" | cut -d' ' -f1
)"
BEAUTIPS_PROJECT_RUNNER_SHA256="${BEAUTIPS_PROJECT_RUNNER_PREDECESSOR_SHA256}"
verify_beautips_project_runner_file_identity() { :; }
verify_beautips_project_runner_upgrade
printf 'foreign predecessor\n' >"${BEAUTIPS_PROJECT_RUNNER}"
if ( verify_beautips_project_runner_upgrade ) >/dev/null 2>&1; then
  fail "foreign Beautips compatibility runner was accepted"
fi
PRESERVED_CONFIG_SHA256="$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)"
PREFLIGHT_SHA256="$(project_config_install_preflight)"
[[ "${PREFLIGHT_SHA256}" == "retain:${PRESERVED_CONFIG_SHA256}" ]] \
  || fail "installer preflight did not retain the existing configuration identity"
project_config_install_finalize "${PREFLIGHT_SHA256}"
[[ "$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)" == "${PRESERVED_CONFIG_SHA256}" ]] \
  || fail "installer finalize rewrote the existing configuration"

jq 'del(.attachmentRoot)' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.legacy"
mv "${PROJECT_CONFIG}.legacy" "${PROJECT_CONFIG}"
LEGACY_CONFIG_SHA256="$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)"
LEGACY_PREFLIGHT_SHA256="$(project_config_install_preflight)"
[[ "${LEGACY_PREFLIGHT_SHA256}" == "retain:${LEGACY_CONFIG_SHA256}" ]] \
  || fail "installer preflight did not retain the exact legacy configuration"
project_config_install_finalize "${LEGACY_PREFLIGHT_SHA256}"
[[ "$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)" == "${LEGACY_CONFIG_SHA256}" ]] \
  || fail "installer finalize rewrote the exact legacy configuration"

write_project_config false false '{}' "${RETAINED_COMMIT}"
SOURCE_ADVANCE_CONFIG_SHA256="$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)"
SOURCE_ADVANCE_PREFLIGHT="$(project_config_install_preflight)"
[[ "${SOURCE_ADVANCE_PREFLIGHT}" \
    == "source-advance:${SOURCE_ADVANCE_CONFIG_SHA256}:${RETAINED_COMMIT}:${CANONICAL_COMMIT}" ]] \
  || fail "installer did not recognize the exact disabled empty source advance"
project_config_install_finalize "${SOURCE_ADVANCE_PREFLIGHT}"
jq -e \
  --arg canonical "${CANONICAL_COMMIT}" '
    .commit == $canonical and
    .selectionEnabled == false and
    .executionEnabled == false and
    .workspaces == {}
  ' "${PROJECT_CONFIG}" >/dev/null \
  || fail "installer did not advance the empty registry while keeping it disabled"
ADVANCED_CONFIG_SHA256="$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)"
ADVANCED_REPEAT_PREFLIGHT="$(project_config_install_preflight)"
[[ "${ADVANCED_REPEAT_PREFLIGHT}" == "retain:${ADVANCED_CONFIG_SHA256}" ]] \
  || fail "repeated source advance did not become an exact retained configuration"
project_config_install_finalize "${ADVANCED_REPEAT_PREFLIGHT}"
[[ "$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)" == "${ADVANCED_CONFIG_SHA256}" ]] \
  || fail "repeated source advance rewrote the canonical disabled registry"

write_project_config false false '{}' "${RETAINED_COMMIT}"
SOURCE_ADVANCE_CHANGED_PREFLIGHT="$(project_config_install_preflight)"
cp "${PROJECT_CONFIG}" "${PROJECT_CONFIG}.before-change"
printf '\n' >>"${PROJECT_CONFIG}"
if ( project_config_install_finalize "${SOURCE_ADVANCE_CHANGED_PREFLIGHT}" ) \
    >/dev/null 2>&1; then
  fail "installer advanced a registry that changed after preflight"
fi
mv "${PROJECT_CONFIG}.before-change" "${PROJECT_CONFIG}"

for mutation in selection execution workspace legacy foreign_commit; do
  write_project_config false false '{}' "${RETAINED_COMMIT}"
  case "${mutation}" in
    selection) jq '.selectionEnabled = true' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.rejected" ;;
    execution) jq '.executionEnabled = true' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.rejected" ;;
    workspace) jq '.workspaces.foreign = {}' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.rejected" ;;
    legacy) jq 'del(.attachmentRoot)' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.rejected" ;;
    foreign_commit) jq '.commit = "1111111111111111111111111111111111111111"' \
      "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.rejected" ;;
  esac
  mv "${PROJECT_CONFIG}.rejected" "${PROJECT_CONFIG}"
  if ( project_config_install_preflight ) >/dev/null 2>&1; then
    fail "installer accepted an unsafe source advance transition: ${mutation}"
  fi
done
write_project_config false false '{}' "${CANONICAL_COMMIT}"

if jq '.foreignAuthority = true' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.ambiguous" \
    && mv "${PROJECT_CONFIG}.ambiguous" "${PROJECT_CONFIG}" \
    && ( project_config_install_preflight ) >/dev/null 2>&1; then
  fail "installer preflight accepted ambiguous existing configuration"
fi
write_project_config false false '{}' "${CANONICAL_COMMIT}"
mv "${PROJECT_CONFIG}" "${PROJECT_CONFIG}.retained"
[[ -z "$(project_config_install_preflight)" ]] \
  || fail "installer preflight invented identity for an absent configuration"
project_config_install_finalize ""
jq -e '.selectionEnabled == false and .executionEnabled == false and (.workspaces | length) == 0' \
  "${PROJECT_CONFIG}" >/dev/null || fail "installer did not initialize a new configuration disabled"
rm -f "${PROJECT_CONFIG}.retained"

PROJECT_TRANSITION_TARGET_COMMIT="${CANONICAL_COMMIT}"
jq -n \
  --arg repository "${PROJECT_REPOSITORY}" \
  --arg branch "${PROJECT_TRANSITION_PREDECESSOR_BRANCH}" \
  --arg commit "${PROJECT_TRANSITION_PREDECESSOR_COMMIT}" \
  --arg manifest "${PROJECT_TRANSITION_PREDECESSOR_MANIFEST_SHA256}" \
  --arg runner "${PROJECT_RUNNER}" \
  --arg attachment_root "${ATTACHMENT_ROOT}" '{
    schemaVersion: "project-codex-v1",
    selectionEnabled: false,
    executionEnabled: false,
    projectId: "atenea",
    repository: $repository,
    branch: $branch,
    commit: $commit,
    manifestSha256: $manifest,
    runner: $runner,
    attachmentRoot: $attachment_root,
    workspaces: {}
  }' >"${PROJECT_CONFIG}"
cp "${PROJECT_CONFIG}" "${TEST_ROOT}/transition-predecessor.json"
TRANSITION_CONFIG_SHA256="$(sha256sum "${PROJECT_CONFIG}" | cut -d' ' -f1)"
TRANSITION_PREFLIGHT="$(project_config_install_preflight)"
[[ "${TRANSITION_PREFLIGHT}" == "transition:${TRANSITION_CONFIG_SHA256}" ]] \
  || fail "installer did not recognize the exact empty transition predecessor"
project_config_install_finalize "${TRANSITION_PREFLIGHT}"
jq -e \
  --arg branch "${PROJECT_BRANCH}" \
  --arg commit "${CANONICAL_COMMIT}" \
  --arg manifest "${PROJECT_MANIFEST_SHA256}" '
    .branch == $branch and
    .commit == $commit and
    .manifestSha256 == $manifest and
    .selectionEnabled == false and
    .executionEnabled == false and
    .workspaces == {}
  ' "${PROJECT_CONFIG}" >/dev/null \
  || fail "installer did not atomically migrate the exact empty predecessor"

for mutation in selection workspace commit manifest; do
  cp "${TEST_ROOT}/transition-predecessor.json" "${PROJECT_CONFIG}"
  jq \
    --arg mutation "${mutation}" \
    'if $mutation == "selection" then .selectionEnabled = true
     elif $mutation == "workspace" then .workspaces.foreign = {}
     elif $mutation == "commit" then .commit = "1111111111111111111111111111111111111111"
     else .manifestSha256 = ("1" * 64)
     end' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.rejected"
  mv "${PROJECT_CONFIG}.rejected" "${PROJECT_CONFIG}"
  if ( verify_project_config_transition_predecessor_content ) >/dev/null 2>&1; then
    fail "installer accepted a non-exact transition predecessor: ${mutation}"
  fi
done
write_project_config false false '{}' "${CANONICAL_COMMIT}"

if jq '.attachmentRoots = [.attachmentRoot]' "${PROJECT_CONFIG}" >"${PROJECT_CONFIG}.ambiguous" \
    && mv "${PROJECT_CONFIG}.ambiguous" "${PROJECT_CONFIG}" \
    && ( verify_project_config_content ) >/dev/null 2>&1; then
  fail "ambiguous attachment root authority was accepted"
fi
write_project_config false false '{}' "${CANONICAL_COMMIT}"
SUDOERS_FILE="${TEST_ROOT}/project-runner.sudoers"
printf '%s\n' \
  "atenea-worker ALL=(root) NOPASSWD: ${PROJECT_RUNNER} --config ${PROJECT_CONFIG}" \
  "atenea-worker ALL=(root) NOPASSWD: ${PROJECT_RUNNER} --config ${PROJECT_CONFIG} --reconcile-materializations" \
  >"${SUDOERS_FILE}"
verify_project_runner_sudoers
printf '%s\n' \
  "atenea-worker ALL=(root) NOPASSWD: ${PROJECT_RUNNER} --config ${PROJECT_CONFIG} *" \
  >>"${SUDOERS_FILE}"
if ( verify_project_runner_sudoers ) >/dev/null 2>&1; then
  fail "broad project runner sudo authority was accepted"
fi
PROJECT_SUDOERS_FILE="${SUDOERS_FILE}"
SUDOERS_FILE="${TEST_ROOT}/validation.sudoers"
printf '%s\n' \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} BACKEND_TEST *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} WEB_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} ANDROID_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} PLAYWRIGHT_ACCEPTANCE *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} start BACKEND_TEST *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} inspect BACKEND_TEST *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} cancel BACKEND_TEST *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} start WEB_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} inspect WEB_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} cancel WEB_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} start ANDROID_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} inspect ANDROID_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} cancel ANDROID_BUILD *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} start PLAYWRIGHT_ACCEPTANCE *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} inspect PLAYWRIGHT_ACCEPTANCE *" \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} cancel PLAYWRIGHT_ACCEPTANCE *" \
  >"${SUDOERS_FILE}"
verify_validation_sudoers
printf '%s\n' \
  "atenea-worker ALL=(root) NOPASSWD: ${VALIDATION_MEDIATOR} ARBITRARY *" \
  >>"${SUDOERS_FILE}"
if ( verify_validation_sudoers ) >/dev/null 2>&1; then
  fail "unregistered validation sudo authority was accepted"
fi
SUDOERS_FILE="${PROJECT_SUDOERS_FILE}"
BEFORE="$(git -C "${WORKTREE}" status --porcelain=v1 --untracked-files=all)"
project_retained_draft_register "${SESSION_ID}" "${WORKSPACE_IDENTITY}" "${RETAINED_COMMIT}"
project_retained_draft_register "${SESSION_ID}" "${WORKSPACE_IDENTITY}" "${RETAINED_COMMIT}"
verify_project_config_content
AFTER="$(git -C "${WORKTREE}" status --porcelain=v1 --untracked-files=all)"

[[ "${BEFORE}" == "${AFTER}" ]] || fail "retained draft changed"
jq -e \
  --arg identity "${WORKSPACE_IDENTITY}" \
  --arg retained "${RETAINED_COMMIT}" \
  --arg canonical "${CANONICAL_COMMIT}" \
  '.selectionEnabled == true and
   .executionEnabled == false and
   .commit == $canonical and
   (.workspaces | keys) == [$identity] and
   .workspaces[$identity].canonicalCommit == $retained' \
  "${PROJECT_CONFIG}" >/dev/null || fail "retained registration is not exact"

if ( project_retained_draft_register \
    "${SESSION_ID}" "${WORKSPACE_IDENTITY}" "${CANONICAL_COMMIT}" ) >/dev/null 2>&1; then
  fail "current commit was accepted as retained"
fi

# Exercise the exact enabled WS19-pinned forward-only exception with isolated
# Git, registry and durable-state fixtures. The production constants above are
# asserted before overriding only their values for this synthetic graph.
PROJECT_PINNED_WORKSPACE_SESSION_ID="${SESSION_ID}"
PROJECT_PINNED_WORKSPACE_COMMIT="${RETAINED_COMMIT}"
PROJECT_PINNED_SOURCE_TARGET_COMMIT="${CANONICAL_COMMIT}"
git -C "${WORKTREE}" checkout -q -- tracked.txt
printf 'shell draft\n' >>"${WORKTREE}/${PINNED_DIRTY_RELATIVE_PATH}"
PROJECT_PINNED_DIRTY_PATH="${PINNED_DIRTY_RELATIVE_PATH}"
PROJECT_PINNED_DIRTY_STATUS=" M ${PROJECT_PINNED_DIRTY_PATH}"
PROJECT_PINNED_DIRTY_CONTENT_SHA256="$(
  sha256sum "${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}" | cut -d' ' -f1
)"
PINNED_UPSTREAM="${TEST_ROOT}/pinned-upstream.git"
git init -q --bare "${PINNED_UPSTREAM}"
git --git-dir="${PINNED_UPSTREAM}" fetch -q "${WORKTREE}" \
  "${CANONICAL_COMMIT}:refs/heads/${PROJECT_BRANCH}"
PROJECT_REPOSITORY="file://${PINNED_UPSTREAM}"
git -C "${WORKTREE}" remote set-url origin "${PROJECT_REPOSITORY}"
git --git-dir="${PROJECT_MIRROR}" remote add origin "${PROJECT_REPOSITORY}"
git --git-dir="${PROJECT_MIRROR}" update-ref \
  "${PROJECT_REF}" "${RETAINED_COMMIT}" "${CANONICAL_COMMIT}"

WORKSPACE_RECORD="$(dirname -- "${WORKTREE}")/workspace-v1.json"
ALLOCATION="$(dirname -- "${WORKTREE}")/runtime-allocation-v1.json"
jq -n \
  --arg session "${SESSION_ID}" \
  --arg remote "${PROJECT_REPOSITORY}" \
  --arg mirror "${PROJECT_MIRROR}" \
  --arg worktree "${WORKTREE}" \
  --arg commit "${RETAINED_COMMIT}" '{
    schemaVersion: 1,
    sessionId: $session,
    projectId: "atenea",
    canonicalRemote: $remote,
    baseBranch: "main",
    branch: ("atenea/session-" + $session),
    mirrorPath: $mirror,
    worktreePath: $worktree,
    workerHost: "synthetic-worker",
    state: "ready",
    expectedBaseCommit: $commit,
    headCommit: $commit
  }' >"${WORKSPACE_RECORD}"
PROJECT_PINNED_WORKSPACE_RECORD_SHA256="$(sha256sum "${WORKSPACE_RECORD}" | cut -d' ' -f1)"
jq -n \
  --arg session "${SESSION_ID}" \
  --arg mirror "${PROJECT_MIRROR}" \
  --arg worktree "${WORKTREE}" '{
    schemaVersion: 1,
    sessionId: $session,
    projectId: "atenea",
    branch: ("atenea/session-" + $session),
    mirrorPath: $mirror,
    worktreePath: $worktree,
    runtimeId: ("ws-" + ($session | gsub("-"; ""))),
    manifestRelativePath: "ops/atenea-runtime.json",
    slot: "slot2",
    workloadClass: "heavy",
    state: "allocated"
  }' >"${ALLOCATION}"
PROJECT_PINNED_ALLOCATION_SHA256="$(sha256sum "${ALLOCATION}" | cut -d' ' -f1)"
PINNED_WORKSPACES="$(jq -cn \
  --arg identity "${WORKSPACE_IDENTITY}" \
  --arg session "${SESSION_ID}" \
  --arg worktree "${WORKTREE}" \
  --arg allocation "${PROJECT_PINNED_ALLOCATION_SHA256}" \
  --arg commit "${RETAINED_COMMIT}" '{
    ($identity): {
      sessionId: $session,
      worktree: $worktree,
      allocationSha256: $allocation,
      canonicalCommit: $commit
    }
  }')"
write_project_config true true "${PINNED_WORKSPACES}" "${RETAINED_COMMIT}"

STATE_DIR="${TEST_ROOT}/srv/atenea/worker/agent-runs-v1"
VALIDATION_JOURNAL_ROOT="${TEST_ROOT}/srv/atenea/worker/validation-broker-v1"
mkdir -p "${STATE_DIR}" "${VALIDATION_JOURNAL_ROOT}"
jq -n '{
  protocol: "agent-run-worker/v1",
  executions: {terminal: {status: "SUCCEEDED"}},
  validations: {terminal: {state: "SUCCEEDED"}}
}' >"${STATE_DIR}/executions.json"
mkdir -p "${VALIDATION_JOURNAL_ROOT}/${SESSION_ID}/terminal"
jq -n '{state: "SUCCEEDED"}' \
  >"${VALIDATION_JOURNAL_ROOT}/${SESSION_ID}/terminal/operation-v1.json"

PINNED_REGISTRY_PREDECESSOR="${TEST_ROOT}/pinned-registry-predecessor.json"
cp "${PROJECT_CONFIG}" "${PINNED_REGISTRY_PREDECESSOR}"
PINNED_ENTRY_BEFORE="$(jq -c --arg identity "${WORKSPACE_IDENTITY}" \
  '.workspaces[$identity]' "${PROJECT_CONFIG}")"
PINNED_RECORD_SHA_BEFORE="$(sha256sum "${WORKSPACE_RECORD}" | cut -d' ' -f1)"
PINNED_ALLOCATION_SHA_BEFORE="$(sha256sum "${ALLOCATION}" | cut -d' ' -f1)"
PINNED_HEAD_BEFORE="$(git -C "${WORKTREE}" rev-parse HEAD)"
PINNED_INDEX_BEFORE="$(git -C "${WORKTREE}" write-tree)"
PINNED_DIRTY_BEFORE="$(git -C "${WORKTREE}" status --porcelain=v1 --untracked-files=all)"
PINNED_DIRTY_SHA_BEFORE="$(sha256sum "${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}" | cut -d' ' -f1)"
PINNED_STATE_SHA_BEFORE="$(sha256sum "${STATE_DIR}/executions.json" | cut -d' ' -f1)"
PINNED_JOURNAL_SHA_BEFORE="$(
  sha256sum "${VALIDATION_JOURNAL_ROOT}/${SESSION_ID}/terminal/operation-v1.json" | cut -d' ' -f1
)"
PINNED_PREFLIGHT="$(project_config_install_preflight)"
[[ "${PINNED_PREFLIGHT}" == \
    "pinned-source-advance:$(sha256sum "${PINNED_REGISTRY_PREDECESSOR}" | cut -d' ' -f1):${RETAINED_COMMIT}:${CANONICAL_COMMIT}" ]] \
  || fail "installer did not recognize the exact WS19 pinned source advance"
project_config_install_finalize "${PINNED_PREFLIGHT}"

PINNED_REGISTRY_SUCCESSOR="${TEST_ROOT}/pinned-registry-successor.json"
cp "${PROJECT_CONFIG}" "${PINNED_REGISTRY_SUCCESSOR}"
jq -e \
  --arg target "${CANONICAL_COMMIT}" '
    .commit == $target and .selectionEnabled == true and
    .executionEnabled == true and (.workspaces | length) == 1
  ' "${PROJECT_CONFIG}" >/dev/null \
  || fail "pinned source advance did not preserve enabled registry state"
[[ "$(jq -c --arg identity "${WORKSPACE_IDENTITY}" '.workspaces[$identity]' \
      "${PROJECT_CONFIG}")" == "${PINNED_ENTRY_BEFORE}" \
    && "$(sha256sum "${WORKSPACE_RECORD}" | cut -d' ' -f1)" == "${PINNED_RECORD_SHA_BEFORE}" \
    && "$(sha256sum "${ALLOCATION}" | cut -d' ' -f1)" == "${PINNED_ALLOCATION_SHA_BEFORE}" \
    && "$(git -C "${WORKTREE}" rev-parse HEAD)" == "${PINNED_HEAD_BEFORE}" \
    && "$(git -C "${WORKTREE}" write-tree)" == "${PINNED_INDEX_BEFORE}" \
    && "$(sha256sum "${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}" | cut -d' ' -f1)" == "${PINNED_DIRTY_SHA_BEFORE}" \
    && "$(sha256sum "${STATE_DIR}/executions.json" | cut -d' ' -f1)" == "${PINNED_STATE_SHA_BEFORE}" \
    && "$(sha256sum "${VALIDATION_JOURNAL_ROOT}/${SESSION_ID}/terminal/operation-v1.json" | cut -d' ' -f1)" == "${PINNED_JOURNAL_SHA_BEFORE}" \
    && "$(git -C "${WORKTREE}" status --porcelain=v1 --untracked-files=all)" == "${PINNED_DIRTY_BEFORE}" ]] \
  || fail "pinned WS19 resources changed during source advance"
sed -E 's/("commit"[[:space:]]*:[[:space:]]*")'"${CANONICAL_COMMIT}"'(\")/\1'"${RETAINED_COMMIT}"'\2/' \
  "${PINNED_REGISTRY_SUCCESSOR}" >"${PROJECT_CONFIG}.restored-comparison"
cmp -s "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}.restored-comparison" \
  || fail "pinned source advance changed registry bytes outside commit"
rm -f "${PROJECT_CONFIG}.restored-comparison"

# New v4 requests select the advanced global commit, while an old legacy
# request carrying the retained workspace commit fails the existing exact
# canonical-equality gate before creating any role worktree.
jq -e --arg target "${CANONICAL_COMMIT}" \
  '.selectionEnabled == true and .executionEnabled == true and .commit == $target' \
  "${PROJECT_CONFIG}" >/dev/null || fail "new v4 source is not selectable"
LEGACY_ROOT="${TEST_ROOT}/legacy-canonical-mismatch"
mkdir -p "${LEGACY_ROOT}/atenea.git" \
  "${LEGACY_ROOT}/sessions/${SESSION_ID}/atenea"
cp "${PROJECT_CONFIG}" "${LEGACY_ROOT}/project.json"
if ATENEA_MULTI_REPO_TEST_MODE=1 ATENEA_MULTI_REPO_TEST_ROOT="${LEGACY_ROOT}" \
    "${SCRIPT_DIR}/atenea-multi-repository-v1.sh" ensure \
    "${SESSION_ID}" "22222222-2222-4222-8222-222222222222" \
    "${RETAINED_COMMIT}" >/dev/null 2>&1; then
  fail "legacy flow accepted a pinned workspace canonical mismatch"
fi

# The existing rollback primitives can restore exact predecessor bytes and the
# canonical ref without touching the worktree or deleting the fetched object.
cp "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}"
git --git-dir="${PROJECT_MIRROR}" update-ref \
  "${PROJECT_REF}" "${RETAINED_COMMIT}" "${CANONICAL_COMMIT}"
cmp -s "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}" \
  || fail "rollback did not restore exact registry predecessor bytes"
[[ "$(git --git-dir="${PROJECT_MIRROR}" rev-parse "${PROJECT_REF}^{commit}")" \
      == "${RETAINED_COMMIT}" \
    && "$(git --git-dir="${PROJECT_MIRROR}" cat-file -t "${CANONICAL_COMMIT}")" == commit \
    && "$(git -C "${WORKTREE}" rev-parse HEAD)" == "${PINNED_HEAD_BEFORE}" \
    && "$(git -C "${WORKTREE}" write-tree)" == "${PINNED_INDEX_BEFORE}" \
    && "$(sha256sum "${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}" | cut -d' ' -f1)" == "${PINNED_DIRTY_SHA_BEFORE}" \
    && "$(git -C "${WORKTREE}" status --porcelain=v1 --untracked-files=all)" == "${PINNED_DIRTY_BEFORE}" ]] \
  || fail "rollback changed the worktree or removed the fetched source object"

assert_pinned_preflight_rejected() {
  local description="$1"
  if ( project_config_install_preflight ) >/dev/null 2>&1; then
    fail "unsafe pinned source advance was accepted: ${description}"
  fi
}

jq --arg identity "remote:ax42-01:work-session:33333333-3333-4333-8333-333333333333" \
  '.workspaces[$identity] = (.workspaces | to_entries[0].value)' \
  "${PINNED_REGISTRY_PREDECESSOR}" >"${PROJECT_CONFIG}"
assert_pinned_preflight_rejected "more than one legacy workspace"
jq '.workspaces = {"foreign": (.workspaces | to_entries[0].value)}' \
  "${PINNED_REGISTRY_PREDECESSOR}" >"${PROJECT_CONFIG}"
assert_pinned_preflight_rejected "foreign workspace"
cp "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}"
git -C "${WORKTREE}" checkout -q -- "${PROJECT_PINNED_DIRTY_PATH}"
assert_pinned_preflight_rejected "clean retained workspace"
printf 'shell draft\n' >>"${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}"
cp "${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}" "${TEST_ROOT}/pinned-dirty.valid"
printf 'different byte\n' >>"${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}"
assert_pinned_preflight_rejected "same dirty path with different content"
mv "${TEST_ROOT}/pinned-dirty.valid" "${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}"
REVIEWED_DIRTY_CONTENT_SHA256="${PROJECT_PINNED_DIRTY_CONTENT_SHA256}"
PROJECT_PINNED_DIRTY_CONTENT_SHA256="$(printf '0%.0s' {1..64})"
assert_pinned_preflight_rejected "same dirty status and path with a different content fingerprint"
PROJECT_PINNED_DIRTY_CONTENT_SHA256="${REVIEWED_DIRTY_CONTENT_SHA256}"

git -C "${WORKTREE}" checkout -q -- "${PROJECT_PINNED_DIRTY_PATH}"
printf 'screen draft\n' >>"${WORKTREE}/${PINNED_OLD_DIRTY_RELATIVE_PATH}"
assert_pinned_preflight_rejected "old incorrect dirty path"
git -C "${WORKTREE}" checkout -q -- "${PINNED_OLD_DIRTY_RELATIVE_PATH}"
printf 'other draft\n' >>"${WORKTREE}/tracked.txt"
assert_pinned_preflight_rejected "other dirty path"
git -C "${WORKTREE}" checkout -q -- tracked.txt

printf 'shell draft\n' >>"${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}"
printf 'other draft\n' >>"${WORKTREE}/tracked.txt"
assert_pinned_preflight_rejected "unexpected dirty count or pattern"
git -C "${WORKTREE}" checkout -q -- tracked.txt

ORPHAN_TREE="$(git -C "${WORKTREE}" write-tree)"
ORPHAN_COMMIT="$(printf 'orphan target\n' | \
  git -C "${WORKTREE}" -c user.name=Test -c user.email=test@example.invalid \
    commit-tree "${ORPHAN_TREE}")"
REVIEWED_TARGET="${PROJECT_PINNED_SOURCE_TARGET_COMMIT}"
PROJECT_PINNED_SOURCE_TARGET_COMMIT="${ORPHAN_COMMIT}"
git --git-dir="${PINNED_UPSTREAM}" fetch -q "${WORKTREE}" \
  "+${ORPHAN_COMMIT}:refs/heads/${PROJECT_BRANCH}"
assert_pinned_preflight_rejected "non-descendant target"
PROJECT_PINNED_SOURCE_TARGET_COMMIT="${REVIEWED_TARGET}"
git --git-dir="${PINNED_UPSTREAM}" update-ref \
  "refs/heads/${PROJECT_BRANCH}" "${CANONICAL_COMMIT}" "${ORPHAN_COMMIT}"

git -C "${WORKTREE}" reset -q --hard "${CANONICAL_COMMIT}"
assert_pinned_preflight_rejected "HEAD differs from canonicalCommit"
git -C "${WORKTREE}" reset -q --hard "${RETAINED_COMMIT}"
printf 'shell draft\n' >>"${WORKTREE}/${PROJECT_PINNED_DIRTY_PATH}"
printf 'invalid manifest\n' >"${WORKTREE}/ops/atenea-runtime.json"
assert_pinned_preflight_rejected "invalid manifest fingerprint"
printf '{}\n' >"${WORKTREE}/ops/atenea-runtime.json"

cp "${ALLOCATION}" "${ALLOCATION}.valid"
printf '\n' >>"${ALLOCATION}"
assert_pinned_preflight_rejected "changed allocation fingerprint"
mv "${ALLOCATION}.valid" "${ALLOCATION}"

cp "${ALLOCATION}" "${ALLOCATION}.valid"
jq '.projectId = "foreign"' "${ALLOCATION}.valid" >"${ALLOCATION}"
MUTATED_ALLOCATION_SHA="$(sha256sum "${ALLOCATION}" | cut -d' ' -f1)"
PROJECT_PINNED_ALLOCATION_SHA256="${MUTATED_ALLOCATION_SHA}"
jq --arg identity "${WORKSPACE_IDENTITY}" --arg sha "${MUTATED_ALLOCATION_SHA}" \
  '.workspaces[$identity].allocationSha256 = $sha' \
  "${PINNED_REGISTRY_PREDECESSOR}" >"${PROJECT_CONFIG}"
assert_pinned_preflight_rejected "incompatible allocation"
mv "${ALLOCATION}.valid" "${ALLOCATION}"
PROJECT_PINNED_ALLOCATION_SHA256="${PINNED_ALLOCATION_SHA_BEFORE}"

cp "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}"
cp "${WORKSPACE_RECORD}" "${WORKSPACE_RECORD}.valid"
printf '\n' >>"${WORKSPACE_RECORD}"
assert_pinned_preflight_rejected "changed workspace record fingerprint"
mv "${WORKSPACE_RECORD}.valid" "${WORKSPACE_RECORD}"

cp "${WORKSPACE_RECORD}" "${WORKSPACE_RECORD}.valid"
jq '.headCommit = null' "${WORKSPACE_RECORD}.valid" >"${WORKSPACE_RECORD}"
assert_pinned_preflight_rejected "invalid workspace record"
mv "${WORKSPACE_RECORD}.valid" "${WORKSPACE_RECORD}"

git -C "${WORKTREE}" remote set-url origin "file://${TEST_ROOT}/foreign"
assert_pinned_preflight_rejected "unexpected workspace remote"
git -C "${WORKTREE}" remote set-url origin "${PROJECT_REPOSITORY}"
git --git-dir="${PROJECT_MIRROR}" remote set-url origin "file://${TEST_ROOT}/foreign"
assert_pinned_preflight_rejected "unexpected mirror remote"
git --git-dir="${PROJECT_MIRROR}" remote set-url origin "${PROJECT_REPOSITORY}"

jq '.executions.active = {status: "RUNNING"}' \
  "${STATE_DIR}/executions.json" >"${STATE_DIR}/executions.changed"
mv "${STATE_DIR}/executions.changed" "${STATE_DIR}/executions.json"
assert_pinned_preflight_rejected "non-terminal AgentRun"
jq 'del(.executions.active) | .validations.active = {state: "QUEUED"}' \
  "${STATE_DIR}/executions.json" >"${STATE_DIR}/executions.changed"
mv "${STATE_DIR}/executions.changed" "${STATE_DIR}/executions.json"
assert_pinned_preflight_rejected "non-terminal validation"
jq 'del(.validations.active)' "${STATE_DIR}/executions.json" \
  >"${STATE_DIR}/executions.changed"
mv "${STATE_DIR}/executions.changed" "${STATE_DIR}/executions.json"
jq -n '{state: "RUNNING"}' \
  >"${VALIDATION_JOURNAL_ROOT}/${SESSION_ID}/terminal/operation-v1.json"
assert_pinned_preflight_rejected "non-terminal validation journal"
jq -n '{state: "SUCCEEDED"}' \
  >"${VALIDATION_JOURNAL_ROOT}/${SESSION_ID}/terminal/operation-v1.json"

cp "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}"
PINNED_CAS_PREFLIGHT="$(project_config_install_preflight)"
printf '\n' >>"${PROJECT_CONFIG}"
if ( project_config_install_finalize "${PINNED_CAS_PREFLIGHT}" ) >/dev/null 2>&1; then
  fail "pinned source advance ignored registry compare-and-swap"
fi
[[ "$(git --git-dir="${PROJECT_MIRROR}" rev-parse "${PROJECT_REF}^{commit}")" \
    == "${RETAINED_COMMIT}" ]] || fail "failed registry CAS changed canonical ref"

cp "${PINNED_REGISTRY_PREDECESSOR}" "${PROJECT_CONFIG}"
PINNED_FINAL_PREFLIGHT="$(project_config_install_preflight)"
project_config_install_finalize "${PINNED_FINAL_PREFLIGHT}"
cmp -s "${PINNED_REGISTRY_SUCCESSOR}" "${PROJECT_CONFIG}" \
  || fail "repeated pinned transition did not reproduce exact successor bytes"
PINNED_REPEAT_PREFLIGHT="$(project_config_install_preflight)"
[[ "${PINNED_REPEAT_PREFLIGHT}" == \
    "retain:$(sha256sum "${PINNED_REGISTRY_SUCCESSOR}" | cut -d' ' -f1)" ]] \
  || fail "advanced pinned registry was not recognized as exact retained state"
project_config_install_finalize "${PINNED_REPEAT_PREFLIGHT}"
cmp -s "${PINNED_REGISTRY_SUCCESSOR}" "${PROJECT_CONFIG}" \
  || fail "advanced pinned registry was rewritten on repeated install"

CONTROL_PLANE_IP=100.64.0.10
ATTACHMENT_ROOT="${TEST_ROOT}/retained"
MATERIALIZATION_PARENT="${TEST_ROOT}/materialization-parent"
MATERIALIZATION_ROOT="${MATERIALIZATION_PARENT}/codex-images"
mkdir -p "${ATTACHMENT_ROOT}" "${MATERIALIZATION_ROOT}"
chmod 0700 "${ATTACHMENT_ROOT}"
chmod 0750 "${MATERIALIZATION_PARENT}"
chmod 0710 "${MATERIALIZATION_ROOT}"
if ( verify_attachment_root ) >/dev/null 2>&1; then
  fail "foreign-owned attachment root was accepted"
fi
if ( verify_materialization_parent ) >/dev/null 2>&1; then
  fail "foreign-owned materialization parent was accepted"
fi
if ( verify_materialization_root ) >/dev/null 2>&1; then
  fail "foreign-owned materialization root was accepted"
fi
AMBIGUOUS_TARGET="${TEST_ROOT}/ambiguous-target"
mkdir -p "${AMBIGUOUS_TARGET}"
MATERIALIZATION_ROOT="${TEST_ROOT}/ambiguous-link"
ln -s "${AMBIGUOUS_TARGET}" "${MATERIALIZATION_ROOT}"
if ( verify_materialization_root ) >/dev/null 2>&1; then
  fail "symlinked materialization root was accepted"
fi

MATERIALIZATION_PARENT="${TEST_ROOT}/prepared-parent"
MATERIALIZATION_ROOT="${MATERIALIZATION_PARENT}/codex-images"
INSTALL_CALLS=()
install_exact_directory() {
  INSTALL_CALLS+=("$1:$2:$3:$4")
  mkdir -p "$4"
  chmod "$3" "$4"
}
PREPARE_PARENT_CHECKS=0
PREPARE_ROOT_CHECKS=0
verify_materialization_parent() {
  [[ -d "${MATERIALIZATION_PARENT}" && ! -L "${MATERIALIZATION_PARENT}" ]] \
    || fail "prepared parent is absent"
  PREPARE_PARENT_CHECKS=$((PREPARE_PARENT_CHECKS + 1))
}
verify_materialization_root() {
  [[ -d "${MATERIALIZATION_ROOT}" && ! -L "${MATERIALIZATION_ROOT}" ]] \
    || fail "prepared root is absent"
  PREPARE_ROOT_CHECKS=$((PREPARE_ROOT_CHECKS + 1))
}
prepare_materialization_root
prepare_materialization_root
[[ "${#INSTALL_CALLS[@]}" -eq 2 \
    && "${INSTALL_CALLS[0]}" == "root:atenea:0750:${MATERIALIZATION_PARENT}" \
    && "${INSTALL_CALLS[1]}" == "root:atenea:0710:${MATERIALIZATION_ROOT}" ]] \
  || fail "materialization preparer created anything beyond the exact absent paths"
[[ "${PREPARE_PARENT_CHECKS}" -eq 3 && "${PREPARE_ROOT_CHECKS}" -eq 3 ]] \
  || fail "materialization preparer did not reverify existing exact paths"

MATERIALIZATION_PARENT="${TEST_ROOT}/materialization-parent"
MATERIALIZATION_ROOT="${MATERIALIZATION_PARENT}/codex-images"
printf 'retained-sentinel\n' >"${ATTACHMENT_ROOT}/sentinel"
printf 'parent-sentinel\n' >"${MATERIALIZATION_PARENT}/sentinel"
printf 'materialized-sentinel\n' >"${MATERIALIZATION_ROOT}/sentinel"
BEFORE_BOUNDARIES="$(sha256sum "${ATTACHMENT_ROOT}/sentinel" \
  "${MATERIALIZATION_PARENT}/sentinel" "${MATERIALIZATION_ROOT}/sentinel")"
BOUNDARY_CHECKS=0
verify_attachment_root() { BOUNDARY_CHECKS=$((BOUNDARY_CHECKS + 1)); }
verify_materialization_parent() { BOUNDARY_CHECKS=$((BOUNDARY_CHECKS + 1)); }
verify_materialization_root() { BOUNDARY_CHECKS=$((BOUNDARY_CHECKS + 1)); }
SYSTEMCTL_CALLS=()
systemctl() { SYSTEMCTL_CALLS+=("$*"); }
UFW_CALLS=()
ufw() {
  if [[ "${1:-}" == status ]]; then
    printf '%s\n' "${PORT}/tcp on tailscale0 ALLOW IN ${CONTROL_PLANE_IP}"
  else
    UFW_CALLS+=("$*")
  fi
}
rollback_endpoint
AFTER_BOUNDARIES="$(sha256sum "${ATTACHMENT_ROOT}/sentinel" \
  "${MATERIALIZATION_PARENT}/sentinel" "${MATERIALIZATION_ROOT}/sentinel")"
[[ "${BOUNDARY_CHECKS}" -eq 6 ]] || fail "rollback did not verify all boundaries before and after"
[[ "${#SYSTEMCTL_CALLS[@]}" -eq 2 \
    && "${SYSTEMCTL_CALLS[0]}" == "disable --now ${SERVICE}" \
    && "${SYSTEMCTL_CALLS[1]}" == "stop ${MATERIALIZATION_SERVICE}" ]] \
  || fail "rollback service scope is not exact"
[[ "${#UFW_CALLS[@]}" -eq 1 ]] || fail "rollback firewall scope is not exact"
[[ "${BEFORE_BOUNDARIES}" == "${AFTER_BOUNDARIES}" ]] \
  || fail "rollback changed retained or materialized boundary content"

printf 'agent-run worker installer, sandbox and rollback tests passed\n'
