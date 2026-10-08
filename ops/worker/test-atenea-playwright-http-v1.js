"use strict";
// HTTP regression without browser dependencies or any real App credentials.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { before, after, test } = require("node:test");
const root = fs.mkdtempSync(path.join(os.tmpdir(), "atenea-playwright-http-"));
process.env.ATENEA_PLAYWRIGHT_TEST_MODE = "1";
process.env.ATENEA_PLAYWRIGHT_STATIC_ROOT = root;
process.env.ATENEA_PLAYWRIGHT_ARTIFACT_ROOT = root;
const { handleRequest } = require("./atenea-playwright-validation-v1.js");
let server, base;
before(async () => {
  fs.writeFileSync(path.join(root, "index.html"), "<!doctype html><body>Anonymous login</body>");
  fs.writeFileSync(path.join(root, "app.js"), "console.log('static asset');");
  server = http.createServer(handleRequest);
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  if (server) {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
  fs.rmSync(root, { recursive: true, force: true });
});
test("refresh is anonymous JSON 401, never HTML or fabricated session", async () => {
  for (const suffix of ["", "?cache=0"]) {
    const response = await fetch(base + "/api/web/auth/refresh" + suffix, {
      method: "POST", headers: { cookie: "synthetic=ignored", authorization: "Bearer synthetic" },
    });
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("content-type"), "application/json");
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("set-cookie"), null);
    assert.deepEqual(await response.json(), { code: "NO_SESSION" });
  }
});
test("unsupported auth methods reject without a successful session", async () => {
  for (const method of ["GET", "PUT", "DELETE"]) {
    const response = await fetch(base + "/api/web/auth/refresh", { method });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("allow"), "POST");
    assert.deepEqual(await response.json(), { code: "NO_SESSION" });
  }
});
test("other APIs do not fall back to the SPA or imply backend health", async () => {
  for (const endpoint of ["/api", "/api/projects", "/api/web/auth/login", "/api/web/auth/refresh/"]) {
    const response = await fetch(base + endpoint, { method: "POST" });
    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { code: "API_NOT_AVAILABLE" });
  }
});
test("ordinary GET assets and SPA navigation still render", async () => {
  for (const endpoint of ["/", "/index.html", "/conversation?session=21"]) {
    const response = await fetch(base + endpoint);
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type"), /^text\/html/);
    assert.match(await response.text(), /Anonymous login/);
  }
  const asset = await fetch(base + "/app.js");
  assert.equal(asset.headers.get("content-type"), "application/javascript");
  assert.match(await asset.text(), /static asset/);
});
test("HEAD stays empty and non-GET page requests cannot return HTML 200", async () => {
  const head = await fetch(base + "/", { method: "HEAD" });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), "");
  const post = await fetch(base + "/conversation", { method: "POST" });
  assert.equal(post.status, 405);
  assert.equal(post.headers.get("allow"), "GET, HEAD");
});
