#!/usr/bin/env bash
set -euo pipefail
export GIT_OPTIONAL_LOCKS=0

ACTION="${1:-}"
CONTROL_PLANE_IP="${ATENEA_CONTROL_PLANE_TAILSCALE_IP:-}"
WORKER_ID="${ATENEA_AGENT_RUN_WORKER_ID:-ax42-01}"
PORT="${ATENEA_AGENT_RUN_WORKER_PORT:-8787}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="atenea-agent-run-worker-v1.service"
MATERIALIZATION_SERVICE="atenea-codex-images-v1.service"
PROGRAM="/usr/local/libexec/atenea/agent-run-worker-v1.py"
DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR="/usr/local/libexec/atenea/development-change-workspace-v1.py"
PROJECT_RUNNER="/usr/local/libexec/atenea/project-codex-runner-v1.py"
BEAUTIPS_PROJECT_RUNNER="/usr/local/libexec/atenea/beautips-project-codex-runner-v1.py"
VALIDATION_MEDIATOR="/usr/local/libexec/atenea/atenea-validation-v1.py"
VALIDATION_JOURNAL_ROOT="/srv/atenea/worker/validation-broker-v1"
PLAYWRIGHT_CHECK="/usr/local/libexec/atenea/atenea-playwright-validation-v1.js"
ROLE_MEDIATOR="/usr/local/libexec/atenea/atenea-multi-repository-v1.sh"
WORKSPACE_ACTIVATOR="/usr/local/libexec/atenea/atenea-workspace-activation-v1.sh"
WORKSPACE_RELEASER="/usr/local/libexec/atenea/atenea-workspace-release-v1.py"
WORKSPACE_ACTIVATION_SUDOERS="/etc/sudoers.d/92-atenea-routing-activation-v1"
WORKSPACE_ACTIVATION_BUNDLE="/srv/atenea/worker/workspace-v1/ops/worker"
WORKSPACE_RELEASE_ROOT="/srv/atenea/worker/workspace-release-v1/sessions"
CODEX_UPDATE_MEDIATOR="/usr/local/libexec/atenea/codex-release-stage-v1.py"
CODEX_ACTIVATE_MEDIATOR="/usr/local/libexec/atenea/codex-release-activate-v1.py"
CODEX_RESTART_SCHEDULER="/usr/local/libexec/atenea/codex-release-restart-v1.sh"
CODEX_UPDATE_REGISTRY="/etc/atenea-worker/codex-release-stage-v1.json"
CODEX_RELEASE_ROOT="/srv/atenea/worker/codex-releases-v1"
PLATFORM_INSTRUCTIONS="/usr/local/share/atenea/codex-platform-instructions-v1.md"
INSTALLER="/usr/local/libexec/atenea/install-agent-run-worker-v1.sh"
ENV_FILE="/etc/atenea-worker/agent-run-worker-v1.env"
TOKEN_FILE="/etc/atenea-worker/agent-run-worker-v1.token"
PROJECT_CONFIG="/etc/atenea-worker/project-codex-v1.json"
SUDOERS_FILE="/etc/sudoers.d/atenea-project-codex-v1"
STATE_DIR="/srv/atenea/worker/agent-runs-v1"
DEVELOPMENT_CHANGE_WORKSPACE_ROOT="/srv/atenea/workspaces/changes"
ATTACHMENT_ROOT="/srv/atenea/attachments-v1"
MATERIALIZATION_ROOT="/run/atenea/codex-images"
MATERIALIZATION_PARENT="/run/atenea"
PROJECT_REPOSITORY="https://github.com/jlnieto/atenea.git"
PROJECT_BRANCH="main"
PROJECT_MANIFEST_SHA256="327a0c521017109d7c0067a11e7d8c3ad2079de4ea78d28296848f9de39c164b"
PROJECT_TRANSITION_PREDECESSOR_BRANCH="feature/actualizar-conversacion-en-web"
PROJECT_TRANSITION_PREDECESSOR_COMMIT="8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d"
PROJECT_TRANSITION_PREDECESSOR_MANIFEST_SHA256="3b26e1899a06993bee69ac596e7cb69b6200a37d063d98203ad308058c91bfa3"
PROJECT_TRANSITION_TARGET_COMMIT="615e539d1f2622a4ac2568ba7697b876d49ae33e"
PROJECT_MIRROR="/srv/atenea/repositories/atenea.git"
PROJECT_REF="refs/remotes/origin/${PROJECT_BRANCH}"
PROJECT_WORKSPACES_ROOT="/srv/atenea/workspaces/sessions"
SERVICE_TEMPLATE_SHA256="d59c5940d9810a30db5000dec26d78d91ab21f15e2b735a4db5760e16da53356"
MATERIALIZATION_SERVICE_TEMPLATE_SHA256="df3a3fa0d75472d8aaf6847c58b4bace6e7ed2f7d532f1f86c8c562cda2387a6"
PROGRAM_SHA256="65a6f6df558c94360988fb110215ccd8d2a5f5cfbb63655ff998a703f2489d31"
VALIDATION_MEDIATOR_SHA256="e7339c3dc68050b3315b70649bfaee0399d4d2b34c4f52bb26dcd036d3eb9d7d"
PLAYWRIGHT_CHECK_SHA256="4196efbfa306edd95955683f1123cffa96645938441f81717ad9032052d68ed9"
DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR_SHA256="7d42b734b76adbfd77538404faaba5502591c152bf1977852e503d0bde16a1a3"
PROJECT_RUNNER_SHA256="0bf1b1b137a4dc2baaf29ca6bd607532d95c07b1736b4e40bce6b31257c3dbf5"
BEAUTIPS_PROJECT_RUNNER_SHA256="e3d5402fbdb4245ddfa47b1a190f8be5fa2599c81b3ab6206f70cab66bad138f"
BEAUTIPS_PROJECT_RUNNER_PREDECESSOR_SHA256="60d54f1e6e6eaf1edea43e9bf3b0800226a413b4feee5a59ce8152954d97b983"
PLATFORM_INSTRUCTIONS_SHA256="44c578a286eb50b35612be0b6c38d59a503e6fee1ecf6cd0339415af018cdf0d"
WORKSPACE_ACTIVATOR_SHA256="5ef544c478c17a0ae6ae88586915185572721ca89dc48dbbf15b65ad417aa889"
WORKSPACE_RELEASER_SHA256="095e0db0ee77814f59f12907d003bad462c64c57aa8b85137e9c142147416de3"
SESSION_WORKSPACE_SHA256="3e41ae7f218f360920bed7cd4b2d75cab5396bb07649635694db3271b12d2ffe"
RUNTIME_ADMISSION_SHA256="a81366d3495bb2a7bf4702e9ea934a74e9b3edb30f728926e655a5c0a6a9f7ce"
SESSION_ALLOCATION_SHA256="2efceeaaba78b349f1d6aa79bfba5d908d397a9e3a480cfa3b100bde52fb99d7"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_root() {
  [[ "$(id -u)" -eq 0 ]] || fail "run this action as root"
}

install_exact_directory() {
  local owner="$1"
  local group="$2"
  local mode="$3"
  local path="$4"
  install -d -o "$owner" -g "$group" -m "$mode" "$path"
  # A newly created child inherits setgid from /srv/atenea/worker.  The
  # reviewed verifier intentionally requires the declared exact mode, so clear
  # inherited special bits after creation instead of weakening verification.
  chmod "$mode" "$path"
  chmod u-s,g-s,o-t "$path"
}

verify_attachment_root() {
  [[ -d "$ATTACHMENT_ROOT" && ! -L "$ATTACHMENT_ROOT" ]] \
    || fail "attachment root is absent or ambiguous"
  [[ "$(stat -c '%a:%U:%G' "$ATTACHMENT_ROOT")" == "700:atenea-worker:atenea" ]] \
    || fail "attachment root ownership or mode is invalid"
}

