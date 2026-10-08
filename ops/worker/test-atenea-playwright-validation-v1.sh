#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/atenea-playwright-validation-v1.js"
SAFE="${ATENEA_PLAYWRIGHT_SAFE:-/home/jose/.local/bin/playwright-safe}"
ROOT="$(mktemp -d /tmp/atenea-playwright-validation-test.XXXXXX)"
STATIC="$ROOT/static"
ARTIFACTS="$ROOT/artifacts"

cleanup() {
  if [[ "${ATENEA_KEEP_TEST_ARTIFACTS:-0}" == "1" ]]; then
    printf 'retained_test_artifacts=%s\n' "$ROOT"
    return
  fi
  case "$ROOT" in
    /tmp/atenea-playwright-validation-test.*)
      find "$ROOT" -type f -delete 2>/dev/null || true
      find "$ROOT" -depth -type d -empty -delete 2>/dev/null || true
      ;;
  esac
}
trap cleanup EXIT
mkdir "$STATIC" "$ARTIFACTS"
cat >"$STATIC/index.html" <<'HTML'
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Atenea validation fixture</title>
  <style>
    body { margin: 0; font: 16px system-ui; background: #f6f7fb; color: #172033; }
    main { max-width: 44rem; margin: 8vh auto; padding: 2rem; }
    h1 { font-size: clamp(1.8rem, 6vw, 3rem); }
    .state { color: #18794e; font-weight: 700; }
    code { overflow-wrap: anywhere; }
  </style>
</head>
<body>
  <main>
    <p class="state">VALIDATION READY</p>
    <h1>Atenea closed Playwright acceptance</h1>
    <p>Data persisted, DOM visible and visual evidence retained.</p>
    <code>remote:ax42-01:work-session:11111111-1111-4111-8111-111111111111</code>
  </main>
  <script>
    // Reproduce the real cookie bootstrap. A fake HTML/200 refresh must fail
    // this acceptance instead of making a session whose operator is undefined.
    document.querySelector('main').hidden = true;
    fetch('/api/web/auth/refresh', { method: 'POST', credentials: 'include' })
      .then(async (response) => {
        if (response.status !== 401 || !response.headers.get('content-type').includes('application/json')) {
          throw new Error('Anonymous bootstrap contract rejected');
        }
        const payload = await response.json();
        if (payload.operator || payload.accessToken || payload.refreshToken) {
          throw new Error('Fabricated session rejected');
        }
        document.querySelector('main').hidden = false;
      });
  </script>
</body>
</html>
HTML

NODE_PATH="$(npm root -g)" \
ATENEA_PLAYWRIGHT_TEST_MODE=1 \
ATENEA_PLAYWRIGHT_STATIC_ROOT="$STATIC" \
ATENEA_PLAYWRIGHT_ARTIFACT_ROOT="$ARTIFACTS" \
  timeout 120s "$SAFE" node "$CHECK"

jq -e '.schemaVersion == 1 and .valuesExposed == false
  and (.viewports | length == 2)
  and ([.viewports[] |
    .httpStatus == 200 and
    .criticalVisible == true and
    .horizontalOverflow == false and
    (.screenshotSha256 | test("^[0-9a-f]{64}$"))
  ] | all)' "$ARTIFACTS/report.json" >/dev/null
[[ -s "$ARTIFACTS/desktop.png" && -s "$ARTIFACTS/mobile.png" ]]
printf 'closed Playwright synthetic validation passed\n'
