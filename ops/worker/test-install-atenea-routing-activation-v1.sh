#!/usr/bin/env bash

set -Eeuo pipefail
umask 0077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}"
TEST_ROOT="$(mktemp -d /tmp/atenea-routing-install.XXXXXX)"
STAT_BIN="$(command -v stat)"
INSTALL_BIN="$(command -v install)"

cleanup() {
  case "${TEST_ROOT}" in
    /tmp/atenea-routing-install.*) rm -rf -- "${TEST_ROOT}" ;;
  esac
}
trap cleanup EXIT

fail_test() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

source "${SOURCE_DIR}/install-atenea-routing-activation-v1.sh"
SCRIPT_DIR="${SOURCE_DIR}"
PROGRAM="${TEST_ROOT}/usr/local/libexec/atenea/atenea-workspace-activation-v1.sh"
RELEASE_PROGRAM="${TEST_ROOT}/usr/local/libexec/atenea/atenea-workspace-release-v1.py"
SUDOERS="${TEST_ROOT}/etc/sudoers.d/92-atenea-routing-activation-v1"
WORKER_BUNDLE="${TEST_ROOT}/srv/atenea/worker/workspace-v1/ops/worker"
RELEASE_STATE_ROOT="${TEST_ROOT}/srv/atenea/worker/workspace-release-v1/sessions"
RETAINED_PREDECESSOR_ROOT="${TEST_ROOT}/srv/atenea/worker/routing-activation-v1/predecessors"
RETAINED_RELEASE_PROGRAM="${RETAINED_PREDECESSOR_ROOT}/atenea-workspace-release-v1.baccb3c7.py"
require_root() { :; }
chown() { :; }
visudo() { :; }
install() {
  local arguments=()
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      -o|-g) shift 2 ;;
      *) arguments+=("$1"); shift ;;
    esac
  done
  "${INSTALL_BIN}" "${arguments[@]}"
}