verify_materialization_root() {
  [[ -d "$MATERIALIZATION_ROOT" && ! -L "$MATERIALIZATION_ROOT" ]] \
    || fail "materialization root is absent or ambiguous"
  [[ "$(stat -c '%a:%U:%G' "$MATERIALIZATION_ROOT")" == "710:root:atenea" ]] \
    || fail "materialization root ownership or mode is invalid"
}

verify_materialization_parent() {
  [[ -d "$MATERIALIZATION_PARENT" && ! -L "$MATERIALIZATION_PARENT" ]] \
    || fail "materialization parent is absent or ambiguous"
  [[ "$(stat -c '%a:%U:%G' "$MATERIALIZATION_PARENT")" == "750:root:atenea" ]] \
    || fail "materialization parent ownership or mode is invalid"
}

verify_development_change_workspace_root() {
  [[ -d "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT" \
      && ! -L "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT" \
      && "$(stat -c '%a:%U:%G' "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT")" \
        == "2770:atenea-worker:atenea" ]] \
    || fail "development-change workspace root ownership or mode is invalid"
}

prepare_development_change_workspace_root() {
  if [[ -e "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT" \
      || -L "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT" ]]; then
    verify_development_change_workspace_root
    return
  fi
  install -d -o atenea-worker -g atenea -m 2770 \
    "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT"
  chmod 2770 "$DEVELOPMENT_CHANGE_WORKSPACE_ROOT"
  verify_development_change_workspace_root
}

prepare_materialization_root() {
  require_root
  if [[ -e "$MATERIALIZATION_PARENT" || -L "$MATERIALIZATION_PARENT" ]]; then
    verify_materialization_parent
  else
    install_exact_directory root atenea 0750 "$MATERIALIZATION_PARENT"
  fi
  if [[ -e "$MATERIALIZATION_ROOT" || -L "$MATERIALIZATION_ROOT" ]]; then
    verify_materialization_root
  else
    install_exact_directory root atenea 0710 "$MATERIALIZATION_ROOT"
  fi
  verify_materialization_parent
  verify_materialization_root
}

verify_project_runner_sudoers() {
  mapfile -t project_runner_rules < <(grep -F -- "$PROJECT_RUNNER" "$SUDOERS_FILE")
  [[ "${#project_runner_rules[@]}" -eq 2 \
      && "${project_runner_rules[0]}" == "atenea-worker ALL=(root) NOPASSWD: $PROJECT_RUNNER --config $PROJECT_CONFIG" \
      && "${project_runner_rules[1]}" == "atenea-worker ALL=(root) NOPASSWD: $PROJECT_RUNNER --config $PROJECT_CONFIG --reconcile-materializations" ]] \
    || fail "project runner sudo authority is not exact"
}

verify_validation_sudoers() {
  mapfile -t validation_rules < <(grep -F -- "$VALIDATION_MEDIATOR" "$SUDOERS_FILE")
  [[ "${#validation_rules[@]}" -eq 16 \
      && "${validation_rules[0]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR BACKEND_TEST *" \
      && "${validation_rules[1]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR WEB_BUILD *" \
      && "${validation_rules[2]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR ANDROID_BUILD *" \
      && "${validation_rules[3]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR PLAYWRIGHT_ACCEPTANCE *" \
      && "${validation_rules[4]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR start BACKEND_TEST *" \
      && "${validation_rules[5]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR inspect BACKEND_TEST *" \
      && "${validation_rules[6]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR cancel BACKEND_TEST *" \
      && "${validation_rules[7]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR start WEB_BUILD *" \
      && "${validation_rules[8]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR inspect WEB_BUILD *" \
      && "${validation_rules[9]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR cancel WEB_BUILD *" \
      && "${validation_rules[10]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR start ANDROID_BUILD *" \
      && "${validation_rules[11]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR inspect ANDROID_BUILD *" \
      && "${validation_rules[12]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR cancel ANDROID_BUILD *" \
      && "${validation_rules[13]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR start PLAYWRIGHT_ACCEPTANCE *" \
      && "${validation_rules[14]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR inspect PLAYWRIGHT_ACCEPTANCE *" \
      && "${validation_rules[15]}" == "atenea-worker ALL=(root) NOPASSWD: $VALIDATION_MEDIATOR cancel PLAYWRIGHT_ACCEPTANCE *" ]] \
    || fail "validation sudo authority is not exact"
}

verify_beautips_project_runner_file_identity() {
  [[ -f "$BEAUTIPS_PROJECT_RUNNER" && ! -L "$BEAUTIPS_PROJECT_RUNNER" \
      && "$(stat -c '%a:%U:%G' "$BEAUTIPS_PROJECT_RUNNER")" == "755:root:root" ]] \
    || fail "existing Beautips project runner identity is invalid"
}

verify_beautips_project_runner_upgrade() {
  verify_beautips_project_runner_file_identity
  local digest
  digest="$(sha256sum "$BEAUTIPS_PROJECT_RUNNER" | cut -d' ' -f1)"
  [[ "$digest" == "$BEAUTIPS_PROJECT_RUNNER_PREDECESSOR_SHA256" \
      || "$digest" == "$BEAUTIPS_PROJECT_RUNNER_SHA256" ]] \
    || fail "existing Beautips project runner is not an accepted predecessor"
}

workspace_activation_sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "$WORKSPACE_ACTIVATOR"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s\n' "$WORKSPACE_RELEASER"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-capacity-owner\n' "$WORKSPACE_RELEASER"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-release-preflight\n' "$WORKSPACE_RELEASER"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-unactivated\n' "$WORKSPACE_RELEASER"
}

verify_workspace_activation_dependency() {
  [[ -f "$WORKSPACE_ACTIVATOR" && ! -L "$WORKSPACE_ACTIVATOR" \
      && "$(stat -c '%a:%U:%G' "$WORKSPACE_ACTIVATOR")" == "755:root:root" \
      && "$(sha256sum "$WORKSPACE_ACTIVATOR" | cut -d' ' -f1)" \
        == "$WORKSPACE_ACTIVATOR_SHA256" ]] \
    || fail "Atenea workspace activator differs from the reviewed source"
  [[ -f "$WORKSPACE_RELEASER" && ! -L "$WORKSPACE_RELEASER" \
      && "$(stat -c '%a:%U:%G' "$WORKSPACE_RELEASER")" == "755:root:root" \
      && "$(sha256sum "$WORKSPACE_RELEASER" | cut -d' ' -f1)" \
        == "$WORKSPACE_RELEASER_SHA256" ]] \
    || fail "Atenea workspace releaser differs from the reviewed source"
  [[ -d "$WORKSPACE_RELEASE_ROOT" && ! -L "$WORKSPACE_RELEASE_ROOT" \
      && "$(stat -c '%a:%U:%G' "$WORKSPACE_RELEASE_ROOT")" == "700:root:root" ]] \
    || fail "Atenea workspace release journal root is not exact"
  [[ -f "$WORKSPACE_ACTIVATION_SUDOERS" && ! -L "$WORKSPACE_ACTIVATION_SUDOERS" \
      && "$(stat -c '%a:%U:%G' "$WORKSPACE_ACTIVATION_SUDOERS")" == "440:root:root" \
      && "$(cat "$WORKSPACE_ACTIVATION_SUDOERS")" \
        == "$(workspace_activation_sudoers_content)" ]] \
    || fail "Atenea workspace activation sudo authority is not exact"
  visudo -cf "$WORKSPACE_ACTIVATION_SUDOERS" >/dev/null \
    || fail "Atenea workspace activation sudo authority is invalid"

  local name expected installed
  while IFS='|' read -r name expected; do
    installed="$WORKSPACE_ACTIVATION_BUNDLE/$name"
    [[ -f "$installed" && ! -L "$installed" \
        && "$(stat -c '%a:%U:%G' "$installed")" == "750:atenea-worker:atenea" \
        && "$(sha256sum "$installed" | cut -d' ' -f1)" == "$expected" ]] \
      || fail "Atenea workspace activation dependency differs: $name"
  done <<EOF
session-workspace-v1.sh|$SESSION_WORKSPACE_SHA256
runtime-admission-v1.sh|$RUNTIME_ADMISSION_SHA256
session-runtime-allocation-v1.sh|$SESSION_ALLOCATION_SHA256
EOF
}

