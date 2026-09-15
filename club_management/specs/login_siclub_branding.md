# Spec: Login — estética SICLUB

Rediseño visual de la pantalla de login de Desk/portal incorporando la marca
**SICLUB** (*Sistema Integral de Gestión de Clubes Deportivos*).

Relacionado con `login_dual.md` (funcionalidad de acceso); este spec cubre solo
**branding** y copy.

---

## Scenario: pantalla de login muestra marca SICLUB

Given un visitante anónimo en `/login`
When carga la página
Then ve el título **SICLUB** y el subtítulo
  *Sistema Integral de Gestión de Clubes Deportivos*
And el formulario de login sigue siendo usable (email/DNI y contraseña).

---

## Scenario: estilos acotados a login

Given cualquier otra ruta web o Desk autenticado
When se carga la UI
Then los estilos SICLUB **no** alteran layouts fuera de la pantalla de login.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| CSS | `public/css/siclub_login.css` |
| Hook | `hooks.py` → `web_include_css` |
| Tests | `members/tests/test_login_siclub_branding.py` |
