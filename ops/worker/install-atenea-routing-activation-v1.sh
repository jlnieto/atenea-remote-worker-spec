#!/usr/bin/env bash

set -Eeuo pipefail
umask 0077

ACTION="${1:-}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROGRAM=/usr/local/libexec/atenea/atenea-workspace-activation-v1.sh
RELEASE_PROGRAM=/usr/local/libexec/atenea/atenea-workspace-release-v1.py
SUDOERS=/etc/sudoers.d/92-atenea-routing-activation-v1
WORKER_BUNDLE=/srv/atenea/worker/workspace-v1/ops/worker
RELEASE_STATE_ROOT=/srv/atenea/worker/workspace-release-v1/sessions
RETAINED_PREDECESSOR_ROOT=/srv/atenea/worker/routing-activation-v1/predecessors
RETAINED_RELEASE_PROGRAM="${RETAINED_PREDECESSOR_ROOT}/atenea-workspace-release-v1.baccb3c7.py"
DEPENDENCIES=(
  session-workspace-v1.sh
  runtime-admission-v1.sh
  session-runtime-allocation-v1.sh
)
PROGRAM_PREDECESSOR_SHA256=61fc03da468f2f9fa1fb101dc42129a773f02acaacbc40fd46e18d7a06724df2
PROGRAM_SHA256=5ef544c478c17a0ae6ae88586915185572721ca89dc48dbbf15b65ad417aa889
RELEASE_PROGRAM_PREDECESSOR_SHA256=baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0
RELEASE_PROGRAM_SHA256=095e0db0ee77814f59f12907d003bad462c64c57aa8b85137e9c142147416de3
SESSION_WORKSPACE_PREDECESSOR_SHA256=3e41ae7f218f360920bed7cd4b2d75cab5396bb07649635694db3271b12d2ffe
SESSION_WORKSPACE_SHA256=09818d9b717ec8939137a8c5b7aac634f954d40596cf35d909fd04aa374df213
RUNTIME_ADMISSION_SHA256=a81366d3495bb2a7bf4702e9ea934a74e9b3edb30f728926e655a5c0a6a9f7ce
SESSION_ALLOCATION_SHA256=2efceeaaba78b349f1d6aa79bfba5d908d397a9e3a480cfa3b100bde52fb99d7

fail() {
  printf 'ATENEA_ROUTING_ACTIVATION_INSTALL_REJECTED: %s\n' "$1" >&2
  exit 65
}

require_root() {
  [[ "${EUID}" -eq 0 ]] || fail "$1 requires root"
}

source_hash() {
  sha256sum "${SCRIPT_DIR}/atenea-workspace-activation-v1.sh" | cut -d' ' -f1
}

release_source_hash() {
  sha256sum "${SCRIPT_DIR}/atenea-workspace-release-v1.py" | cut -d' ' -f1
}

sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "${PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s\n' "${RELEASE_PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-capacity-owner\n' "${RELEASE_PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-release-preflight\n' "${RELEASE_PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-unactivated\n' "${RELEASE_PROGRAM}"
}

release_preflight_predecessor_sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "${PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s\n' "${RELEASE_PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-capacity-owner\n' "${RELEASE_PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-release-preflight\n' "${RELEASE_PROGRAM}"
}

capacity_diagnosis_sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "${PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s\n' "${RELEASE_PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s --diagnose-capacity-owner\n' "${RELEASE_PROGRAM}"
}

successor_predecessor_sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "${PROGRAM}"
  printf 'atenea-worker ALL=(root) NOPASSWD: %s\n' "${RELEASE_PROGRAM}"
}

predecessor_sudoers_content() {
  printf 'atenea-worker ALL=(root) NOPASSWD: %s ensure *\n' "${PROGRAM}"
}

expected_dependency_sha256() {
  case "$1" in
    session-workspace-v1.sh) printf '%s\n' "${SESSION_WORKSPACE_SHA256}" ;;
    runtime-admission-v1.sh) printf '%s\n' "${RUNTIME_ADMISSION_SHA256}" ;;
    session-runtime-allocation-v1.sh) printf '%s\n' "${SESSION_ALLOCATION_SHA256}" ;;
    *) fail 'unknown activation dependency' ;;
  esac
}

