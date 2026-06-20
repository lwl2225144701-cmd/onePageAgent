import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./visual-tests",
  timeout: 45_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3100",
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    launchOptions: {
      executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    },
  },
  webServer: {
    command: "npx next dev -p 3100",
    url: "http://127.0.0.1:3100/visual-test/minimal-text-only",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
