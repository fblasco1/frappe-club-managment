import { APIRequestContext, Page } from "@playwright/test";

export type SubmitPayload = Record<string, unknown>;

export async function submitSolicitud(
  request: APIRequestContext,
  baseURL: string,
  payload: SubmitPayload,
): Promise<{ token_seguimiento: string }> {
  const res = await request.post(
    `${baseURL}/api/method/club_management.members.api.solicitud_publica.submit_solicitud`,
    {
      form: { data: JSON.stringify(payload) },
    },
  );
  if (!res.ok()) {
    throw new Error(`submit_solicitud failed: ${res.status()} ${await res.text()}`);
  }
  const body = await res.json();
  const message = body.message as { token_seguimiento: string };
  return message;
}

export async function consultarSolicitud(
  request: APIRequestContext,
  baseURL: string,
  token: string,
): Promise<{ workflow_state: string }> {
  const res = await request.get(
    `${baseURL}/api/method/club_management.members.api.solicitud_publica.consultar_solicitud`,
    { params: { token } },
  );
  if (!res.ok()) {
    throw new Error(`consultar_solicitud failed: ${res.status()}`);
  }
  const body = await res.json();
  return body.message as { workflow_state: string };
}

export async function loginDesk(
  request: APIRequestContext,
  baseURL: string,
  email: string,
  password: string,
): Promise<void> {
  const res = await request.post(`${baseURL}/api/method/login`, {
    form: { usr: email, pwd: password },
  });
  if (!res.ok()) {
    throw new Error(`login failed: ${res.status()} ${await res.text()}`);
  }
}

/** Login vía API compartiendo cookies con `page` (necesario para tests UI). */
export async function loginDeskPage(
  page: Page,
  baseURL: string,
  email: string,
  password: string,
): Promise<void> {
  const res = await page.request.post(`${baseURL}/api/method/login`, {
    form: { usr: email, pwd: password },
  });
  if (!res.ok()) {
    throw new Error(`login failed: ${res.status()} ${await res.text()}`);
  }
}

export async function callWhitelisted<T = Record<string, unknown>>(
  request: APIRequestContext,
  baseURL: string,
  method: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  const res = await request.post(`${baseURL}/api/method/${method}`, {
    data: args,
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok()) {
    throw new Error(`${method} failed: ${res.status()} ${await res.text()}`);
  }
  const body = await res.json();
  return body.message as T;
}

export type RecordatorioSueldosPayload = {
  mostrar: boolean;
  es_ultimo_dia_habil: boolean;
  conceptos_pendientes: Array<{ key: string; label: string; item_code: string }>;
  mensaje: string;
};

export async function getPanelLists(
  request: APIRequestContext,
  baseURL: string,
  referenceDate?: string,
): Promise<{ recordatorio_sueldos: RecordatorioSueldosPayload }> {
  return callWhitelisted(request, baseURL, "club_management.members.api.secretaria_workspace.get_panel_lists", {
    ...(referenceDate ? { reference_date: referenceDate } : {}),
    tendencia_reference_date: "2026-07-01",
  });
}

export async function fetchPanelListsInBrowser(
  page: Page,
  referenceDate: string,
): Promise<{ recordatorio_sueldos: RecordatorioSueldosPayload } & Record<string, unknown>> {
  await page.waitForFunction(
    () =>
      Boolean(
        (window as { frappe?: { call?: unknown } }).frappe?.call
          && (window as { club_management?: { secretaria_panel?: unknown } }).club_management?.secretaria_panel,
      ),
    { timeout: 45_000 },
  );

  return page.evaluate(async (date) => {
    return await new Promise<Record<string, unknown>>((resolve, reject) => {
      (window as { frappe: { call: (opts: Record<string, unknown>) => void } }).frappe.call({
        method: "club_management.members.api.secretaria_workspace.get_panel_lists",
        args: {
          reference_date: date,
          tendencia_reference_date: "2026-07-01",
        },
        callback: (r: { message: Record<string, unknown> }) => resolve(r.message),
        error: (err: unknown) => reject(err),
      });
    });
  }, referenceDate) as Promise<{ recordatorio_sueldos: RecordatorioSueldosPayload } & Record<string, unknown>>;
}

export async function renderSecretariaPanel(page: Page, panelData: Record<string, unknown>): Promise<void> {
  await page.evaluate((data) => {
    const panel = (window as {
      club_management?: { secretaria_panel?: { render_lists: (el: unknown, payload: unknown) => void } };
    }).club_management?.secretaria_panel;
    const $panel = (window as { $?: (sel: string) => { length: number } }).$("#club-secretaria-lists");
    if (panel && $panel?.length) {
      panel.render_lists($panel, data);
    }
  }, panelData);
}

export type ProyeccionFlujoPayload = {
  saldo_caja_bancos: number;
  liquidez_proyectada: number;
  ventana_dias: number;
  company: string;
};

export async function getProyeccionFlujo(
  request: APIRequestContext,
  baseURL: string,
): Promise<ProyeccionFlujoPayload> {
  return callWhitelisted(
    request,
    baseURL,
    "club_management.finance.api.tesoreria_desk.get_proyeccion_flujo_fondos",
    {},
  );
}
