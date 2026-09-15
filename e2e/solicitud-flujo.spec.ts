import { test, expect } from "@playwright/test";
import {
  consultarSolicitud,
  loginDesk,
  submitSolicitud,
} from "./helpers/frappe-api";

const SECRETARIA_EMAIL = process.env.QA_SECRETARIA_EMAIL || "secretaria@dev.local";
const SECRETARIA_PASSWORD = process.env.QA_SECRETARIA_PASSWORD || "Secretaria123!";

const adultPayload = () => ({
  nombre: "QA",
  apellido: "Playwright",
  dni: String(Date.now()).slice(-8),
  nacionalidad: "Argentina",
  fecha_nacimiento: "1990-01-15",
  genero: "Femenino",
  categoria_solicitada: "Activo",
  email: `qa.pw.${Date.now()}@example.com`,
  telefono: "+541112223344",
  calle: "Calle QA 1",
  localidad: "CABA",
  provincia: "CABA",
  codigo_postal: "1414",
  dni_frente: "/files/test_dni_frente.jpg",
  dni_dorso: "/files/test_dni_dorso.jpg",
  foto_perfil: "/files/test_foto_perfil.jpg",
  ficha_medica: "/files/test_ficha_medica.pdf",
});

test.describe("Solicitud Asociación — E2E UI (supervisado / local)", () => {
  test.skip(
    !process.env.PLAYWRIGHT_BASE_URL && !process.env.CI,
    "Definí PLAYWRIGHT_BASE_URL (ej. http://dev.localhost:8000)",
  );

  test("formulario público carga", async ({ page }) => {
    await page.goto("/solicitud-asociacion");
    await expect(page.locator("body")).toContainText(/solicitud|asociaci/i);
  });

  test("API alta + consulta Pendiente", async ({ request, baseURL }) => {
    const alta = await submitSolicitud(request, baseURL!, adultPayload());
    expect(alta.token_seguimiento).toBeTruthy();
    const estado = await consultarSolicitud(request, baseURL!, alta.token_seguimiento);
    expect(estado.workflow_state).toBe("Pendiente");
  });

  test("Desk login Secretaría (smoke)", async ({ page, request, baseURL }) => {
    await loginDesk(request, baseURL!, SECRETARIA_EMAIL, SECRETARIA_PASSWORD);
    await page.goto("/app");
    await expect(page).not.toHaveURL(/login/);
  });

  test("pago-stub muestra error con token inválido", async ({ page }) => {
    await page.goto("/pago-stub?token=token-invalido-de-prueba");
    await expect(page.locator("body")).toContainText(/no válido|no válido|Enlace/i);
  });

  test("flujo supervisado — pausas manuales", async ({ page, request, baseURL }) => {
    test.skip(!process.env.QA_SUPERVISED, "Set QA_SUPERVISED=1 para pausas manuales");

    const alta = await submitSolicitud(request, baseURL!, adultPayload());
    await loginDesk(request, baseURL!, SECRETARIA_EMAIL, SECRETARIA_PASSWORD);

    await page.goto("/app/solicitud-asociacion");
    test.info().annotations.push({
      type: "token_seguimiento",
      description: alta.token_seguimiento,
    });
    await page.pause();
  });
});
