"""Suite dirigida del portal socio (perfil, inscripción, sesión).

Uso: ``bench --site dev.localhost run-tests --module club_management.members.test_portal_socio``
"""

from __future__ import annotations

import unittest

_PORTAL_MODULES = (
	"club_management.members.tests.test_portal_socio_perfil",
	"club_management.activities.tests.test_portal_socio_inscripcion",
	"club_management.activities.tests.test_portal_socio_url",
)


def load_tests(
	loader: unittest.TestLoader,
	_tests: unittest.TestSuite,
	_pattern: str | None,
) -> unittest.TestSuite:
	suite = unittest.TestSuite()
	for module_name in _PORTAL_MODULES:
		suite.addTests(loader.loadTestsFromName(module_name))
	return suite