verify_source_bundle() {
  [[ "$(source_hash)" == "${PROGRAM_SHA256}" ]] ||
    fail 'activation mediator source fingerprint is stale'
  [[ "$(release_source_hash)" == "${RELEASE_PROGRAM_SHA256}" ]] ||
    fail 'release mediator source fingerprint is stale'
  local dependency expected
  for dependency in "${DEPENDENCIES[@]}"; do
    expected="$(expected_dependency_sha256 "${dependency}")"
    [[ -f "${SCRIPT_DIR}/${dependency}" &&
        "$(sha256sum "${SCRIPT_DIR}/${dependency}" | cut -d' ' -f1)" == "${expected}" ]] ||
      fail "activation dependency source fingerprint is stale: ${dependency}"
  done
}

verify_release_program() {
  [[ -f "${RELEASE_PROGRAM}" && ! -L "${RELEASE_PROGRAM}" &&
      "$(stat -c %U:%G:%a "${RELEASE_PROGRAM}")" == root:root:755 &&
      "$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)" == \
        "${RELEASE_PROGRAM_SHA256}" ]] ||
    fail 'installed release mediator differs'
}

verify_release_program_upgrade() {
  [[ -f "${RELEASE_PROGRAM}" && ! -L "${RELEASE_PROGRAM}" &&
      "$(stat -c %U:%G:%a "${RELEASE_PROGRAM}")" == root:root:755 ]] ||
    fail 'installed release mediator identity is ambiguous'
  local digest
  digest="$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)"
  [[ "${digest}" == "${RELEASE_PROGRAM_SHA256}" ||
      "${digest}" == "${RELEASE_PROGRAM_PREDECESSOR_SHA256}" ]] ||
    fail 'installed release mediator is not an accepted predecessor'
}

verify_release_state_root() {
  [[ -d "${RELEASE_STATE_ROOT}" && ! -L "${RELEASE_STATE_ROOT}" &&
      "$(stat -c %U:%G:%a "${RELEASE_STATE_ROOT}")" == root:root:700 ]] ||
    fail 'release journal root identity is ambiguous'
}

verify_retained_release_predecessor() {
  [[ -d "${RETAINED_PREDECESSOR_ROOT}" && ! -L "${RETAINED_PREDECESSOR_ROOT}" &&
      "$(stat -c %U:%G:%a "${RETAINED_PREDECESSOR_ROOT}")" == root:root:700 ]] ||
    fail 'retained predecessor root identity is ambiguous'
  [[ -f "${RETAINED_RELEASE_PROGRAM}" && ! -L "${RETAINED_RELEASE_PROGRAM}" &&
      "$(stat -c %U:%G:%a "${RETAINED_RELEASE_PROGRAM}")" == root:root:755 &&
      "$(sha256sum "${RETAINED_RELEASE_PROGRAM}" | cut -d' ' -f1)" == \
        "${RELEASE_PROGRAM_PREDECESSOR_SHA256}" ]] ||
    fail 'retained release mediator predecessor differs'
}

retain_release_predecessor() {
  local installed_hash
  installed_hash="$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)"
  [[ "${installed_hash}" == "${RELEASE_PROGRAM_PREDECESSOR_SHA256}" ||
      "${installed_hash}" == "${RELEASE_PROGRAM_SHA256}" ]] ||
    fail 'installed release mediator changed after preflight'
  if [[ -e "${RETAINED_PREDECESSOR_ROOT}" || -L "${RETAINED_PREDECESSOR_ROOT}" ]]; then
    verify_retained_release_predecessor
    [[ "${installed_hash}" == "${RELEASE_PROGRAM_PREDECESSOR_SHA256}" ]] || return 0
  else
    [[ "${installed_hash}" == "${RELEASE_PROGRAM_PREDECESSOR_SHA256}" ]] || return 0
    install -d -o root -g root -m 0700 "${RETAINED_PREDECESSOR_ROOT}"
    chown root:root "${RETAINED_PREDECESSOR_ROOT}"
    chmod 0700 "${RETAINED_PREDECESSOR_ROOT}"
    chmod u-s,g-s,o-t "${RETAINED_PREDECESSOR_ROOT}"
    install -o root -g root -m 0755 \
      "${RELEASE_PROGRAM}" "${RETAINED_RELEASE_PROGRAM}"
  fi
  verify_retained_release_predecessor
}

