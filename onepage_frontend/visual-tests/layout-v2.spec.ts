import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";

const fixtures = [
  ["watermark-center-tape", "watermark-center-tape.png"],
  ["watermark-center-clean", "watermark-center-clean.png"],
  ["short-note-focal-center", "short-note-focal-center.png"],
  ["text-forward-long", "text-forward-long.png"],
  ["minimal-text-only", "minimal-text-only.png"],
] as const;

const baselineDir = path.resolve(process.cwd(), "tests/visual-baselines");

for (const [fixture, filename] of fixtures) {
  test(`${fixture} matches baseline`, async ({ page }) => {
    await page.goto(`/visual-test/${fixture}`);
    await page.locator('[data-visual-ready="true"]').waitFor();
    await page.evaluate(() => document.fonts.ready);
    const actual = await page.locator("[data-visual-canvas]").screenshot();
    const baselinePath = path.join(baselineDir, filename);
    if (process.env.UPDATE_VISUAL_BASELINES === "1") {
      fs.mkdirSync(baselineDir, { recursive: true });
      fs.writeFileSync(baselinePath, actual);
      return;
    }
    expect(fs.existsSync(baselinePath), `Missing baseline ${baselinePath}`).toBe(true);
    expect(comparePng(actual, fs.readFileSync(baselinePath))).toBeLessThanOrEqual(0.015);
  });
}

test("editor preview and exported PNG use the same stage", async ({ page }) => {
  await page.goto("/visual-test/watermark-center-tape");
  await page.locator('[data-visual-ready="true"]').waitFor();
  const preview = await page.locator("canvas").first().screenshot();
  const dataUrl = await page.evaluate(() => window.__onepageVisualExport?.());
  expect(dataUrl).toBeTruthy();
  const exported = Buffer.from(String(dataUrl).split(",", 2)[1], "base64");
  expect(comparePng(preview, exported, true)).toBeLessThanOrEqual(0.05);
});

function comparePng(actualBuffer: Buffer, expectedBuffer: Buffer, resizeExpected = false) {
  const actual: PNG = PNG.sync.read(actualBuffer);
  let expected: PNG = PNG.sync.read(expectedBuffer);
  if (actual.width !== expected.width || actual.height !== expected.height) {
    if (!resizeExpected) return 1;
    expected = resizeNearest(expected, actual.width, actual.height);
  }
  const diff = new PNG({ width: actual.width, height: actual.height });
  const mismatched = pixelmatch(actual.data, expected.data, diff.data, actual.width, actual.height, { threshold: 0.12 });
  return mismatched / (actual.width * actual.height);
}

function resizeNearest(source: PNG, width: number, height: number) {
  const output = new PNG({ width, height });
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const sourceX = Math.min(source.width - 1, Math.floor((x / width) * source.width));
      const sourceY = Math.min(source.height - 1, Math.floor((y / height) * source.height));
      const sourceOffset = (sourceY * source.width + sourceX) * 4;
      const targetOffset = (y * width + x) * 4;
      source.data.copy(output.data, targetOffset, sourceOffset, sourceOffset + 4);
    }
  }
  return output;
}
