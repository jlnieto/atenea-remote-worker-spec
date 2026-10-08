"use strict";

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");

const testMode = process.env.ATENEA_PLAYWRIGHT_TEST_MODE === "1";
const staticRoot = testMode ? process.env.ATENEA_PLAYWRIGHT_STATIC_ROOT : "/work/static";
const artifactRoot = testMode ? process.env.ATENEA_PLAYWRIGHT_ARTIFACT_ROOT : "/artifacts";
if (!staticRoot || !artifactRoot
    || (testMode && (!staticRoot.startsWith("/tmp/") || !artifactRoot.startsWith("/tmp/")))) {
  throw new Error("closed Playwright roots are invalid");
}
const viewports = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];
const mime = {
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};
let browser;
let context;
let page;
let server;

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function handleRequest(request, response) {
    const pathname = (request.url || "/").split("?")[0];
    const jsonError = (status, code, allow) => {
      const headers = { "content-type": "application/json", "cache-control": "no-store" };
      if (allow) headers.allow = allow;
      response.writeHead(status, headers);
      response.end(request.method === "HEAD" ? undefined : JSON.stringify({ code }));
    };
    // This is a static, anonymous acceptance boundary, not an App backend.
    // Returning index.html/200 here fabricated a truthy authentication session.
    // Never mint operators/tokens/cookies or contact PROD to render the login.
    if (pathname === "/api/web/auth/refresh") {
      jsonError(request.method === "POST" ? 401 : 405, "NO_SESSION", "POST");
      return;
    }
    if (pathname === "/api" || pathname.startsWith("/api/")) {
      jsonError(404, "API_NOT_AVAILABLE");
      return;
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      jsonError(405, "METHOD_NOT_ALLOWED", "GET, HEAD");
      return;
    }
    const requested = pathname === "/" ? "/index.html" : pathname;
    let file = path.resolve(staticRoot, `.${requested}`);
    if (!file.startsWith(`${staticRoot}/`) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      file = path.join(staticRoot, "index.html");
    }
    response.writeHead(200, { "content-type": mime[path.extname(file)] || "application/octet-stream" });
    if (request.method === "HEAD") response.end();
    else fs.createReadStream(file).pipe(response);
}

async function main() {
  const { chromium } = require("playwright");
  server = http.createServer(handleRequest);
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const port = server.address().port;
  browser = await chromium.launch({ headless: true });
  const results = [];
  for (const viewport of viewports) {
    context = await browser.newContext({ viewport });
    page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.setDefaultNavigationTimeout(30000);
    const response = await page.goto(`http://127.0.0.1:${port}/`, {
      waitUntil: "networkidle",
      timeout: 30000,
    });
    if (!response || response.status() !== 200) throw new Error("fixed page did not return HTTP 200");
    const data = await page.evaluate(() => {
      const body = document.body;
      const text = (body.innerText || "").trim();
      const visible = body.getBoundingClientRect().width > 0 && body.getBoundingClientRect().height > 0;
      return {
        textLength: text.length,
        criticalVisible: visible && text.length > 0,
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      };
    });
    if (!data.criticalVisible || data.horizontalOverflow) throw new Error("fixed DOM acceptance failed");
    const screenshot = path.join(artifactRoot, `${viewport.name}.png`);
    await page.screenshot({ path: screenshot, fullPage: false });
    results.push({
      name: viewport.name,
      width: viewport.width,
      height: viewport.height,
      httpStatus: response.status(),
      textLength: data.textLength,
      criticalVisible: data.criticalVisible,
      horizontalOverflow: data.horizontalOverflow,
      screenshotSha256: sha256(screenshot),
    });
    await page.close();
    page = undefined;
    await context.close();
    context = undefined;
  }
  fs.writeFileSync(path.join(artifactRoot, "report.json"), JSON.stringify({
    schemaVersion: 1,
    viewports: results,
    valuesExposed: false,
  }));
}

module.exports = { handleRequest };

if (require.main === module) main().catch((error) => {
  process.stderr.write(`closed Playwright acceptance failed: ${error.name}\n`);
  process.exitCode = 1;
}).finally(async () => {
  if (page) await page.close().catch(() => {});
  if (context) await context.close().catch(() => {});
  if (browser) await browser.close().catch(() => {});
  if (server) await new Promise((resolve) => server.close(resolve));
});
