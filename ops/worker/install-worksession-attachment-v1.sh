#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
CONTROL_PLANE_IP="${ATENEA_CONTROL_PLANE_TAILSCALE_IP:-}"
WORKER_ID="${ATENEA_ATTACHMENT_WORKER_ID:-ax42-01}"
PORT="${ATENEA_ATTACHMENT_WORKER_PORT:-8788}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="atenea-worksession-attachment-v1.service"
PROGRAM="/usr/local/libexec/atenea/worksession-attachment-worker-v1.py"
ENV_FILE="/etc/atenea-worker/worksession-attachment-v1.env"
TOKEN_FILE="/etc/atenea-worker/worksession-attachment-v1.token"
STORAGE_ROOT="/srv/atenea/attachments-v1"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_root() {
  [[ "$(id -u)" -eq 0 ]] || fail "run this action as root"
}

tailscale_ipv4() {
  ip -4 -o address show dev tailscale0 scope global \
    | awk 'NR == 1 { split($4, value, "/"); print value[1] }'
}

validate_inputs() {
  [[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT >= 1024 && PORT <= 65535)) \
    || fail "attachment port must be an unprivileged TCP port"
  [[ "$WORKER_ID" =~ ^[a-zA-Z0-9._-]{1,80}$ ]] || fail "worker id is invalid"
  [[ -f "$SCRIPT_DIR/worksession-attachment-worker-v1.py" ]] || fail "attachment program is missing"
  [[ -f "$SCRIPT_DIR/templates/$SERVICE" ]] || fail "systemd template is missing"
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
    '{
      action: $action,
      workerId: $worker_id,
      bind: $bind,
      port: $port,
      controlPlaneIp: (if $control_plane_ip == "" then null else $control_plane_ip end),
      protocol: "worksession-attachment/v1",
      maxFileBytes: 16777216,
      maxSessionBytes: 268435456,
      storageRoot: "/srv/atenea/attachments-v1",
      tokenValueExposed: false,
      filesystemBrowsing: false,
      arbitraryExecution: false
    }'
}

apply_install() {
  require_root
  validate_inputs
  [[ "$CONTROL_PLANE_IP" =~ ^100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] \
    || fail "ATENEA_CONTROL_PLANE_TAILSCALE_IP must be an exact tailnet IPv4 address"
  local bind
  bind="$(tailscale_ipv4)"
  [[ -n "$bind" ]] || fail "tailscale0 has no global IPv4 address"

  install -d -o root -g root -m 0755 /usr/local/libexec/atenea
  install -o root -g root -m 0755 "$SCRIPT_DIR/worksession-attachment-worker-v1.py" "$PROGRAM"
  install -d -o root -g atenea -m 0750 /etc/atenea-worker
  install -d -o atenea-worker -g atenea -m 0700 "$STORAGE_ROOT"
  if [[ ! -e "$TOKEN_FILE" ]]; then
    umask 0077
    openssl rand -hex 32 >"$TOKEN_FILE"
  fi
  chown root:atenea "$TOKEN_FILE"
  chmod 0640 "$TOKEN_FILE"

  {
    printf 'ATENEA_ATTACHMENT_BIND=%s\n' "$bind"
    printf 'ATENEA_ATTACHMENT_PORT=%s\n' "$PORT"
    printf 'ATENEA_ATTACHMENT_WORKER_ID=%s\n' "$WORKER_ID"
  } >"$ENV_FILE"
  chown root:root "$ENV_FILE"
  chmod 0644 "$ENV_FILE"

  install -o root -g root -m 0644 "$SCRIPT_DIR/templates/$SERVICE" "/etc/systemd/system/$SERVICE"
  systemctl daemon-reload
  ufw allow in on tailscale0 proto tcp from "$CONTROL_PLANE_IP" to any port "$PORT" \
    comment 'atenea-worksession-attachment-v1' >/dev/null
  systemctl enable "$SERVICE"
  systemctl restart "$SERVICE"
  verify
}

verify() {
  require_root
  cmp --silent "$SCRIPT_DIR/worksession-attachment-worker-v1.py" "$PROGRAM" \
    || fail "installed attachment program differs from reviewed source"
  local bind
  bind="$(tailscale_ipv4)"
  systemctl is-enabled "$SERVICE"
  local ready=false
  for _attempt in $(seq 1 60); do
    if systemctl is-active --quiet "$SERVICE" \
        && ss -H -lntp "sport = :$PORT" | grep -F "$bind:$PORT" >/dev/null; then
      ready=true
      break
    fi
    sleep 0.25
  done
  [[ "$ready" == true ]] || fail "attachment service did not become ready within 15 seconds"
  systemctl is-active "$SERVICE"
  systemd-analyze security "$SERVICE" --no-pager >/dev/null
  ! ss -H -lntp "sport = :$PORT" \
      | awk '{ print $4 }' \
      | grep -Eq '^(0\.0\.0\.0|\[::\]):' \
    || fail "attachment service has a wildcard listener"
  [[ "$(stat -c '%a:%U:%G' "$TOKEN_FILE")" == "640:root:atenea" ]] \
    || fail "token file ownership or mode is invalid"
  [[ "$(stat -c '%a:%U:%G' "$STORAGE_ROOT")" == "700:atenea-worker:atenea" ]] \
    || fail "attachment root ownership or mode is invalid"
  printf '%s\n' 'worksession-attachment-v1 verification passed'
}

disable_endpoint() {
  require_root
  systemctl disable --now "$SERVICE"
}

rollback_endpoint() {
  require_root
  [[ "$CONTROL_PLANE_IP" =~ ^100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] \
    || fail "ATENEA_CONTROL_PLANE_TAILSCALE_IP must be an exact tailnet IPv4 address"
  systemctl disable --now "$SERVICE"
  if ufw status | grep -F "$PORT/tcp on tailscale0" | grep -Fq "$CONTROL_PLANE_IP"; then
    ufw --force delete allow in on tailscale0 proto tcp from "$CONTROL_PLANE_IP" \
      to any port "$PORT" comment 'atenea-worksession-attachment-v1' >/dev/null
  fi
}

enable_endpoint() {
  require_root
  systemctl enable --now "$SERVICE"
  verify
}

case "$ACTION" in
  plan) plan ;;
  apply) apply_install ;;
  verify) verify ;;
  disable) disable_endpoint ;;
  rollback) rollback_endpoint ;;
  enable) enable_endpoint ;;
  *) fail "usage: $0 plan|apply|verify|disable|rollback|enable" ;;
esac