verify_common_predecessor() {
  [[ -f "${PROGRAM}" && ! -L "${PROGRAM}" &&
      "$(stat -c %U:%G:%a "${PROGRAM}")" == root:root:755 ]] ||
    fail 'installed mediator identity is ambiguous'
  local phase="${1:-upgrade}" digest dependency installed expected
  digest="$(sha256sum "${PROGRAM}" | cut -d' ' -f1)"
  [[ "${digest}" == "${PROGRAM_SHA256}" ||
      "${digest}" == "${PROGRAM_PREDECESSOR_SHA256}" ]] ||
    fail 'installed mediator is not an accepted predecessor'
  for dependency in "${DEPENDENCIES[@]}"; do
    installed="${WORKER_BUNDLE}/${dependency}"
    expected="$(expected_dependency_sha256 "${dependency}")"
    [[ -f "${installed}" && ! -L "${installed}" &&
        "$(stat -c %U:%G:%a "${installed}")" == atenea-worker:atenea:750 ]] ||
      fail "installed activation dependency is foreign: ${dependency}"
    digest="$(sha256sum "${installed}" | cut -d' ' -f1)"
    # The reviewed dependency predecessor is valid only before upgrading.
    [[ "${digest}" == "${expected}" ||
        ( "${phase}" == upgrade && "${dependency}" == session-workspace-v1.sh &&
          "${digest}" == "${SESSION_WORKSPACE_PREDECESSOR_SHA256}" ) ]] ||
      fail "installed activation dependency is foreign: ${dependency}"
  done
}

