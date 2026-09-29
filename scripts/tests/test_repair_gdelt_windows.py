from datetime import date, timedelta
import unittest
from scripts.repair_gdelt_windows import windows


class RepairWindowsTest(unittest.TestCase):
    def test_each_daily_sample_covers_exact_four_quarter_hours(self):
        planned = list(windows(date(2026, 9, 1), date(2026, 9, 28)))
        self.assertEqual(len(planned), 28)
        self.assertEqual(planned[0][0].isoformat(), '2026-08-31T23:45:00+00:00')
        self.assertEqual(planned[-1][1].isoformat(), '2026-09-28T00:30:00+00:00')
        for lower, upper in planned:
            self.assertEqual(upper - lower, timedelta(minutes=45))

    def test_rejects_reversed_or_unbounded_repair(self):
        for start, end in [(date(2026, 9, 2), date(2026, 9, 1)), (date(2026, 8, 1), date(2026, 9, 1))]:
            with self.assertRaises(ValueError):
                list(windows(start, end))