tailscale_ipv4() {
  ip -4 -o address show dev tailscale0 scope global \
    | awk 'NR == 1 { split($4, value, "/"); print value[1] }'
}

validate_inputs() {
  [[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT >= 1024 && PORT <= 65535)) \
    || fail "worker port must be an unprivileged TCP port"
  [[ "$WORKER_ID" =~ ^[a-zA-Z0-9._-]{1,80}$ ]] || fail "worker id is invalid"
  [[ -f "$SCRIPT_DIR/agent-run-worker-v1.py" ]] || fail "worker program is missing"
  [[ -f "$SCRIPT_DIR/development-change-workspace-v1.py" ]] \
    || fail "development-change workspace mediator is missing"
  [[ -f "$SCRIPT_DIR/project-codex-runner-v1.py" ]] || fail "project runner is missing"
  [[ -f "$SCRIPT_DIR/beautips-project-codex-runner-v1.py" ]] \
    || fail "Beautips compatibility runner is missing"
  [[ -f "$SCRIPT_DIR/atenea-validation-v1.py" ]] || fail "validation mediator is missing"
  [[ -f "$SCRIPT_DIR/atenea-playwright-validation-v1.js" ]] || fail "Playwright check is missing"
  [[ -f "$SCRIPT_DIR/atenea-multi-repository-v1.sh" ]] || fail "repository role mediator is missing"
  [[ -f "$SCRIPT_DIR/atenea-workspace-activation-v1.sh" ]] || fail "workspace activator is missing"
  [[ -f "$SCRIPT_DIR/atenea-workspace-release-v1.py" ]] || fail "workspace releaser is missing"
  [[ -f "$SCRIPT_DIR/codex-release-stage-v1.py" ]] || fail "Codex update stage mediator is missing"
  [[ -f "$SCRIPT_DIR/codex-release-activate-v1.py" ]] || fail "Codex update activation mediator is missing"
  [[ -f "$SCRIPT_DIR/codex-release-restart-v1.sh" ]] || fail "Codex update restart scheduler is missing"
  [[ -f "$SCRIPT_DIR/codex-platform-instructions-v1.md" ]] || fail "platform instructions are missing"
  [[ -f "$SCRIPT_DIR/templates/$SERVICE" ]] || fail "systemd template is missing"
  [[ -f "$SCRIPT_DIR/templates/$MATERIALIZATION_SERVICE" ]] \
    || fail "materialization service template is missing"
  [[ "$(sha256sum "$SCRIPT_DIR/agent-run-worker-v1.py" | cut -d' ' -f1)" \
      == "$PROGRAM_SHA256" ]] || fail "worker program fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/development-change-workspace-v1.py" | cut -d' ' -f1)" \
      == "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR_SHA256" ]] \
    || fail "development-change workspace mediator fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/project-codex-runner-v1.py" | cut -d' ' -f1)" \
      == "$PROJECT_RUNNER_SHA256" ]] || fail "project runner fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/beautips-project-codex-runner-v1.py" | cut -d' ' -f1)" \
      == "$BEAUTIPS_PROJECT_RUNNER_SHA256" ]] \
    || fail "Beautips compatibility runner fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/atenea-validation-v1.py" | cut -d' ' -f1)" \
      == "$VALIDATION_MEDIATOR_SHA256" ]] \
    || fail "validation mediator fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/atenea-playwright-validation-v1.js" | cut -d' ' -f1)" \
      == "$PLAYWRIGHT_CHECK_SHA256" ]] \
    || fail "Playwright check fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/atenea-workspace-activation-v1.sh" | cut -d' ' -f1)" \
      == "$WORKSPACE_ACTIVATOR_SHA256" ]] \
    || fail "workspace activator fingerprint is stale"
  [[ "$(sha256sum "$SCRIPT_DIR/atenea-workspace-release-v1.py" | cut -d' ' -f1)" \
      == "$WORKSPACE_RELEASER_SHA256" ]] \
    || fail "workspace releaser fingerprint is stale"
}

plan() {
  validate_inputs
  local bind
  bind="$(tailscale_ipv4)"
  [[ -n "$bind" ]] || fail "tailscale0 has no global IPv4 address"
  jq -n \
    --arg action apply \
    --arg worker_id "$WORKER_ID" \
    --arg bind "$bind" \
    --argjson port "$PORT" \
    --arg control_plane_ip "$CONTROL_PLANE_IP" \
    --arg protocol "agent-run-worker/v1" \
    --arg synthetic_capability "synthetic-routing-v1" \
    --arg development_change_capability "development-change-workspace/v1" \
    --arg validation_capability "closed-validation-broker/v1" \
    --arg project_capability "project-codex-v1" \
    '{
      action: $action,
      workerId: $worker_id,
      bind: $bind,
      port: $port,
      controlPlaneIp: (if $control_plane_ip == "" then null else $control_plane_ip end),
      protocol: $protocol,
      capabilities: [$synthetic_capability, $development_change_capability, $validation_capability],
      availableDisabledCapabilities: [$project_capability],
      normalCapacity: 4,
      heavyCapacity: 2,
      tokenValueExposed: false,
      arbitraryExecution: false
    }'
}

write_project_config() {
  local selection_enabled="$1"
  local execution_enabled="$2"
  local workspaces_json="$3"
  local canonical_commit="$4"
  local temporary
  temporary="$(mktemp "$(dirname "$PROJECT_CONFIG")/.project-codex-v1.XXXXXX")"
  jq -n \
    --arg schema_version project-codex-v1 \
    --argjson selection_enabled "$selection_enabled" \
    --argjson execution_enabled "$execution_enabled" \
    --arg project_id atenea \
    --arg repository "$PROJECT_REPOSITORY" \
    --arg branch "$PROJECT_BRANCH" \
    --arg commit "$canonical_commit" \
    --arg manifest_sha256 "$PROJECT_MANIFEST_SHA256" \
    --arg runner "$PROJECT_RUNNER" \
    --arg attachment_root "$ATTACHMENT_ROOT" \
    --argjson workspaces "$workspaces_json" \
    '{
      schemaVersion: $schema_version,
      selectionEnabled: $selection_enabled,
      executionEnabled: $execution_enabled,
      projectId: $project_id,
      repository: $repository,
      branch: $branch,
      commit: $commit,
      manifestSha256: $manifest_sha256,
      runner: $runner,
      attachmentRoot: $attachment_root,
      workspaces: $workspaces
    }' >"$temporary"
  chown root:root "$temporary"
  chmod 0644 "$temporary"
  mv -f "$temporary" "$PROJECT_CONFIG"
}

observe_project_commit() {
  local commit
  commit="$(git --git-dir="$PROJECT_MIRROR" rev-parse --verify "${PROJECT_REF}^{commit}")" \
    || fail "canonical mirror ref is unavailable"
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || fail "canonical mirror ref is ambiguous"
  printf '%s\n' "$commit"
}