activation_bundle_preflight() {
  verify_source_bundle
  local present=0 total=$((4 + ${#DEPENDENCIES[@]}))
  local path dependency digest release_digest sudoers_value
  for path in "${PROGRAM}" "${RELEASE_PROGRAM}" "${SUDOERS}" "${RELEASE_STATE_ROOT}"; do
    [[ -e "${path}" || -L "${path}" ]] && present=$((present + 1))
  done
  for dependency in "${DEPENDENCIES[@]}"; do
    path="${WORKER_BUNDLE}/${dependency}"
    [[ -e "${path}" || -L "${path}" ]] && present=$((present + 1))
  done

  if [[ "${present}" -eq 0 ]]; then
    printf 'absent\n'
    return 0
  fi
  [[ -f "${SUDOERS}" && ! -L "${SUDOERS}" &&
      "$(stat -c %U:%G:%a "${SUDOERS}")" == root:root:440 ]] ||
    fail 'installed sudoers boundary is foreign'
  verify_common_predecessor "${1:-upgrade}"
  digest="$(sha256sum "${PROGRAM}" | cut -d' ' -f1)"
  sudoers_value="$(cat "${SUDOERS}")"

  if [[ "${sudoers_value}" == "$(sudoers_content)" ]]; then
    [[ "${present}" -eq "${total}" && "${digest}" == "${PROGRAM_SHA256}" ]] ||
      fail 'installed successor activation bundle is partial'
    verify_release_program
    verify_release_state_root
    printf 'current\n'
    return 0
  fi
  if [[ "${sudoers_value}" == "$(release_preflight_predecessor_sudoers_content)" ]]; then
    [[ "${present}" -eq "${total}" && "${digest}" == "${PROGRAM_SHA256}" ]] ||
      fail 'installed unactivated-diagnosis predecessor is partial'
    verify_release_program_upgrade
    verify_release_state_root
    release_digest="$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)"
    if [[ "${release_digest}" == "${RELEASE_PROGRAM_PREDECESSOR_SHA256}" ]]; then
      printf 'rollout-predecessor\n'
    else
      printf 'rollback-routing-predecessor\n'
    fi
    return 0
  fi
  if [[ "${sudoers_value}" == "$(capacity_diagnosis_sudoers_content)" ]]; then
    [[ "${present}" -eq "${total}" && "${digest}" == "${PROGRAM_SHA256}" ]] ||
      fail 'installed release-preflight predecessor is partial'
    verify_release_program_upgrade
    verify_release_state_root
    printf 'upgrade\n'
    return 0
  fi
  if [[ "${sudoers_value}" == "$(successor_predecessor_sudoers_content)" ]]; then
    [[ "${present}" -eq "${total}" && "${digest}" == "${PROGRAM_SHA256}" ]] ||
      fail 'installed capacity-diagnosis predecessor is partial'
    verify_release_program_upgrade
    verify_release_state_root
    printf 'upgrade\n'
    return 0
  fi
  [[ "${sudoers_value}" == "$(predecessor_sudoers_content)" ]] ||
    fail 'installed sudoers boundary is foreign'
  if [[ ! -e "${RELEASE_PROGRAM}" && ! -L "${RELEASE_PROGRAM}" ]]; then
    [[ "${present}" -eq $((total - 2)) || "${present}" -eq $((total - 1)) ]] ||
      fail 'installed predecessor activation bundle is partial'
    if [[ -e "${RELEASE_STATE_ROOT}" || -L "${RELEASE_STATE_ROOT}" ]]; then
      verify_release_state_root
    fi
    printf 'predecessor\n'
    return 0
  fi
  [[ "${present}" -eq "${total}" && "${digest}" == "${PROGRAM_SHA256}" ]] ||
    fail 'disabled release rollback bundle is partial'
  verify_release_program_upgrade
  verify_release_state_root
  printf 'rollback-disabled\n'
}

write_sudoers() {
  local content_function="$1"
  local temporary
  temporary="$(mktemp "$(dirname -- "${SUDOERS}")/.atenea-routing.XXXXXX")"
  "${content_function}" >"${temporary}"
  chown root:root "${temporary}"
  chmod 0440 "${temporary}"
  visudo -cf "${temporary}" >/dev/null
  mv -f "${temporary}" "${SUDOERS}"
}

apply_install() {
  require_root installation
  local preflight_state
  preflight_state="$(activation_bundle_preflight)"
  [[ "$(activation_bundle_preflight)" == "${preflight_state}" ]] ||
    fail 'installed activation bundle changed after preflight'
  if [[ -e "${RETAINED_PREDECESSOR_ROOT}" || -L "${RETAINED_PREDECESSOR_ROOT}" ||
        "${preflight_state}" == rollout-predecessor ]]; then
    retain_release_predecessor
  fi
  install -d -o root -g root -m 0755 "$(dirname -- "${PROGRAM}")"
  install -d -o atenea-worker -g atenea -m 0750 "${WORKER_BUNDLE}"
  local dependency
  for dependency in "${DEPENDENCIES[@]}"; do
    install -o atenea-worker -g atenea -m 0750 \
      "${SCRIPT_DIR}/${dependency}" "${WORKER_BUNDLE}/${dependency}"
  done
  install -o root -g root -m 0755 \
    "${SCRIPT_DIR}/atenea-workspace-activation-v1.sh" "${PROGRAM}"
  install -o root -g root -m 0755 \
    "${SCRIPT_DIR}/atenea-workspace-release-v1.py" "${RELEASE_PROGRAM}"
  if [[ ! -e "${RELEASE_STATE_ROOT}" && ! -L "${RELEASE_STATE_ROOT}" ]]; then
    install -d -o root -g root -m 0700 "${RELEASE_STATE_ROOT}"
    # /srv/atenea/worker is setgid. GNU install can preserve the inherited
    # special bit even with -m 0700, so normalize the new private leaf before
    # verifying or writing a journal.
    chown root:root "${RELEASE_STATE_ROOT}"
    chmod 0700 "${RELEASE_STATE_ROOT}"
    chmod u-s,g-s,o-t "${RELEASE_STATE_ROOT}"
  fi
  verify_release_state_root
  write_sudoers sudoers_content
  verify
}

rollback_install() {
  require_root rollback
  local state
  state="$(activation_bundle_preflight)"
  [[ "$(activation_bundle_preflight)" == "${state}" ]] ||
    fail 'installed activation bundle changed after rollback preflight'
  if [[ "${state}" == predecessor ]]; then
    jq -cn '{state: "rolled-back", changed: false, routingChanged: false,
      releaseAuthority: false, retainedJournals: true}'
    return 0
  fi
  if [[ "${state}" == rollout-predecessor ]]; then
    local retained_static=false
    if [[ -e "${RETAINED_PREDECESSOR_ROOT}" || -L "${RETAINED_PREDECESSOR_ROOT}" ]]; then
      verify_retained_release_predecessor
      retained_static=true
    fi
    jq -cn --argjson retained_static "${retained_static}" '{
      state: "rolled-back", changed: false, routingChanged: false,
      releaseAuthority: true, retainedJournals: true,
      retainedStaticPredecessor: $retained_static
    }'
    return 0
  fi
  if [[ "${state}" == current &&
        ( -e "${RETAINED_PREDECESSOR_ROOT}" || -L "${RETAINED_PREDECESSOR_ROOT}" ) ]]; then
    verify_retained_release_predecessor
    write_sudoers release_preflight_predecessor_sudoers_content
    [[ "$(activation_bundle_preflight)" == rollback-routing-predecessor ]] ||
      fail 'predecessor routing authority was not restored exactly'
    install -o root -g root -m 0755 \
      "${RETAINED_RELEASE_PROGRAM}" "${RELEASE_PROGRAM}"
    [[ "$(activation_bundle_preflight)" == rollout-predecessor ]] ||
      fail 'complete rollout predecessor was not restored exactly'
    jq -cn '{state: "rolled-back", changed: true, routingChanged: false,
      releaseAuthority: true, retainedJournals: true,
      retainedStaticPredecessor: true}'
    return 0
  fi
  if [[ "${state}" == current || "${state}" == upgrade ]]; then
    write_sudoers predecessor_sudoers_content
    [[ "$(activation_bundle_preflight)" == rollback-disabled ]] ||
      fail 'release authority was not disabled exactly'
    state=rollback-disabled
  fi
  [[ "${state}" == rollback-disabled ]] ||
    fail 'installed bundle is not an exact rollback successor'
  verify_release_program_upgrade
  rm -f -- "${RELEASE_PROGRAM}"
  [[ "$(activation_bundle_preflight)" == predecessor ]] ||
    fail 'exact activation predecessor was not restored'
  jq -cn '{state: "rolled-back", changed: true, routingChanged: false,
    releaseAuthority: false, retainedJournals: true}'
}

