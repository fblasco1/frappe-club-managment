from __future__ import annotations

import unittest
from datetime import datetime, timezone

from club_management.integrations.scheduler_postgres import naive_datetime


class TestSchedulerPostgres(unittest.TestCase):
	def test_naive_datetime_strips_tz(self) -> None:
		aware = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
		naive = naive_datetime(aware)
		self.assertIsNone(naive.tzinfo)
		self.assertEqual(naive, datetime(2026, 9, 1, 12, 0))

	def test_naive_datetime_keeps_naive(self) -> None:
		original = datetime(2026, 9, 1, 12, 0)
		self.assertIs(naive_datetime(original), original)

	def test_naive_comparison_avoids_type_error(self) -> None:
		aware = datetime(2026, 6, 19, 0, 0, 2, tzinfo=timezone.utc)
		naive_now = datetime(2026, 9, 1, 14, 0)
		self.assertLessEqual(naive_datetime(aware), naive_now)


if __name__ == "__main__":
	unittest.main()