verify_project_config_content() {
  jq -e \
    --arg repository "$PROJECT_REPOSITORY" \
    --arg branch "$PROJECT_BRANCH" \
    --arg manifest_sha256 "$PROJECT_MANIFEST_SHA256" \
    --arg runner "$PROJECT_RUNNER" \
    --arg attachment_root "$ATTACHMENT_ROOT" '
    ((keys | sort) == ["attachmentRoot", "branch", "commit",
      "executionEnabled", "manifestSha256", "projectId", "repository",
      "runner", "schemaVersion", "selectionEnabled", "workspaces"] or
    (keys | sort) == ["branch", "commit", "executionEnabled",
      "manifestSha256", "projectId", "repository", "runner",
      "schemaVersion", "selectionEnabled", "workspaces"]) and
    .schemaVersion == "project-codex-v1" and
    .projectId == "atenea" and
    .repository == $repository and
    .branch == $branch and
    .manifestSha256 == $manifest_sha256 and
    .runner == $runner and
    ((has("attachmentRoot") | not) or
      .attachmentRoot == $attachment_root) and
    (.commit | test("^[0-9a-f]{40}$")) and
    (.selectionEnabled | type == "boolean") and
    (.executionEnabled | type == "boolean") and
    (.workspaces | type == "object") and
    (.workspaces | length) <= 1 and
    ([.workspaces[] |
      (keys | sort) == ["allocationSha256", "canonicalCommit", "sessionId", "worktree"] and
      (.sessionId | test("^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")) and
      (.allocationSha256 | test("^[0-9a-f]{64}$")) and
      (.canonicalCommit | test("^[0-9a-f]{40}$"))] | all)
  ' "$PROJECT_CONFIG" >/dev/null || fail "project configuration is invalid"

  local canonical_commit workspace_count
  canonical_commit="$(observe_project_commit)"
  [[ "$(jq -r '.commit' "$PROJECT_CONFIG")" == "$canonical_commit" ]] \
    || fail "project configuration canonical commit moved"
  workspace_count="$(jq '.workspaces | length' "$PROJECT_CONFIG")"
  [[ "$workspace_count" -eq 0 ]] && return 0

  local identity session_id worktree allocation_sha retained_commit allocation
  IFS=$'\t' read -r identity session_id worktree allocation_sha retained_commit < <(
    jq -r '.workspaces | to_entries[0] |
      [.key, .value.sessionId, .value.worktree,
       .value.allocationSha256, .value.canonicalCommit] | @tsv' "$PROJECT_CONFIG"
  )
  [[ "$identity" == "remote:ax42-01:work-session:${session_id}" ]] \
    || fail "project workspace identity is invalid"
  [[ "$worktree" == "${PROJECT_WORKSPACES_ROOT}/${session_id}/atenea" \
      && -d "$worktree" && ! -L "$worktree" ]] \
    || fail "project worktree ownership is invalid"
  allocation="${PROJECT_WORKSPACES_ROOT}/${session_id}/runtime-allocation-v1.json"
  [[ -f "$allocation" && ! -L "$allocation" \
      && "$(sha256sum "$allocation" | cut -d' ' -f1)" == "$allocation_sha" ]] \
    || fail "project allocation ownership is invalid"
  [[ "$(git -c safe.directory="$worktree" -C "$worktree" remote get-url origin)" == "$PROJECT_REPOSITORY" \
      && "$(git -c safe.directory="$worktree" -C "$worktree" rev-parse --verify 'HEAD^{commit}')" == "$retained_commit" \
      && "$(sha256sum "$worktree/ops/atenea-runtime.json" | cut -d' ' -f1)" == "$PROJECT_MANIFEST_SHA256" ]] \
    || fail "project worktree fingerprint is invalid"

  local status
  status="$(git -c safe.directory="$worktree" -C "$worktree" status --porcelain=v1 --untracked-files=all)"
  if [[ "$retained_commit" == "$canonical_commit" ]]; then
    [[ -z "$status" ]] || fail "current project worktree is not clean"
  else
    [[ "$(jq -r '.selectionEnabled' "$PROJECT_CONFIG")" == true \
        && "$(jq -r '.executionEnabled' "$PROJECT_CONFIG")" == false \
        && -n "$status" ]] || fail "retained project draft is not safely disabled"
    git --git-dir="$PROJECT_MIRROR" merge-base --is-ancestor "$retained_commit" "$canonical_commit" \
      || fail "retained project draft is not an ancestor of canonical source"
  fi
}

verify_project_config_source_advance_content() {
  jq -e \
    --arg repository "$PROJECT_REPOSITORY" \
    --arg branch "$PROJECT_BRANCH" \
    --arg manifest_sha256 "$PROJECT_MANIFEST_SHA256" \
    --arg runner "$PROJECT_RUNNER" \
    --arg attachment_root "$ATTACHMENT_ROOT" '
    (keys | sort) == ["attachmentRoot", "branch", "commit",
      "executionEnabled", "manifestSha256", "projectId", "repository",
      "runner", "schemaVersion", "selectionEnabled", "workspaces"] and
    .schemaVersion == "project-codex-v1" and
    .selectionEnabled == false and
    .executionEnabled == false and
    .projectId == "atenea" and
    .repository == $repository and
    .branch == $branch and
    .manifestSha256 == $manifest_sha256 and
    .runner == $runner and
    .attachmentRoot == $attachment_root and
    (.commit | test("^[0-9a-f]{40}$")) and
    .workspaces == {}
  ' "$PROJECT_CONFIG" >/dev/null \
    || fail "source-advanced project configuration is not exact"

  local retained_commit canonical_commit
  retained_commit="$(jq -r '.commit' "$PROJECT_CONFIG")"
  canonical_commit="$(observe_project_commit)"
  [[ "$retained_commit" != "$canonical_commit" ]] \
    || fail "project configuration source did not advance"
  git --git-dir="$PROJECT_MIRROR" merge-base --is-ancestor \
    "$retained_commit" "$canonical_commit" \
    || fail "project configuration commit is not an ancestor of canonical source"
  printf '%s:%s\n' "$retained_commit" "$canonical_commit"
}

verify_project_config_file_identity() {
  [[ -f "$PROJECT_CONFIG" && ! -L "$PROJECT_CONFIG" \
      && "$(stat -c '%a:%U:%G' "$PROJECT_CONFIG")" == "644:root:root" ]] \
    || fail "existing project configuration identity is invalid"
}

verify_project_config_transition_predecessor_content() {
  jq -e \
    --arg repository "$PROJECT_REPOSITORY" \
    --arg branch "$PROJECT_TRANSITION_PREDECESSOR_BRANCH" \
    --arg commit "$PROJECT_TRANSITION_PREDECESSOR_COMMIT" \
    --arg manifest_sha256 "$PROJECT_TRANSITION_PREDECESSOR_MANIFEST_SHA256" \
    --arg runner "$PROJECT_RUNNER" \
    --arg attachment_root "$ATTACHMENT_ROOT" '
    (keys | sort) == ["attachmentRoot", "branch", "commit",
      "executionEnabled", "manifestSha256", "projectId", "repository",
      "runner", "schemaVersion", "selectionEnabled", "workspaces"] and
    .schemaVersion == "project-codex-v1" and
    .selectionEnabled == false and
    .executionEnabled == false and
    .projectId == "atenea" and
    .repository == $repository and
    .branch == $branch and
    .commit == $commit and
    .manifestSha256 == $manifest_sha256 and
    .runner == $runner and
    .attachmentRoot == $attachment_root and
    .workspaces == {}
  ' "$PROJECT_CONFIG" >/dev/null \
    || fail "existing project configuration is not the exact empty transition predecessor"
}

