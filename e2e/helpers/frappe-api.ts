import { APIRequestContext } from "@playwright/test";

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
