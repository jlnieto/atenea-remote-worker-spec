#!/usr/bin/env bash
# Installation is an explicit one-time operator bootstrap, never an AgentRun.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROGRAM=/usr/local/libexec/atenea/release-control-v1.py
SERVICE=/etc/systemd/system/atenea-release-control-v1.service

unit_content() {
  local writable
  case "${1:-VPS}" in
    VPS) writable='/srv/atenea /run/atenea' ;;
    AX42) writable='/srv/atenea /usr/local/libexec/atenea /usr/local/share/atenea /etc/atenea-worker /etc/systemd/system /etc/sudoers.d /run/atenea' ;;
    *) return 2 ;;
  esac
  printf '%s\n' \
    '[Unit]' 'Description=Atenea fixed-target durable release executor v1' \
    'After=network-online.target tailscaled.service docker.service' 'Wants=network-online.target' \
    '[Service]' 'Type=simple' 'User=root' 'Group=root' \
    'RuntimeDirectory=atenea/release-v1' 'RuntimeDirectoryMode=0755' 'RuntimeDirectoryPreserve=yes' \
    "ExecStartPre=${PROGRAM} --prepare-runtime" "ExecStart=${PROGRAM}" \
    'Restart=on-failure' 'RestartSec=3' 'TimeoutStopSec=15' \
    'UMask=0077' 'PrivateTmp=true' 'ProtectHome=read-only' 'ProtectSystem=strict' \
    'ProtectKernelTunables=true' 'ProtectKernelModules=true' 'ProtectControlGroups=true' \
    "ReadWritePaths=${writable}" \
    'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6' \
    '[Install]' 'WantedBy=multi-user.target'
}

preflight() {
  [[ "$(id -u)" == 0 ]] || { echo 'Root operator installation required' >&2; return 1; }
  /usr/bin/python3 "${SCRIPT_DIR}/release-control-v1.py" --preflight-install
  [[ -d /usr/local/libexec/atenea && ! -L /usr/local/libexec/atenea ]] \
    || { echo 'Existing Atenea libexec authority required' >&2; return 1; }
}

main() {
  [[ "$#" == 1 ]] || { echo 'Usage: install-release-control-v1.sh plan|apply|verify|bootstrap-platform' >&2; return 2; }
  case "$1" in
    plan) preflight; echo 'Release executor preflight passed; no changes made' ;;
    apply)
      preflight
      mode="$(/usr/bin/python3 "${SCRIPT_DIR}/release-control-v1.py" --installation-mode)"
      install -o root -g root -m 0755 "${SCRIPT_DIR}/release-control-v1.py" "$PROGRAM"
      install -d -o root -g root -m 0700 /srv/atenea/release-v1
      unit_content "$mode" >"$SERVICE"
      chown root:root "$SERVICE"; chmod 0644 "$SERVICE"
      "$PROGRAM" --prepare-runtime
      systemd-analyze verify "$SERVICE"
      systemctl daemon-reload
      systemctl enable atenea-release-control-v1.service
      systemctl restart atenea-release-control-v1.service
      ;;
    verify)
      preflight
      mode="$(/usr/bin/python3 "${SCRIPT_DIR}/release-control-v1.py" --installation-mode)"
      cmp --silent "${SCRIPT_DIR}/release-control-v1.py" "$PROGRAM"
      cmp --silent <(unit_content "$mode") "$SERVICE"
      [[ "$(stat -c '%u:%g:%a' "$PROGRAM")" == 0:0:755 ]]
      systemctl is-active --quiet atenea-release-control-v1.service
      "$PROGRAM" --verify-runtime
      echo 'Release executor verification passed'
      ;;
    bootstrap-platform)
      preflight
      # It only adopts an exact already-installed successful main artifact;
      # never installs worker code and never invents an installed predecessor.
      "$PROGRAM" --bootstrap-platform
      ;;
    *) echo 'Unsupported installer operation' >&2; return 2 ;;
  esac
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