project_config_install_preflight() {
  if [[ ! -e "$PROJECT_CONFIG" && ! -L "$PROJECT_CONFIG" ]]; then
    return 0
  fi
  verify_project_config_file_identity
  local retained_sha256
  retained_sha256="$(sha256sum "$PROJECT_CONFIG" | cut -d' ' -f1)"
  if ( verify_project_config_transition_predecessor_content ) >/dev/null 2>&1; then
    printf 'transition:%s\n' "$retained_sha256"
    return 0
  fi
  local source_advance
  if source_advance="$(verify_project_config_source_advance_content 2>/dev/null)"; then
    printf 'source-advance:%s:%s\n' "$retained_sha256" "$source_advance"
    return 0
  fi
  verify_project_config_content
  printf 'retain:%s\n' "$retained_sha256"
}

project_config_install_finalize() {
  local retained_identity="$1"
  if [[ -z "$retained_identity" ]]; then
    write_project_config false false '{}' "$(observe_project_commit)"
    return 0
  fi
  local operation retained_sha256 retained_commit canonical_commit surplus
  IFS=: read -r operation retained_sha256 retained_commit canonical_commit surplus \
    <<<"$retained_identity"
  [[ "$operation" == "retain" || "$operation" == "transition" \
      || "$operation" == "source-advance" ]] \
    || fail "existing project configuration transition identity is invalid"
  [[ "$retained_sha256" =~ ^[0-9a-f]{64}$ ]] \
    || fail "existing project configuration fingerprint is invalid"
  [[ -z "$surplus" ]] \
    || fail "existing project configuration transition identity is ambiguous"
  if [[ "$operation" == "source-advance" ]]; then
    [[ "$retained_commit" =~ ^[0-9a-f]{40}$ \
        && "$canonical_commit" =~ ^[0-9a-f]{40}$ ]] \
      || fail "source advance transition commits are invalid"
  else
    [[ -z "$retained_commit" && -z "$canonical_commit" ]] \
      || fail "existing project configuration transition identity is ambiguous"
  fi
  verify_project_config_file_identity
  [[ "$(sha256sum "$PROJECT_CONFIG" | cut -d' ' -f1)" == "$retained_sha256" ]] \
    || fail "existing project configuration changed during installation"
  if [[ "$operation" == "transition" ]]; then
    verify_project_config_transition_predecessor_content
    local canonical_commit
    canonical_commit="$(observe_project_commit)"
    [[ "$canonical_commit" == "$PROJECT_TRANSITION_TARGET_COMMIT" ]] \
      || fail "canonical main commit is not the reviewed transition target"
    write_project_config false false '{}' "$canonical_commit"
    verify_project_config_content
    return 0
  fi
  if [[ "$operation" == "source-advance" ]]; then
    [[ "$(verify_project_config_source_advance_content)" \
        == "${retained_commit}:${canonical_commit}" ]] \
      || fail "canonical source advance changed during installation"
    write_project_config false false '{}' "$canonical_commit"
    verify_project_config_content
    return 0
  fi
  verify_project_config_content
}