# The production verifier requires root-owned paths. This focused sandbox
# preserves and checks the real modes/hashes while projecting only the expected
# owners; AX42 verification covers the real owner values.
stat() {
  if [[ "$#" -eq 3 && "$1" == -c && "$2" == %U:%G:%a ]]; then
    local mode
    mode="$("${STAT_BIN}" -c %a "$3")"
    case "$3" in
      "${PROGRAM}"|"${RELEASE_PROGRAM}"|"${SUDOERS}"|"${RELEASE_STATE_ROOT}"|"${RETAINED_PREDECESSOR_ROOT}"|"${RETAINED_RELEASE_PROGRAM}")
        printf 'root:root:%s\n' "${mode}"
        ;;
      "${WORKER_BUNDLE}"/*) printf 'atenea-worker:atenea:%s\n' "${mode}" ;;
      *) return 1 ;;
    esac
    return 0
  fi
  "${STAT_BIN}" "$@"
}

bundle_common() {
  mkdir -p "$(dirname -- "${PROGRAM}")" "$(dirname -- "${SUDOERS}")" \
    "${WORKER_BUNDLE}"
  cp "${SOURCE_DIR}/atenea-workspace-activation-v1.sh" "${PROGRAM}"
  chmod 0755 "${PROGRAM}"
  local dependency
  for dependency in "${DEPENDENCIES[@]}"; do
    cp "${SOURCE_DIR}/${dependency}" "${WORKER_BUNDLE}/${dependency}"
    chmod 0750 "${WORKER_BUNDLE}/${dependency}"
  done
}

bundle_create_current() {
  bundle_common
  cp "${SOURCE_DIR}/atenea-workspace-release-v1.py" "${RELEASE_PROGRAM}"
  chmod 0755 "${RELEASE_PROGRAM}"
  mkdir -p "${RELEASE_STATE_ROOT}"
  chmod 0700 "${RELEASE_STATE_ROOT}"
  sudoers_content >"${SUDOERS}"
  chmod 0440 "${SUDOERS}"
}

bundle_create_capacity_diagnosis_predecessor() {
  bundle_common
  printf 'reviewed release predecessor fixture\n' >"${RELEASE_PROGRAM}"
  chmod 0755 "${RELEASE_PROGRAM}"
  mkdir -p "${RELEASE_STATE_ROOT}"
  chmod 0700 "${RELEASE_STATE_ROOT}"
  capacity_diagnosis_sudoers_content >"${SUDOERS}"
  chmod 0440 "${SUDOERS}"
}

bundle_create_release_preflight_predecessor() {
  bundle_common
  printf 'reviewed live release predecessor fixture\n' >"${RELEASE_PROGRAM}"
  chmod 0755 "${RELEASE_PROGRAM}"
  mkdir -p "${RELEASE_STATE_ROOT}"
  chmod 0700 "${RELEASE_STATE_ROOT}"
  release_preflight_predecessor_sudoers_content >"${SUDOERS}"
  chmod 0440 "${SUDOERS}"
}

bundle_create_predecessor() {
  bundle_common
  predecessor_sudoers_content >"${SUDOERS}"
  chmod 0440 "${SUDOERS}"
}

bundle_reset() {
  rm -rf -- "${TEST_ROOT}/usr" "${TEST_ROOT}/etc" "${TEST_ROOT}/srv"
}

[[ "$(activation_bundle_preflight)" == absent ]] \
  || fail_test 'all-absent bundle was not accepted'
verify_source_bundle

# The deployed predecessor is an exact reviewed release, not a generic fixture.
# It must be promotable while the earlier retained rollback predecessor remains
# byte-for-byte intact.
git -C "${SOURCE_DIR}" show \
  '419d046e27a6e54316eb4124344c233b4cbac84b:ops/worker/atenea-workspace-release-v1.py' \
  >"${TEST_ROOT}/release-4bc-predecessor.py"
[[ "$(sha256sum "${TEST_ROOT}/release-4bc-predecessor.py" | cut -d' ' -f1)" == \
    4bc09eadbba298d91bde171ede58ba6df10bee691cbe7bfabd5276c689885003 ]] \
  || fail_test 'historical release predecessor does not match the reviewed digest'
git -C "${SOURCE_DIR}" show \
  '9eacd058c51860d30fb526acd7340ec4e233b4bc:ops/worker/atenea-workspace-release-v1.py' \
  >"${TEST_ROOT}/release-bacc-retained.py"
[[ "$(sha256sum "${TEST_ROOT}/release-bacc-retained.py" | cut -d' ' -f1)" == \
    baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0 ]] \
  || fail_test 'historical retained predecessor does not match the reviewed digest'
bundle_create_current
cp "${TEST_ROOT}/release-4bc-predecessor.py" "${RELEASE_PROGRAM}"
chmod 0755 "${RELEASE_PROGRAM}"
mkdir -p "${RETAINED_PREDECESSOR_ROOT}"
chmod 0700 "${RETAINED_PREDECESSOR_ROOT}"
cp "${TEST_ROOT}/release-bacc-retained.py" "${RETAINED_RELEASE_PROGRAM}"
chmod 0755 "${RETAINED_RELEASE_PROGRAM}"
[[ "$(activation_bundle_preflight)" == release-successor-predecessor ]] \
  || fail_test 'exact 4bc release predecessor was not accepted for promotion'
if ( verify ) >"${TEST_ROOT}/final-rejection" 2>&1; then
  fail_test 'final verification accepted the 4bc release predecessor'
fi
grep -Fq 'installed release mediator is not current' "${TEST_ROOT}/final-rejection" \
  || fail_test '4bc final verification rejected for an unrelated reason'
apply_install >/dev/null
[[ "$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)" == \
    aa02b2a7d2179c5607666e3f4a2150d917f37da12e3ab3f12965594ceabfc3f4 ]] \
  || fail_test 'exact 4bc transition did not install the aa02 target'
[[ "$(sha256sum "${RETAINED_RELEASE_PROGRAM}" | cut -d' ' -f1)" == \
    baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0 ]] \
  || fail_test 'exact bacc retained predecessor was changed by promotion'
verify >/dev/null
printf 'foreign release mediator\n' >"${RELEASE_PROGRAM}"
chmod 0755 "${RELEASE_PROGRAM}"
if ( activation_bundle_preflight ) >"${TEST_ROOT}/release-rejection" 2>&1; then
  fail_test 'foreign release mediator was accepted for promotion'
fi
grep -Fq 'installed release mediator is not an accepted predecessor' \
  "${TEST_ROOT}/release-rejection" \
  || fail_test 'foreign release mediator rejected for an unrelated reason'
printf 'PASS: exact 4bc-to-aa02 release promotion retains bacc and rejects foreign provenance\n'
bundle_reset

# Reconstruct the immediate Git predecessor of 78256ad from the packaged target.
# Check real bytes against fixed digests; do not substitute the allowlisted SHA.
bundle_create_current
sed 's/git init -q --bare --shared=0660 "${TEMP_MIRROR}"/git init -q --bare "${TEMP_MIRROR}"/' \
  "${SOURCE_DIR}/session-workspace-v1.sh" >"${TEST_ROOT}/session-workspace-predecessor.sh"
[[ "$(sha256sum "${TEST_ROOT}/session-workspace-predecessor.sh" | cut -d' ' -f1)" == \
    3e41ae7f218f360920bed7cd4b2d75cab5396bb07649635694db3271b12d2ffe ]] \
  || fail_test 'historical session workspace fixture does not match the exact predecessor'
[[ "$(sha256sum "${SOURCE_DIR}/session-workspace-v1.sh" | cut -d' ' -f1)" == \
    09818d9b717ec8939137a8c5b7aac634f954d40596cf35d909fd04aa374df213 ]] \
  || fail_test 'packaged session workspace target changed'
cp "${TEST_ROOT}/session-workspace-predecessor.sh" "${WORKER_BUNDLE}/session-workspace-v1.sh"
[[ "$(stat -c %U:%G:%a "${WORKER_BUNDLE}/session-workspace-v1.sh")" == atenea-worker:atenea:750 ]] \
  || fail_test 'dependency predecessor identity differs'
[[ "$(activation_bundle_preflight)" == current ]] \
  || fail_test 'exact dependency predecessor was rejected by upgrade preflight'
if ( verify ) >"${TEST_ROOT}/final-rejection" 2>&1; then
  fail_test 'final verification accepted the old dependency with current authority'
fi
grep -Fq 'installed activation dependency is foreign: session-workspace-v1.sh' \
  "${TEST_ROOT}/final-rejection" || fail_test 'final verification rejected for an unrelated reason'
# Exercise the existing predecessor authority with the target release mediator.
chmod 0640 "${SUDOERS}"
release_preflight_predecessor_sudoers_content >"${SUDOERS}"
chmod 0440 "${SUDOERS}"
[[ "$(activation_bundle_preflight)" == rollback-routing-predecessor ]] \
  || fail_test 'old dependency and new bundle failed predecessor preflight'
printf 'PASS: exact old dependency + new bundle upgrade preflight\n'
apply_install >/dev/null
[[ "$(sha256sum "${WORKER_BUNDLE}/session-workspace-v1.sh" | cut -d' ' -f1)" == \
    09818d9b717ec8939137a8c5b7aac634f954d40596cf35d909fd04aa374df213 ]] \
  || fail_test 'simulated installation did not install the exact target'
verify >/dev/null
apply_install >/dev/null
verify >/dev/null
printf 'PASS: target final verification and idempotent sandbox installation\n'
cp "${TEST_ROOT}/session-workspace-predecessor.sh" "${WORKER_BUNDLE}/session-workspace-v1.sh"
if ( verify ) >"${TEST_ROOT}/final-rejection" 2>&1; then
  fail_test 'final verification accepted an old dependency restored after installation'
fi
grep -Fq 'installed activation dependency is foreign: session-workspace-v1.sh' \
  "${TEST_ROOT}/final-rejection" || fail_test 'post-install verification rejected for an unrelated reason'
printf 'PASS: old dependency rejected by final verification after simulated installation\n'
for content in arbitrary altered; do
  if [[ "${content}" == arbitrary ]]; then
    printf 'third arbitrary dependency\n' >"${WORKER_BUNDLE}/session-workspace-v1.sh"
  else
    cp "${TEST_ROOT}/session-workspace-predecessor.sh" "${WORKER_BUNDLE}/session-workspace-v1.sh"
    printf '# altered predecessor\n' >>"${WORKER_BUNDLE}/session-workspace-v1.sh"
  fi
  [[ "$(stat -c %U:%G:%a "${WORKER_BUNDLE}/session-workspace-v1.sh")" == atenea-worker:atenea:750 ]] \
    || fail_test 'negative fixture lost its accepted ownership/mode'
  if ( activation_bundle_preflight ) >"${TEST_ROOT}/dependency-rejection" 2>&1; then
    fail_test "${content} dependency was accepted"
  fi
  grep -Fq 'installed activation dependency is foreign: session-workspace-v1.sh' \
    "${TEST_ROOT}/dependency-rejection" || fail_test 'foreign dependency rejected for an unrelated reason'
  printf 'PASS: %s dependency rejected as foreign with correct ownership/mode\n' "${content}"
done
bundle_reset

mkdir -p "$(dirname -- "${SUDOERS}")"
mkdir -p "$(dirname -- "${RELEASE_STATE_ROOT}")"
chmod 2770 "$(dirname -- "${RELEASE_STATE_ROOT}")"
applied="$(apply_install)"
jq -e '.state == "verified" and .releaseEnabledByDefault == false' \
  <<<"${applied}" >/dev/null || fail_test 'sandbox apply did not return exact verification'
[[ "$("${STAT_BIN}" -c %a "${RELEASE_STATE_ROOT}")" == 700 ]] \
  || fail_test 'apply retained an inherited setgid bit on the journal root'
[[ "$(activation_bundle_preflight)" == current ]] \
  || fail_test 'sandbox apply did not install the exact current bundle'
printf 'retained after apply\n' >"${RELEASE_STATE_ROOT}/apply-operation.json"
apply_retained_before="$(sha256sum "${RELEASE_STATE_ROOT}/apply-operation.json")"
apply_install >/dev/null
[[ "${apply_retained_before}" == \
    "$(sha256sum "${RELEASE_STATE_ROOT}/apply-operation.json")" ]] \
  || fail_test 'idempotent apply changed a retained release operation'
bundle_reset

bundle_create_capacity_diagnosis_predecessor
RELEASE_PROGRAM_PREDECESSOR_SHA256="$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)"
[[ "$(activation_bundle_preflight)" == upgrade ]] \
  || fail_test 'capacity-diagnosis predecessor was not accepted for upgrade'
apply_install >/dev/null
[[ "$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)" == "${RELEASE_PROGRAM_SHA256}" ]] \
  || fail_test 'capacity-diagnosis predecessor was not upgraded exactly'
[[ "$(cat "${SUDOERS}")" == "$(sudoers_content)" ]] \
  || fail_test 'release-preflight sudo authority was not installed exactly'
RELEASE_PROGRAM_PREDECESSOR_SHA256=4bc09eadbba298d91bde171ede58ba6df10bee691cbe7bfabd5276c689885003
bundle_reset

bundle_create_release_preflight_predecessor
RELEASE_PROGRAM_PREDECESSOR_SHA256="$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)"
preapply_rollback="$(rollback_install)"
jq -e '.changed == false and .releaseAuthority == true and
  .retainedStaticPredecessor == false' <<<"${preapply_rollback}" >/dev/null \
  || fail_test 'unapplied live predecessor rollback was not an unchanged result'
mkdir -p "${RETAINED_PREDECESSOR_ROOT}"
chmod 0700 "${RETAINED_PREDECESSOR_ROOT}"
printf 'foreign retained predecessor\n' >"${RETAINED_RELEASE_PROGRAM}"
chmod 0755 "${RETAINED_RELEASE_PROGRAM}"
before="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
if ( apply_install ) >/dev/null 2>&1; then
  fail_test 'apply accepted a foreign retained release predecessor'
fi
after="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
[[ "${before}" == "${after}" ]] \
  || fail_test 'rejected retained predecessor changed the installed bundle'
RELEASE_PROGRAM_PREDECESSOR_SHA256=4bc09eadbba298d91bde171ede58ba6df10bee691cbe7bfabd5276c689885003
bundle_reset

bundle_create_release_preflight_predecessor
cp "${TEST_ROOT}/release-4bc-predecessor.py" "${RELEASE_PROGRAM}"
chmod 0755 "${RELEASE_PROGRAM}"
mkdir -p "${RETAINED_PREDECESSOR_ROOT}"
chmod 0700 "${RETAINED_PREDECESSOR_ROOT}"
cp "${TEST_ROOT}/release-bacc-retained.py" "${RETAINED_RELEASE_PROGRAM}"
chmod 0755 "${RETAINED_RELEASE_PROGRAM}"
cp "${TEST_ROOT}/session-workspace-predecessor.sh" "${WORKER_BUNDLE}/session-workspace-v1.sh"
[[ "$(activation_bundle_preflight)" == rollout-predecessor ]] \
  || fail_test 'live release-preflight predecessor was not accepted for upgrade'
if ( verify ) >/dev/null 2>&1; then
  fail_test 'installed verifier accepted the release predecessor as current'
fi
apply_install >/dev/null
[[ "$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)" == "${RELEASE_PROGRAM_SHA256}" ]] \
  || fail_test 'release predecessor was not upgraded to the exact source'
[[ -f "${RETAINED_RELEASE_PROGRAM}" &&
    "$(sha256sum "${RETAINED_RELEASE_PROGRAM}" | cut -d' ' -f1)" == \
      "${RETAINED_RELEASE_PROGRAM_SHA256}" ]] \
  || fail_test 'live release predecessor was not retained exactly'
printf 'foreign retained rollback predecessor\n' >"${RETAINED_RELEASE_PROGRAM}"
chmod 0755 "${RETAINED_RELEASE_PROGRAM}"
before="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
if ( rollback_install ) >/dev/null 2>&1; then
  fail_test 'rollback accepted a foreign retained release predecessor'
fi
after="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
[[ "${before}" == "${after}" ]] \
  || fail_test 'rejected retained rollback predecessor changed the installed bundle'
cp "${TEST_ROOT}/release-bacc-retained.py" "${RETAINED_RELEASE_PROGRAM}"
chmod 0755 "${RETAINED_RELEASE_PROGRAM}"
live_predecessor_hash="${RETAINED_RELEASE_PROGRAM_SHA256}"
live_rollback="$(rollback_install)"
jq -e '.state == "rolled-back" and .changed == true and
  .releaseAuthority == true and .retainedStaticPredecessor == true' \
  <<<"${live_rollback}" >/dev/null \
  || fail_test 'live predecessor rollback result is not exact'
[[ "$(activation_bundle_preflight)" == rollout-predecessor &&
    "$(sha256sum "${RELEASE_PROGRAM}" | cut -d' ' -f1)" == "${live_predecessor_hash}" &&
    "$(cat "${SUDOERS}")" == "$(release_preflight_predecessor_sudoers_content)" ]] \
  || fail_test 'rollback did not restore the complete live predecessor'
live_repeat="$(rollback_install)"
jq -e '.changed == false and .releaseAuthority == true and
  .retainedStaticPredecessor == true' <<<"${live_repeat}" >/dev/null \
  || fail_test 'repeated live predecessor rollback was not idempotent'
bundle_reset

mkdir -p "$(dirname -- "${PROGRAM}")"
cp "${SOURCE_DIR}/atenea-workspace-activation-v1.sh" "${PROGRAM}"
chmod 0755 "${PROGRAM}"
if ( activation_bundle_preflight ) >/dev/null 2>&1; then
  fail_test 'partial activation bundle was accepted'
fi

bundle_reset
bundle_create_predecessor
[[ "$(activation_bundle_preflight)" == predecessor ]] \
  || fail_test 'exact predecessor activation bundle was not accepted'

mkdir -p "${RELEASE_STATE_ROOT}"
chmod 0700 "${RELEASE_STATE_ROOT}"
printf 'retained journal\n' >"${RELEASE_STATE_ROOT}/retained-operation.json"
[[ "$(activation_bundle_preflight)" == predecessor ]] \
  || fail_test 'predecessor rejected retained release journals'

bundle_reset
bundle_create_current
[[ "$(activation_bundle_preflight)" == current ]] \
  || fail_test 'exact current activation bundle was not accepted'
verified="$(verify)"
jq -e '.state == "verified" and .projectId == "atenea" and
  .releaseEnabledByDefault == false and .arbitraryAuthority == false' \
  <<<"${verified}" >/dev/null || fail_test 'installed verifier result is not closed'

bundle_reset
bundle_create_predecessor
printf 'reviewed predecessor fixture\n' >"${PROGRAM}"
chmod 0755 "${PROGRAM}"
PROGRAM_PREDECESSOR_SHA256="$(sha256sum "${PROGRAM}" | cut -d' ' -f1)"
[[ "$(activation_bundle_preflight)" == predecessor ]] \
  || fail_test 'exact predecessor activation bundle was not accepted'

printf 'foreign activation fixture\n' >"${PROGRAM}"
chmod 0755 "${PROGRAM}"
PROGRAM_PREDECESSOR_SHA256="$(printf '0%.0s' {1..64})"
before="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
if ( activation_bundle_preflight ) >/dev/null 2>&1; then
  fail_test 'foreign activation program was accepted'
fi
after="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
[[ "${before}" == "${after}" ]] || fail_test 'rejected bundle was modified'

bundle_reset
PROGRAM_PREDECESSOR_SHA256=61fc03da468f2f9fa1fb101dc42129a773f02acaacbc40fd46e18d7a06724df2
bundle_create_current
mv "${PROGRAM}" "${PROGRAM}.target"
ln -s "${PROGRAM}.target" "${PROGRAM}"
if ( activation_bundle_preflight ) >/dev/null 2>&1; then
  fail_test 'symlinked activation program was accepted'
fi

bundle_reset
bundle_create_current
printf 'foreign dependency\n' >"${WORKER_BUNDLE}/${DEPENDENCIES[1]}"
chmod 0750 "${WORKER_BUNDLE}/${DEPENDENCIES[1]}"
if ( activation_bundle_preflight ) >/dev/null 2>&1; then
  fail_test 'foreign activation dependency was accepted'
fi

bundle_reset
bundle_create_current
printf 'foreign release mediator\n' >"${RELEASE_PROGRAM}"
chmod 0755 "${RELEASE_PROGRAM}"
before="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
if ( rollback_install ) >/dev/null 2>&1; then
  fail_test 'rollback removed a foreign release mediator'
fi
after="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
[[ "${before}" == "${after}" ]] || fail_test 'rejected rollback modified a foreign bundle'

bundle_reset
bundle_create_current
chmod 0600 "${SUDOERS}"
printf '%s\n' \
  'atenea-worker ALL=(root) NOPASSWD: /usr/local/libexec/atenea/atenea-workspace-release-v1.py *' \
  >>"${SUDOERS}"
chmod 0440 "${SUDOERS}"
before="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
if ( rollback_install ) >/dev/null 2>&1; then
  fail_test 'rollback accepted broadened release sudo authority'
fi
after="$(find "${TEST_ROOT}" -type f -print0 | sort -z | xargs -0 sha256sum)"
[[ "${before}" == "${after}" ]] || fail_test 'rejected broad sudoers was modified'

bundle_reset
bundle_create_current
printf 'retained operation\n' >"${RELEASE_STATE_ROOT}/operation.json"
printf 'unrelated retained\n' >"${TEST_ROOT}/unrelated-operation"
before_retained="$(sha256sum "${RELEASE_STATE_ROOT}/operation.json" \
  "${TEST_ROOT}/unrelated-operation")"
first_rollback="$(rollback_install)"
jq -e '.state == "rolled-back" and .changed == true and
  .releaseAuthority == false and .retainedJournals == true' \
  <<<"${first_rollback}" >/dev/null || fail_test 'first rollback result is not exact'
[[ ! -e "${RELEASE_PROGRAM}" && "$(activation_bundle_preflight)" == predecessor ]] \
  || fail_test 'rollback did not restore the exact predecessor'
[[ "$(cat "${SUDOERS}")" == "$(predecessor_sudoers_content)" ]] \
  || fail_test 'rollback did not remove only release sudo authority'
after_retained="$(sha256sum "${RELEASE_STATE_ROOT}/operation.json" \
  "${TEST_ROOT}/unrelated-operation")"
[[ "${before_retained}" == "${after_retained}" ]] \
  || fail_test 'rollback changed retained or unrelated operations'
second_rollback="$(rollback_install)"
jq -e '.changed == false and .releaseAuthority == false' \
  <<<"${second_rollback}" >/dev/null || fail_test 'repeated rollback was not idempotent'

bundle_reset
bundle_create_current
chmod 0600 "${SUDOERS}"
predecessor_sudoers_content >"${SUDOERS}"
chmod 0440 "${SUDOERS}"
[[ "$(activation_bundle_preflight)" == rollback-disabled ]] \
  || fail_test 'disabled rollback successor was not recognized'
rollback_install >/dev/null
[[ "$(activation_bundle_preflight)" == predecessor ]] \
  || fail_test 'interrupted rollback did not resume to the predecessor'

[[ "$(sudoers_content | wc -l)" -eq 5 ]] || fail_test 'sudoers rule count is not exact'
[[ "$(release_preflight_predecessor_sudoers_content | wc -l)" -eq 4 ]] \
  || fail_test 'live predecessor sudoers rule count is not exact'
! release_preflight_predecessor_sudoers_content \
  | grep -F -- '--diagnose-unactivated' >/dev/null \
  || fail_test 'live predecessor unexpectedly contains successor authority'
[[ "$(sudoers_content | grep -Fxc \
  "atenea-worker ALL=(root) NOPASSWD: ${RELEASE_PROGRAM}")" -eq 1 ]] \
  || fail_test 'release sudo authority without arguments is missing'
[[ "$(sudoers_content | grep -Fxc \
  "atenea-worker ALL=(root) NOPASSWD: ${RELEASE_PROGRAM} --diagnose-capacity-owner")" \
  -eq 1 ]] || fail_test 'capacity diagnosis sudo authority is not exact'
[[ "$(sudoers_content | grep -Fxc \
  "atenea-worker ALL=(root) NOPASSWD: ${RELEASE_PROGRAM} --diagnose-release-preflight")" \
  -eq 1 ]] || fail_test 'release-preflight sudo authority is not exact'
[[ "$(sudoers_content | grep -Fxc \
  "atenea-worker ALL=(root) NOPASSWD: ${RELEASE_PROGRAM} --diagnose-unactivated")" \
  -eq 1 ]] || fail_test 'unactivated diagnosis sudo authority is not exact'
! sudoers_content | grep -F "${RELEASE_PROGRAM} *" >/dev/null \
  || fail_test 'release sudo authority is broadened'
grep -Fq 'installed activation bundle changed after preflight' \
  "${SOURCE_DIR}/install-atenea-routing-activation-v1.sh" \
  || fail_test 'apply does not repeat the whole-bundle preflight before writing'
grep -Fq 'installed activation bundle changed after rollback preflight' \
  "${SOURCE_DIR}/install-atenea-routing-activation-v1.sh" \
  || fail_test 'rollback does not repeat the whole-bundle preflight before writing'

printf 'Atenea workspace activation/release installer and rollback tests passed\n'
