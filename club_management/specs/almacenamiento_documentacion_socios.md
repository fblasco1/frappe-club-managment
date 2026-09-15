# Spec: Almacenamiento de documentación de socios (plan multi-club)

Política de **dónde** viven DNI, foto, ficha médica y comprobantes, **qué pasa al renovar**, y **cuándo** el storage deja de ir incluido en el VPS.

**Estado:** política acordada (2026-08-18). Al validar un alta, los adjuntos se **clonan** al `Socio` / `Tutor No Socio` como `File` privado propio. Al renovar, el `File` anterior **se borra** (pisa).

**Relacionado:** `socio_minimo.md`, `tutor_no_socio_minimo.md`, `solicitud_asociacion_publica.md`, `portal_alta_grupo_familiar.md`

---

## Decisión de producto

- Cada socio tiene **un** documento vigente por tipo de campo (`dni_frente`, `dni_dorso`, `foto_perfil`, `ficha_medica`, `comprobante_jubilado`).
- Cada **Tutor No Socio** nuevo tiene **un** vigente de `dni_frente`, `dni_dorso` y `foto_perfil` (sin ficha médica).
- Al **renovar** (ficha médica vencida, DNI nuevo por vencimiento, foto actualizada) el archivo **pisa** al anterior.
- **No** se guarda histórico de versiones. Versionado de File, papeleras eternas o “adjuntos anteriores” quedan fuera de alcance.
- El costo de disco **no se cobra al socio**. En un futuro multi-club se contempla en la **cuota del servicio al club**, no en la cuota social.

Documentación de proceso (specs, UAT, scripts) vive en **git**, no en el File Manager de producción.

---

## Día 1 (un club, ICDPE)

El landing (Vercel Hobby) **no** almacena archivos: proxy ≤ 4 MB hacia Frappe.

Los adjuntos viven en el **disco del site** en Hetzner (CX23, **40 GB** SSD para SO + Docker + Postgres + `files`):

| Pieza | Producción |
|-------|------------|
| Frontend | Vercel Hobby (sin Blob / sin S3) |
| Archivos | Frappe `File` en `sites/<site>/private/files/` |
| Visibilidad | **Privados** (`is_private = 1`). DNI y ficha no van a `/files/` público |
| Backup | `bench backup --with-files` + copias de la VM; el backup de Postgres **no** alcanza |

Volumen típico: **2–4 MB por socio** (4 adjuntos; tope ~4 MB c/u). ~1.200 socios digitalizados ≈ **3–5 GB**. Cabe en el CX23 con holgura si se **pisa** al renovar y no se acumulan fichas anuales.

---

## Scenario: alta valida copia documentación al Socio y al tutor

Given una `Solicitud Asociacion` Validada de un adulto (Activo / Adherente / Jubilado) con adjuntos
When Secretaría valida
Then el `Socio` queda con `File` **privados** propios (`foto_perfil`, `dni_frente`, `dni_dorso`, `ficha_medica`)
And si es Jubilado, también `comprobante_jubilado`
And esos `File` tienen `attached_to_doctype = Socio` (no se comparte el blob con otro socio)

Given una solicitud de **Menor** con DNI/foto del tutor y un `Tutor No Socio` nuevo
When Secretaría valida
Then el menor recibe sus adjuntos en el `Socio`
And el `Tutor No Socio` recibe `dni_frente`, `dni_dorso` y `foto_perfil` privados propios
And si el tutor ya existía con documentación, **no** se pisa con la del hijo.

---

## Scenario: renovación pisa el archivo anterior

Given un `Socio` con `ficha_medica` (o `dni_frente` / `dni_dorso` / `foto_perfil`) ya adjuntada
When Secretaría o el socio sube un archivo **válido** en el mismo campo (renovación de ficha, DNI vencido, foto nueva)
Then el campo apunta solo al archivo nuevo
And el `File` anterior y su blob en disco se **eliminan**
And no queda una versión vieja listable ni recuperable desde Desk.

Given la misma renovación con archivo **inválido** (MIME o tamaño)
When la validación falla
Then el campo **conserva** el archivo vigente
And no se borra el documento anterior.

---

## Scenario: no hay historial de documentación

Given un club con N renovaciones de ficha médica a lo largo de los años
When se mide el disco de adjuntos
Then el crecimiento es ~**un set vigente por socio**, no N años × fichas
And no existe DocType ni child table de “documentos históricos” para estos campos.

---

## Scenario: umbral de infra (un club)

Given el site ICDPE en un CX23 (40 GB)
When los adjuntos vigentes + backups con archivos superan ~**50 % del disco libre** (orden de **~3.000–5.000 socios digitalizados** a 2–4 MB, o antes si hay huérfanos)
Then se evalúa Volume Hetzner o Cloudflare R2
And **no** se abre un cargo por socio.

Given ~10.000 socios digitalizados o una **segunda copia offsite** de archivos
When se cotiza el servicio
Then el extra de infra (Volume / R2 / Storage Box, orden **€3–8/mes**) va en el **costo del servicio al club**.

---

## Scenario: multi-club (futuro)

Given N clubs, cada uno con su **site** Frappe (o tenant equivalente)
When se almacena documentación
Then los archivos de un club no son accesibles desde otro (mismo aislamiento que socios)
And el storage sigue en disco del site o R2 **prefijado por site**
And el precio al club incluye una línea de infra si el tenant no cabe en el disco compartido / free tier de R2 (~10 GB/mes)
And **nunca** un extra de almacenamiento en la cuota social del socio.

R2 u object storage se activa **después** del umbral de disco, no el día 1.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Campos Attach Socio | `members/doctype/socio/` (`foto_perfil`, `dni_frente`, `dni_dorso`, `ficha_medica`, `comprobante_jubilado`) |
| Campos Attach Tutor | `members/doctype/tutor_no_socio/` (`foto_perfil`, `dni_frente`, `dni_dorso`) |
| Alta portal (upload) | landing `app/api/inscripcion/upload` → Frappe `upload_file` (`is_private=1`) |
| Servicio | `members/services/documentacion_adjuntos.py` |
| Copia al validar | `members/services/validar_solicitud.py` |
| Tests | `members/tests/test_documentacion_socio.py` |

---

## Fuera de alcance

- Conservar fichas o DNI viejos “por las dudas”.
- Vercel Blob, AWS S3 o cobrar GB al socio.
- Histórico de Version / File versiones de Frappe para estos campos.
