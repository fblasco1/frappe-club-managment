import { test, expect } from "@playwright/test";
import path from "node:path";
import {
  fetchPanelListsInBrowser,
  getPanelLists,
  getProyeccionFlujo,
  loginDesk,
  loginDeskPage,
  renderSecretariaPanel,
} from "./helpers/frappe-api";

const SECRETARIA_EMAIL = process.env.QA_SECRETARIA_EMAIL || "secretaria@dev.local";
const SECRETARIA_PASSWORD = process.env.QA_SECRETARIA_PASSWORD || "Secretaria123!";
const ADMIN_EMAIL = process.env.QA_ADMIN_EMAIL || "Administrator";
const ADMIN_PASSWORD = process.env.QA_ADMIN_PASSWORD || "admin";

/** Último día hábil julio 2026 (viernes 31/07). */
const ULTIMO_HABIL_JULIO_2026 = "2026-07-31";

async function attachScreenshot(
  testInfo: import("@playwright/test").TestInfo,
  page: import("@playwright/test").Page,
  name: string,
) {
  const file = path.join(testInfo.outputDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  await testInfo.attach(name, { path: file, contentType: "image/png" });
}

test.describe("Gestión Financiera — E2E Playwright", () => {
  test.skip(
    !process.env.PLAYWRIGHT_BASE_URL && !process.env.CI,
    "Definí PLAYWRIGHT_BASE_URL (ej. http://localhost:8000)",
  );

  test("API — recordatorio sueldos en último día hábil", async ({ request, baseURL }) => {
    await loginDesk(request, baseURL!, SECRETARIA_EMAIL, SECRETARIA_PASSWORD);

    const fuera = await getPanelLists(request, baseURL!, "2026-07-10");
    expect(fuera.recordatorio_sueldos.mostrar).toBe(false);

    const ultimo = await getPanelLists(request, baseURL!, ULTIMO_HABIL_JULIO_2026);
    expect(ultimo.recordatorio_sueldos.mostrar).toBe(true);
    expect(ultimo.recordatorio_sueldos.es_ultimo_dia_habil).toBe(true);
    expect(ultimo.recordatorio_sueldos.conceptos_pendientes.length).toBeGreaterThan(0);
  });

  test("API — proyección flujo de fondos (Tesorería)", async ({ request, baseURL }) => {
    await loginDesk(request, baseURL!, ADMIN_EMAIL, ADMIN_PASSWORD);
    const data = await getProyeccionFlujo(request, baseURL!);
    expect(data).toHaveProperty("saldo_caja_bancos");
    expect(data).toHaveProperty("liquidez_proyectada");
    expect(data.ventana_dias).toBeGreaterThanOrEqual(1);
    expect(data.company).toBeTruthy();
  });

  test("UI — Secretaría muestra banner provisión sueldos", async ({ page, baseURL }, testInfo) => {
    await loginDeskPage(page, baseURL!, SECRETARIA_EMAIL, SECRETARIA_PASSWORD);
    await page.goto("/desk/secretaría");
    await page.waitForSelector("#club-secretaria-lists", { timeout: 45_000 });

    const panelData = await fetchPanelListsInBrowser(page, ULTIMO_HABIL_JULIO_2026);
    expect(panelData.recordatorio_sueldos.mostrar).toBe(true);
    await renderSecretariaPanel(page, panelData);

    await page.waitForSelector(".club-secretaria-sueldos-banner", { timeout: 10_000 });
    await expect(page.locator(".club-secretaria-sueldos-banner")).toContainText(/Provisión de sueldos/i);
    await expect(page.locator(".club-secretaria-sueldos-banner")).toContainText(/Purchase Invoice/i);
    await expect(page.locator(".club-secretaria-nueva-pi")).toBeVisible();
    await attachScreenshot(testInfo, page, "01-secretaria-banner-sueldos");
  });

  test("UI — Tesorería abre reporte Proyección Flujo de Fondos", async ({ page, baseURL }, testInfo) => {
    await loginDeskPage(page, baseURL!, ADMIN_EMAIL, ADMIN_PASSWORD);

    await page.goto("/desk/query-report/Proyeccion%20Flujo%20de%20Fondos");
    await page.waitForLoadState("domcontentloaded");
    await expect(page).not.toHaveURL(/login/);
    await expect(page.locator("body")).not.toContainText(/Error del Servidor/i);
    await expect(page.locator(".page-title")).toContainText(/Proyeccion Flujo de Fondos/i);
    await page.waitForSelector(".dt-row, .report-summary", { timeout: 30_000 });
    await attachScreenshot(testInfo, page, "02-tesoreria-reporte-flujo-fondos");
  });

  test("UI — Secretaría sin banner fuera del último día hábil", async ({ page, baseURL }, testInfo) => {
    await loginDeskPage(page, baseURL!, SECRETARIA_EMAIL, SECRETARIA_PASSWORD);
    await page.goto("/desk/secretaría");
    await page.waitForSelector("#club-secretaria-lists", { timeout: 30_000 });

    const panelData = await fetchPanelListsInBrowser(page, "2026-07-10");
    expect(panelData.recordatorio_sueldos.mostrar).toBe(false);
    await renderSecretariaPanel(page, panelData);

    await expect(page.locator(".club-secretaria-sueldos-banner")).toHaveCount(0);
    await attachScreenshot(testInfo, page, "03-secretaria-sin-banner");
  });
});
