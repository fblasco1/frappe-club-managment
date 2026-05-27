// CommonJS evita "exports is not defined" al cargar @playwright/test en Node 24.
const path = require("node:path");
const { defineConfig, devices } = require("@playwright/test");

const rootDir = __dirname;
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:8000";
const browserChannel = process.env.PW_CHANNEL || undefined;

/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = defineConfig({
	testDir: path.join(rootDir, "e2e"),
	outputDir: path.join(rootDir, "test-results"),
	timeout: 120_000,
	expect: { timeout: 15_000 },
	fullyParallel: false,
	retries: process.env.CI ? 1 : 0,
	reporter: [
		["list"],
		["html", { open: "never", outputFolder: path.join(rootDir, "playwright-report") }],
	],
	use: {
		baseURL,
		trace: "on-first-retry",
		screenshot: "only-on-failure",
		video: process.env.PW_VIDEO ? "on" : "off",
	},
	projects: [
		{
			name: browserChannel || "chromium",
			use: {
				...devices["Desktop Chrome"],
				...(browserChannel ? { channel: browserChannel } : {}),
			},
		},
	],
});
