"""Alias del módulo de tests de perfil portal.

Spec: `club_management/specs/portal_socio_perfil.md`

La suite canónica vive en `test_portal_socio_perfil`; este módulo permite
`bench --site … run-tests --module club_management.members.tests.test_portal_perfil`.
"""

from __future__ import annotations

from club_management.members.tests.test_portal_socio_perfil import *  # noqa: F401,F403
from club_management.members.tests.test_portal_socio_perfil import (  # noqa: F401
	TestPortalSocioPerfil,
)
