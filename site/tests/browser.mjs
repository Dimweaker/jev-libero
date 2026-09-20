// Build first: python tools/build_site.py --out _site
// npm ci && npx playwright install chromium && npm run test:browser
import { chromium } from "playwright";
import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
import { createServer } from "node:http";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../_site/", import.meta.url));
const results = fileURLToPath(new URL("../test-results/", import.meta.url));
await mkdir(results, { recursive: true });
const mime = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".mp4": "video/mp4",
};
const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  // Serve under a project prefix to catch GitHub Pages path mistakes.
  if (!url.pathname.startsWith("/jev-libero/")) {
    res.writeHead(404).end();
    return;
  }
  let relative = decodeURIComponent(url.pathname.slice("/jev-libero/".length));
  if (!relative) relative = "index.html";
  const path = resolve(root, relative);
  if (!path.startsWith(resolve(root) + sep)) {
    res.writeHead(403).end();
    return;
  }
  try {
    const bytes = await readFile(path);
    const headers = {
      "Content-Type": mime[extname(path)] || "application/octet-stream",
      "Accept-Ranges": "bytes",
    };
    const range = req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
    if (range) {
      const start = Number(range[1]),
        end = range[2]
          ? Math.min(Number(range[2]), bytes.length - 1)
          : bytes.length - 1;
      res
        .writeHead(206, {
          ...headers,
          "Content-Range": `bytes ${start}-${end}/${bytes.length}`,
          "Content-Length": end - start + 1,
        })
        .end(bytes.subarray(start, end + 1));
    } else
      res
        .writeHead(200, { ...headers, "Content-Length": bytes.length })
        .end(bytes);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const origin = `http://127.0.0.1:${server.address().port}/jev-libero/`;
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
    reducedMotion: "reduce",
  });
  const errors = [],
    failed = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) failed.push(response.url());
  });
  await page.goto(origin);
  await page.waitForFunction(
    () =>
      document.querySelector("#explorer").getAttribute("aria-busy") ===
        "false" && document.querySelector("video").readyState >= 2,
  );
  assert.equal(
    await page.$eval("video", (v) => v.paused),
    true,
    "Reduced motion starts paused",
  );
  for (const id of ["microwave", "top-drawer"]) {
    if (id !== "microwave") await page.click(`[data-episode="${id}"]`);
    const data = JSON.parse(
      await readFile(resolve(root, "data", `${id}.json`), "utf8"),
    );
    await page.waitForFunction(
      (title) =>
        document.querySelector("#episode-title").textContent === title &&
        document.querySelector("#explorer").getAttribute("aria-busy") ===
          "false",
      data.title,
    );
    assert.ok(
      Math.abs((await page.$eval("video", (v) => v.duration)) - data.duration) <
        0.06,
    );
    for (const [index, step] of data.steps.entries()) {
      await page.click(`#timeline [data-step="${index}"]`);
      await page.waitForFunction(
        (n) =>
          document
            .querySelector("#decision-counter")
            .textContent.startsWith(String(n + 1).padStart(2, "0")),
        index,
      );
      assert.equal(
        await page.$eval("#action-overlay", (el) => el.textContent),
        (await import("../replay.js")).label(step.choice),
      );
      assert.equal(await page.locator(".action-cell.selected").count(), 1);
      assert.equal(
        await page.locator(".action-cell.selected").getAttribute("data-action"),
        step.choice,
      );
      assert.equal(
        await page.locator(".prob-row.chosen").getAttribute("data-candidate"),
        step.choice,
      );
      assert.equal(
        await page.locator(".flow-card.held").count(),
        3 - step.fresh.length,
      );
    }
    await page.$eval(
      "#seek",
      (el, duration) => {
        el.value = duration;
        el.dispatchEvent(new Event("input", { bubbles: true }));
      },
      data.duration,
    );
    await page.waitForFunction(() =>
      document.querySelector("#outcome").textContent.includes("SUCCESS"),
    );
    assert.equal(
      await page.$eval("#measure", (el) => el.textContent),
      data.samples.at(-1).toFixed(1),
    );
  }
  await page.click('#timeline [data-step="7"]');
  await page.click('[data-layer="intent"]');
  await page.click("#inspect-request");
  assert.equal(await page.$eval("#request-dialog", (el) => el.open), true);
  assert.ok((await page.textContent("#request-json")).includes('"intent"'));
  await page.keyboard.press("Escape");
  assert.equal(await page.$eval("#request-dialog", (el) => el.open), false);
  await page.click('[data-layer="motor"]');
  await page.click("#play");
  const before = await page.$eval("video", (v) => v.currentTime);
  await page.waitForTimeout(500);
  assert.ok((await page.$eval("video", (v) => v.currentTime)) > before);
  await page.click("#play");
  await page.selectOption("#speed", "0.5");
  assert.equal(await page.$eval("video", (v) => v.playbackRate), 0.5);
  await page.selectOption("#projection", "xy");
  await page.click('#timeline [data-step="9"]');
  await page.screenshot({
    path: resolve(results, "desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: resolve(results, "mobile.png"),
    fullPage: true,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
    "No horizontal overflow on mobile",
  );
  await page.click("#next");
  assert.ok((await page.textContent("#decision-counter")).startsWith("11"));
  assert.deepEqual(errors, []);
  assert.deepEqual(failed, []);
  console.log(
    "Browser checks passed: both episodes, all 34 decisions, end states, play/pause, layer inspector, speed, projection, and mobile layout.",
  );
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
