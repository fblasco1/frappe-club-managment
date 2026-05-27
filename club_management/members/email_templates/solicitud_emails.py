"""Plantillas HTML de email — flujo Solicitud de Asociación (Sprint 1)."""

from __future__ import annotations

from frappe.utils import escape_html, get_url


def render_solicitud_validada_email(*, nombre: str, pago_url: str) -> str:
	"""Email post-validación: nombre + link stub de pago (sin DNI ni dirección)."""
	nombre_seguro = escape_html(nombre or "Solicitante")
	pago_url_seguro = escape_html(pago_url)
	return f"""<p>Hola {nombre_seguro},</p>
<p>Tu solicitud de asociación fue <strong>validada</strong>.</p>
<p>Para abonar la primera cuota, usá este enlace:</p>
<p><a href="{pago_url_seguro}">Pagar primera cuota</a></p>
<p>Equipo del club</p>"""


def render_solicitud_rechazada_email(*, nombre: str, motivos_rechazo: str) -> str:
	"""Email de rechazo con `motivos_rechazo` escapado (anti-XSS)."""
	nombre_seguro = escape_html(nombre or "Solicitante")
	motivos_seguros = escape_html(motivos_rechazo or "")
	return f"""<p>Hola {nombre_seguro},</p>
<p>Tu solicitud de asociación fue <strong>rechazada</strong>.</p>
<p>Motivos:</p>
<p>{motivos_seguros}</p>
<p>Equipo del club</p>"""


def render_solicitud_requiere_correccion_email(
	*, nombre: str, token_seguimiento: str, observaciones: str
) -> str:
	"""Email al pedir corrección: token + observaciones escapadas."""
	nombre_seguro = escape_html(nombre or "Solicitante")
	obs_seguras = escape_html(observaciones or "")
	token_seguro = escape_html(token_seguimiento or "")
	consulta_url = escape_html(
		get_url(f"/api/method/club_management.members.api.solicitud_publica.consultar_solicitud?token={token_seguimiento}")
	)
	return f"""<p>Hola {nombre_seguro},</p>
<p>Tu solicitud requiere corrección.</p>
<p>Observaciones:</p>
<p>{obs_seguras}</p>
<p>Tu token de seguimiento: <strong>{token_seguro}</strong></p>
<p>Podés consultar el estado en: <a href="{consulta_url}">seguimiento</a></p>
<p>Equipo del club</p>"""