verify() {
  require_root verification
  [[ "$(activation_bundle_preflight final)" == current ]] ||
    fail 'installed activation bundle is not current'
  verify_release_program
  visudo -cf "${SUDOERS}" >/dev/null ||
    fail 'sudoers boundary is invalid'
  jq -cn --arg program "${PROGRAM}" --arg release_program "${RELEASE_PROGRAM}" '{
    state: "verified",
    program: $program,
    releaseProgram: $release_program,
    projectId: "atenea",
    releaseEnabledByDefault: false,
    arbitraryAuthority: false
  }'
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

[[ "${ACTION}" =~ ^(plan|apply|verify|rollback)$ && "$#" -eq 1 ]] ||
  fail 'usage: plan|apply|verify|rollback'

case "${ACTION}" in
  plan)
    verify_source_bundle
    jq -cn --arg program "${PROGRAM}" --arg release_program "${RELEASE_PROGRAM}" --arg sudoers "${SUDOERS}" '{
      action: "apply",
      program: $program,
      releaseProgram: $release_program,
      sudoers: $sudoers,
      defaultRoutingChange: false,
      releaseEnabledByDefault: false,
      serviceRestart: false
    }'
    ;;
  apply)
    apply_install
    ;;
  verify)
    verify
    ;;
  rollback)
    rollback_install
    ;;
esac