apply_install() {
  require_root
  validate_inputs
  [[ "$CONTROL_PLANE_IP" =~ ^100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] \
    || fail "ATENEA_CONTROL_PLANE_TAILSCALE_IP must be an exact tailnet IPv4 address"
  local bind
  bind="$(tailscale_ipv4)"
  [[ -n "$bind" ]] || fail "tailscale0 has no global IPv4 address"
  verify_attachment_root
  if [[ -e "$MATERIALIZATION_PARENT" || -L "$MATERIALIZATION_PARENT" ]]; then
    verify_materialization_parent
  fi
  if [[ -e "$MATERIALIZATION_ROOT" || -L "$MATERIALIZATION_ROOT" ]]; then
    verify_materialization_root
  fi
  local retained_project_config_sha256
  retained_project_config_sha256="$(project_config_install_preflight)"
  verify_beautips_project_runner_upgrade
  verify_workspace_activation_dependency
  systemctl stop "$SERVICE"

  install -d -o root -g root -m 0755 /usr/local/libexec/atenea
  install -d -o root -g root -m 0755 /usr/local/share/atenea
  install -o root -g root -m 0755 "$SCRIPT_DIR/agent-run-worker-v1.py" "$PROGRAM"
  install -o root -g root -m 0755 \
    "$SCRIPT_DIR/development-change-workspace-v1.py" \
    "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR"
  install -o root -g root -m 0755 "$SCRIPT_DIR/project-codex-runner-v1.py" "$PROJECT_RUNNER"
  install -o root -g root -m 0755 \
    "$SCRIPT_DIR/beautips-project-codex-runner-v1.py" "$BEAUTIPS_PROJECT_RUNNER"
  install -o root -g root -m 0755 "$SCRIPT_DIR/atenea-validation-v1.py" "$VALIDATION_MEDIATOR"
  install -o root -g root -m 0644 "$SCRIPT_DIR/atenea-playwright-validation-v1.js" "$PLAYWRIGHT_CHECK"
  install -o root -g root -m 0755 "$SCRIPT_DIR/atenea-multi-repository-v1.sh" "$ROLE_MEDIATOR"
  install -o root -g root -m 0755 "$SCRIPT_DIR/codex-release-stage-v1.py" "$CODEX_UPDATE_MEDIATOR"
  install -o root -g root -m 0755 "$SCRIPT_DIR/codex-release-activate-v1.py" "$CODEX_ACTIVATE_MEDIATOR"
  install -o root -g root -m 0755 "$SCRIPT_DIR/codex-release-restart-v1.sh" "$CODEX_RESTART_SCHEDULER"
  install -o root -g root -m 0644 \
    "$SCRIPT_DIR/codex-platform-instructions-v1.md" "$PLATFORM_INSTRUCTIONS"
  id atenea-program-role >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin atenea-program-role
  id atenea-worker-role >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin atenea-worker-role
  install -o root -g root -m 0755 "$SCRIPT_DIR/install-agent-run-worker-v1.sh" "$INSTALLER"
  install -d -o root -g atenea -m 0750 /etc/atenea-worker
  install_exact_directory atenea-worker atenea 0700 "$STATE_DIR"
  install_exact_directory root atenea 0750 "$VALIDATION_JOURNAL_ROOT"
  prepare_development_change_workspace_root
  prepare_materialization_root
  install_exact_directory root atenea 0750 "$CODEX_RELEASE_ROOT"
  install_exact_directory root atenea 0750 "$CODEX_RELEASE_ROOT/inbox"
  install_exact_directory atenea-worker atenea 0750 "$CODEX_RELEASE_ROOT/releases"
  install_exact_directory atenea-worker atenea 0750 "$CODEX_RELEASE_ROOT/operations"
  install_exact_directory root atenea 0750 "$CODEX_RELEASE_ROOT/activations"
  install_exact_directory root atenea 0750 "$CODEX_RELEASE_ROOT/rollbacks"
  if [[ ! -e "$TOKEN_FILE" ]]; then
    umask 0077
    openssl rand -hex 32 >"$TOKEN_FILE"
  fi
  chown root:atenea "$TOKEN_FILE"
  chmod 0640 "$TOKEN_FILE"

  {
    printf 'ATENEA_WORKER_BIND=%s\n' "$bind"
    printf 'ATENEA_WORKER_PORT=%s\n' "$PORT"
    printf 'ATENEA_WORKER_ID=%s\n' "$WORKER_ID"
  } >"$ENV_FILE"
  chown root:root "$ENV_FILE"
  chmod 0644 "$ENV_FILE"
  project_config_install_finalize "$retained_project_config_sha256"
  {
    printf 'atenea-worker ALL=(root) NOPASSWD: %s --config %s\n' "$PROJECT_RUNNER" "$PROJECT_CONFIG"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s --config %s --reconcile-materializations\n' \
      "$PROJECT_RUNNER" "$PROJECT_CONFIG"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s BACKEND_TEST *\n' "$VALIDATION_MEDIATOR"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s WEB_BUILD *\n' "$VALIDATION_MEDIATOR"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s ANDROID_BUILD *\n' "$VALIDATION_MEDIATOR"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s PLAYWRIGHT_ACCEPTANCE *\n' "$VALIDATION_MEDIATOR"
    for validation_definition in BACKEND_TEST WEB_BUILD ANDROID_BUILD PLAYWRIGHT_ACCEPTANCE; do
      printf 'atenea-worker ALL=(root) NOPASSWD: %s start %s *\n' "$VALIDATION_MEDIATOR" "$validation_definition"
      printf 'atenea-worker ALL=(root) NOPASSWD: %s inspect %s *\n' "$VALIDATION_MEDIATOR" "$validation_definition"
      printf 'atenea-worker ALL=(root) NOPASSWD: %s cancel %s *\n' "$VALIDATION_MEDIATOR" "$validation_definition"
    done
    printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "$ROLE_MEDIATOR"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s --registry %s --release-root %s --release-owner-uid %s\n' \
      "$CODEX_ACTIVATE_MEDIATOR" "$CODEX_UPDATE_REGISTRY" "$CODEX_RELEASE_ROOT" "$(id -u atenea-worker)"
    printf 'atenea-worker ALL=(root) NOPASSWD: %s --registry %s --release-root %s --release-owner-uid %s --restart-scheduler %s\n' \
      "$CODEX_ACTIVATE_MEDIATOR" "$CODEX_UPDATE_REGISTRY" "$CODEX_RELEASE_ROOT" \
      "$(id -u atenea-worker)" "$CODEX_RESTART_SCHEDULER"
  } >"$SUDOERS_FILE"
  chown root:root "$SUDOERS_FILE"
  chmod 0440 "$SUDOERS_FILE"
  visudo -cf "$SUDOERS_FILE" >/dev/null

  install -o root -g root -m 0644 \
    "$SCRIPT_DIR/templates/$MATERIALIZATION_SERVICE" "/etc/systemd/system/$MATERIALIZATION_SERVICE"
  install -o root -g root -m 0644 "$SCRIPT_DIR/templates/$SERVICE" "/etc/systemd/system/$SERVICE"
  systemctl daemon-reload
  systemctl start "$MATERIALIZATION_SERVICE"
  ufw allow in on tailscale0 proto tcp from "$CONTROL_PLANE_IP" to any port "$PORT" \
    comment 'atenea-agent-run-worker-v1' >/dev/null
  systemctl enable "$SERVICE"
  systemctl restart "$SERVICE"
  verify
}

verify() {
  require_root
  verify_workspace_activation_dependency
  local bind
  bind="$(tailscale_ipv4)"
  systemctl is-enabled "$SERVICE"
  systemctl is-active "$MATERIALIZATION_SERVICE"
  local ready=false
  for _attempt in $(seq 1 60); do
    if systemctl is-active --quiet "$SERVICE" \
        && ss -H -lntp "sport = :$PORT" | grep -F "$bind:$PORT" >/dev/null; then
      ready=true
      break
    fi
    sleep 0.25
  done
  [[ "$ready" == true ]] || fail "worker did not become ready within 15 seconds"
  systemctl is-active "$SERVICE"
  systemd-analyze security "$SERVICE" --no-pager >/dev/null
  ! ss -H -lntp "sport = :$PORT" \
      | awk '{ print $4 }' \
      | grep -Eq '^(0\.0\.0\.0|\[::\]):' \
    || fail "worker has a wildcard listener"
  [[ "$(stat -c '%a:%U:%G' "$TOKEN_FILE")" == "640:root:atenea" ]] \
    || fail "token file ownership or mode is invalid"
  [[ "$(stat -c '%a:%U:%G' "$STATE_DIR")" == "700:atenea-worker:atenea" ]] \
    || fail "state directory ownership or mode is invalid"
  [[ "$(stat -c '%a:%U:%G' "$VALIDATION_JOURNAL_ROOT")" == "750:root:atenea" ]] \
    || fail "validation journal ownership or mode is invalid"
  verify_development_change_workspace_root
  verify_attachment_root
  verify_materialization_parent
  verify_materialization_root
  [[ "$(stat -c '%a:%U:%G' "$CODEX_RELEASE_ROOT")" == "750:root:atenea" ]] \
    || fail "Codex release root ownership or mode is invalid"
  [[ "$(stat -c '%a:%U:%G' "$CODEX_RELEASE_ROOT/activations")" == "750:root:atenea" ]] \
    || fail "Codex activation operation directory ownership or mode is invalid"
  [[ "$(stat -c '%a:%U:%G' "$CODEX_RELEASE_ROOT/rollbacks")" == "750:root:atenea" ]] \
    || fail "Codex rollback operation directory ownership or mode is invalid"
  [[ "$(stat -c '%a:%U:%G' "$PROJECT_CONFIG")" == "644:root:root" ]] \
    || fail "project configuration ownership or mode is invalid"
  [[ -f "/etc/systemd/system/$SERVICE" && ! -L "/etc/systemd/system/$SERVICE" \
      && "$(stat -c '%a:%U:%G' "/etc/systemd/system/$SERVICE")" == "644:root:root" \
      && "$(sha256sum "/etc/systemd/system/$SERVICE" | cut -d' ' -f1)" \
        == "$SERVICE_TEMPLATE_SHA256" ]] \
    || fail "worker systemd unit differs from the reviewed template"
  [[ -f "/etc/systemd/system/$MATERIALIZATION_SERVICE" \
      && ! -L "/etc/systemd/system/$MATERIALIZATION_SERVICE" \
      && "$(stat -c '%a:%U:%G' "/etc/systemd/system/$MATERIALIZATION_SERVICE")" == "644:root:root" \
      && "$(sha256sum "/etc/systemd/system/$MATERIALIZATION_SERVICE" | cut -d' ' -f1)" \
        == "$MATERIALIZATION_SERVICE_TEMPLATE_SHA256" ]] \
    || fail "materialization service differs from the reviewed template"
  [[ -f "$INSTALLER" && ! -L "$INSTALLER" \
      && "$(stat -c '%a:%U:%G' "$INSTALLER")" == "755:root:root" \
      && "$(sha256sum "$INSTALLER" | cut -d' ' -f1)" \
        == "$(sha256sum "$SCRIPT_DIR/install-agent-run-worker-v1.sh" | cut -d' ' -f1)" ]] \
    || fail "worker installer differs from the reviewed source"
  [[ -f "$PROGRAM" && ! -L "$PROGRAM" \
      && "$(stat -c '%a:%U:%G' "$PROGRAM")" == "755:root:root" \
      && "$(sha256sum "$PROGRAM" | cut -d' ' -f1)" == "$PROGRAM_SHA256" ]] \
    || fail "worker program differs from the reviewed source"
  [[ -f "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR" \
      && ! -L "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR" \
      && "$(stat -c '%a:%U:%G' "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR")" \
        == "755:root:root" \
      && "$(sha256sum "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR" | cut -d' ' -f1)" \
        == "$DEVELOPMENT_CHANGE_WORKSPACE_MEDIATOR_SHA256" ]] \
    || fail "development-change workspace mediator differs from the reviewed source"
  [[ -f "$PROJECT_RUNNER" && ! -L "$PROJECT_RUNNER" \
      && "$(stat -c '%a:%U:%G' "$PROJECT_RUNNER")" == "755:root:root" \
      && "$(sha256sum "$PROJECT_RUNNER" | cut -d' ' -f1)" == "$PROJECT_RUNNER_SHA256" ]] \
    || fail "project runner differs from the reviewed source"
  [[ -f "$BEAUTIPS_PROJECT_RUNNER" && ! -L "$BEAUTIPS_PROJECT_RUNNER" \
      && "$(stat -c '%a:%U:%G' "$BEAUTIPS_PROJECT_RUNNER")" == "755:root:root" \
      && "$(sha256sum "$BEAUTIPS_PROJECT_RUNNER" | cut -d' ' -f1)" \
        == "$BEAUTIPS_PROJECT_RUNNER_SHA256" ]] \
    || fail "Beautips compatibility runner differs from the reviewed source"
  [[ -f "$ROLE_MEDIATOR" && ! -L "$ROLE_MEDIATOR" \
      && "$(stat -c '%a:%U:%G' "$ROLE_MEDIATOR")" == "755:root:root" \
      && "$(sha256sum "$ROLE_MEDIATOR" | cut -d' ' -f1)" \
        == "$(sha256sum "$SCRIPT_DIR/atenea-multi-repository-v1.sh" | cut -d' ' -f1)" ]] \
    || fail "repository role mediator differs from the reviewed source"
  [[ -f "$CODEX_UPDATE_MEDIATOR" && ! -L "$CODEX_UPDATE_MEDIATOR" \
      && "$(stat -c '%a:%U:%G' "$CODEX_UPDATE_MEDIATOR")" == "755:root:root" \
      && "$(sha256sum "$CODEX_UPDATE_MEDIATOR" | cut -d' ' -f1)" \
        == "$(sha256sum "$SCRIPT_DIR/codex-release-stage-v1.py" | cut -d' ' -f1)" ]] \
    || fail "Codex update stage mediator differs from the reviewed source"
  [[ -f "$CODEX_ACTIVATE_MEDIATOR" && ! -L "$CODEX_ACTIVATE_MEDIATOR" \
      && "$(stat -c '%a:%U:%G' "$CODEX_ACTIVATE_MEDIATOR")" == "755:root:root" \
      && "$(sha256sum "$CODEX_ACTIVATE_MEDIATOR" | cut -d' ' -f1)" \
        == "$(sha256sum "$SCRIPT_DIR/codex-release-activate-v1.py" | cut -d' ' -f1)" ]] \
    || fail "Codex update activation mediator differs from the reviewed source"
  [[ -f "$CODEX_RESTART_SCHEDULER" && ! -L "$CODEX_RESTART_SCHEDULER" \
      && "$(stat -c '%a:%U:%G' "$CODEX_RESTART_SCHEDULER")" == "755:root:root" \
      && "$(sha256sum "$CODEX_RESTART_SCHEDULER" | cut -d' ' -f1)" \
        == "$(sha256sum "$SCRIPT_DIR/codex-release-restart-v1.sh" | cut -d' ' -f1)" ]] \
    || fail "Codex update restart scheduler differs from the reviewed source"
  if [[ -e "$CODEX_UPDATE_REGISTRY" ]]; then
    [[ -f "$CODEX_UPDATE_REGISTRY" && ! -L "$CODEX_UPDATE_REGISTRY" \
        && "$(stat -c '%a:%U:%G' "$CODEX_UPDATE_REGISTRY")" == "600:root:root" ]] \
      || fail "Codex update registry ownership or mode is invalid"
  fi
  [[ -f "$PLATFORM_INSTRUCTIONS" && ! -L "$PLATFORM_INSTRUCTIONS" \
      && "$(stat -c '%a:%U:%G' "$PLATFORM_INSTRUCTIONS")" == "644:root:root" \
      && "$(sha256sum "$PLATFORM_INSTRUCTIONS" | cut -d' ' -f1)" \
        == "$PLATFORM_INSTRUCTIONS_SHA256" ]] \
    || fail "platform instructions differ from the reviewed source"
  [[ -f "$VALIDATION_MEDIATOR" && ! -L "$VALIDATION_MEDIATOR" \
      && "$(stat -c '%a:%U:%G' "$VALIDATION_MEDIATOR")" == "755:root:root" \
      && "$(sha256sum "$VALIDATION_MEDIATOR" | cut -d' ' -f1)" \
        == "$VALIDATION_MEDIATOR_SHA256" ]] \
    || fail "validation mediator differs from the reviewed source"
  [[ -f "$PLAYWRIGHT_CHECK" && ! -L "$PLAYWRIGHT_CHECK" \
      && "$(stat -c '%a:%U:%G' "$PLAYWRIGHT_CHECK")" == "644:root:root" \
      && "$(sha256sum "$PLAYWRIGHT_CHECK" | cut -d' ' -f1)" \
        == "$PLAYWRIGHT_CHECK_SHA256" ]] \
    || fail "Playwright check differs from the reviewed source"
  [[ "$(getent passwd atenea-program-role | cut -d: -f7)" == /usr/sbin/nologin ]] \
    || fail "programme role identity is unavailable or interactive"
  [[ "$(getent passwd atenea-worker-role | cut -d: -f7)" == /usr/sbin/nologin ]] \
    || fail "worker source role identity is unavailable or interactive"
  verify_project_config_content
  visudo -cf "$SUDOERS_FILE" >/dev/null
  verify_project_runner_sudoers
  verify_validation_sudoers
  printf '%s\n' 'agent-run-worker-v1 verification passed'
}

project_retained_draft_register() {
  require_root
  [[ "$#" -eq 3 ]] ||
    fail "project-retained-draft-register requires SESSION_ID, WORKSPACE_IDENTITY and RETAINED_COMMIT"
  local session_id="$1"
  local workspace_identity="$2"
  local retained_commit="$3"
  [[ "$session_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] \
    || fail "session id is invalid"
  [[ "$workspace_identity" == "remote:ax42-01:work-session:${session_id}" ]] \
    || fail "workspace identity is not exact"
  [[ "$retained_commit" =~ ^[0-9a-f]{40}$ ]] || fail "retained commit is invalid"

  local worktree="${PROJECT_WORKSPACES_ROOT}/${session_id}/atenea"
  local allocation="${PROJECT_WORKSPACES_ROOT}/${session_id}/runtime-allocation-v1.json"
  [[ -d "$worktree" && ! -L "$worktree" && -f "$allocation" && ! -L "$allocation" ]] \
    || fail "persisted retained workspace ownership is absent"
  [[ "$(git -c safe.directory="$worktree" -C "$worktree" remote get-url origin)" == "$PROJECT_REPOSITORY" ]] \
    || fail "retained workspace remote is foreign"
  [[ "$(git -c safe.directory="$worktree" -C "$worktree" rev-parse --verify 'HEAD^{commit}')" \
      == "$retained_commit" ]] || fail "retained workspace HEAD is conflicting"

  local canonical_commit
  canonical_commit="$(observe_project_commit)"
  [[ "$retained_commit" != "$canonical_commit" ]] || fail "retained workspace is not stale"
  git --git-dir="$PROJECT_MIRROR" merge-base --is-ancestor "$retained_commit" "$canonical_commit" \
    || fail "retained workspace is not an ancestor of canonical source"
  [[ -n "$(git -c safe.directory="$worktree" -C "$worktree" status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "retained workspace has no draft to preserve"
  [[ "$(sha256sum "$worktree/ops/atenea-runtime.json" | cut -d' ' -f1)" == "$PROJECT_MANIFEST_SHA256" ]] \
    || fail "retained workspace manifest is foreign"

  local allocation_sha exact_record existing_count existing_exact workspaces
  allocation_sha="$(sha256sum "$allocation" | cut -d' ' -f1)"
  exact_record="$(jq -cn \
    --arg session_id "$session_id" \
    --arg worktree "$worktree" \
    --arg allocation_sha256 "$allocation_sha" \
    --arg canonical_commit "$retained_commit" \
    '{
      sessionId: $session_id,
      worktree: $worktree,
      allocationSha256: $allocation_sha256,
      canonicalCommit: $canonical_commit
    }')"
  existing_count="$(jq '.workspaces | length' "$PROJECT_CONFIG")"
  existing_exact="$(jq -c --arg identity "$workspace_identity" '.workspaces[$identity] // null' "$PROJECT_CONFIG")"
  if [[ "$existing_count" -ne 0 &&
        ! ("$existing_count" -eq 1 && "$existing_exact" == "$exact_record") ]]; then
    fail "another persisted Atenea workspace is registered"
  fi
  workspaces="$(jq -cn \
    --arg identity "$workspace_identity" \
    --argjson record "$exact_record" \
    '{($identity): $record}')"
  write_project_config true false "$workspaces" "$canonical_commit"
}

project_register() {
  require_root
  [[ "$#" -eq 2 ]] || fail "project-register requires SESSION_ID and WORKSPACE_IDENTITY"
  local session_id="$1"
  local workspace_identity="$2"
  [[ "$session_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] \
    || fail "session id is invalid"
  [[ "$workspace_identity" == "remote:ax42-01:work-session:${session_id}" ]] \
    || fail "workspace identity is not exact"
  local worktree="${PROJECT_WORKSPACES_ROOT}/${session_id}/atenea"
  local allocation="${PROJECT_WORKSPACES_ROOT}/${session_id}/runtime-allocation-v1.json"
  [[ -d "$worktree" && ! -L "$worktree" && -f "$allocation" ]] \
    || fail "persisted workspace ownership is absent"
  [[ "$(git -c safe.directory="$worktree" -C "$worktree" remote get-url origin)" == "$PROJECT_REPOSITORY" ]] \
    || fail "workspace remote is foreign"
  local canonical_commit
  canonical_commit="$(observe_project_commit)"
  [[ "$(git -c safe.directory="$worktree" -C "$worktree" rev-parse --verify 'HEAD^{commit}')" \
      == "$canonical_commit" ]] || fail "workspace HEAD is not the canonical commit"
  [[ -z "$(git -c safe.directory="$worktree" -C "$worktree" status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "workspace is not clean"
  [[ "$(sha256sum "$worktree/ops/atenea-runtime.json" | cut -d' ' -f1)" == "$PROJECT_MANIFEST_SHA256" ]] \
    || fail "workspace manifest is foreign"
  local allocation_sha workspaces
  allocation_sha="$(sha256sum "$allocation" | cut -d' ' -f1)"
  workspaces="$(jq \
    --arg identity "$workspace_identity" \
    --arg session_id "$session_id" \
    --arg worktree "$worktree" \
    --arg allocation_sha256 "$allocation_sha" \
    --arg canonical_commit "$canonical_commit" \
    '.workspaces + {
      ($identity): {
        sessionId: $session_id,
        worktree: $worktree,
        allocationSha256: $allocation_sha256,
        canonicalCommit: $canonical_commit
      }
    }' "$PROJECT_CONFIG")"
  write_project_config true false "$workspaces" "$canonical_commit"
}

project_selection_enable() {
  require_root
  local workspaces
  workspaces="$(jq -c '.workspaces' "$PROJECT_CONFIG")"
  [[ "$(jq 'length' <<<"$workspaces")" -le 1 ]] || fail "at most one persisted workspace may be registered"
  write_project_config true false "$workspaces" "$(jq -r '.commit' "$PROJECT_CONFIG")"
  systemctl try-restart "$SERVICE"
}

project_enable() {
  require_root
  local workspaces
  workspaces="$(jq -c '.workspaces' "$PROJECT_CONFIG")"
  [[ "$(jq 'length' <<<"$workspaces")" -eq 1 ]] || fail "exactly one persisted workspace must be registered"
  write_project_config true true "$workspaces" "$(jq -r '.commit' "$PROJECT_CONFIG")"
  systemctl try-restart "$SERVICE"
}

project_activate() {
  require_root
  [[ "$#" -eq 2 ]] || fail "project-activate requires SESSION_ID and WORKSPACE_IDENTITY"
  project_register "$1" "$2"
  local workspaces
  workspaces="$(jq -c '.workspaces' "$PROJECT_CONFIG")"
  [[ "$(jq 'length' <<<"$workspaces")" -eq 1 ]] || fail "exactly one persisted workspace must be registered"
  # The worker reads this file for every request. Avoid restarting the service
  # from inside the workspace-ensure request that is currently serving activation.
  write_project_config true true "$workspaces" "$(jq -r '.commit' "$PROJECT_CONFIG")"
}

project_disable() {
  require_root
  local workspaces
  workspaces="$(jq -c '.workspaces' "$PROJECT_CONFIG")"
  write_project_config false false "$workspaces" "$(jq -r '.commit' "$PROJECT_CONFIG")"
  systemctl try-restart "$SERVICE"
}

project_unregister() {
  require_root
  [[ "$#" -eq 2 ]] || fail "project-unregister requires SESSION_ID and WORKSPACE_IDENTITY"
  local session_id="$1"
  local workspace_identity="$2"
  local matches
  matches="$(jq -r \
    --arg identity "$workspace_identity" \
    --arg session_id "$session_id" \
    '(.workspaces[$identity].sessionId // "") == $session_id' "$PROJECT_CONFIG")"
  [[ "$matches" == true ]] || fail "exact persisted workspace ownership does not match"
  local workspaces
  workspaces="$(jq -c --arg identity "$workspace_identity" 'del(.workspaces[$identity]) | .workspaces' "$PROJECT_CONFIG")"
  write_project_config false false "$workspaces" "$(jq -r '.commit' "$PROJECT_CONFIG")"
  systemctl try-restart "$SERVICE"
}

disable_endpoint() {
  require_root
  systemctl disable --now "$SERVICE"
  systemctl stop "$MATERIALIZATION_SERVICE"
}

rollback_endpoint() {
  require_root
  [[ "$CONTROL_PLANE_IP" =~ ^100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] \
    || fail "ATENEA_CONTROL_PLANE_TAILSCALE_IP must be an exact tailnet IPv4 address"
  verify_attachment_root
  verify_materialization_parent
  verify_materialization_root
  systemctl disable --now "$SERVICE"
  systemctl stop "$MATERIALIZATION_SERVICE"
  if ufw status | grep -F "$PORT/tcp on tailscale0" | grep -Fq "$CONTROL_PLANE_IP"; then
    ufw --force delete allow in on tailscale0 proto tcp from "$CONTROL_PLANE_IP" \
      to any port "$PORT" comment 'atenea-agent-run-worker-v1' >/dev/null
  fi
  verify_attachment_root
  verify_materialization_parent
  verify_materialization_root
}

enable_endpoint() {
  require_root
  systemctl enable --now "$SERVICE"
  verify
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

case "$ACTION" in
  plan) plan ;;
  apply) apply_install ;;
  verify) verify ;;
  disable) disable_endpoint ;;
  rollback) rollback_endpoint ;;
  enable) enable_endpoint ;;
  project-register) shift; project_register "$@" ;;
  project-retained-draft-register) shift; project_retained_draft_register "$@" ;;
  project-activate) shift; project_activate "$@" ;;
  project-selection-enable) project_selection_enable ;;
  project-enable) project_enable ;;
  project-disable) project_disable ;;
  project-unregister) shift; project_unregister "$@" ;;
  prepare-materialization-root) prepare_materialization_root ;;
  *) fail "usage: $0 plan|apply|verify|disable|rollback|enable|project-register|project-retained-draft-register|project-activate|project-selection-enable|project-enable|project-disable|project-unregister|prepare-materialization-root" ;;
esac
