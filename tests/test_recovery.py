"""Phase 5 acceptance checks for the recovery layer (SPEC-v3.md section 3).

Run: python3 -m unittest discover -s tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_sessions as an  # noqa: E402

END = date(2026, 11, 8)  # a Sunday; the last finished day in every test


def days(spec, end=END):
    """Build daily records ending on `end`.

    spec is a list, oldest first, of None (no data), a number (active hours)
    or a tuple (active hours, late prompts).
    """
    out = []
    for i, s in enumerate(spec):
        d = end - timedelta(days=len(spec) - 1 - i)
        if s is None:
            out.append({"date": d.isoformat(), "no_data": True, "active_h": 0,
                        "late_prompts": 0})
            continue
        h, late = s if isinstance(s, tuple) else (s, 0)
        out.append({"date": d.isoformat(), "no_data": False, "active_h": h,
                    "late_prompts": late})
    return out


NORMAL_WEEK = [4, 4, 4, 4, 4, 0, 0]  # Mon-Fri work, weekend rest


def with_baseline(week, base_week=NORMAL_WEEK):
    """Four baseline weeks followed by the current week."""
    return days(base_week * 4 + week)


class DayDefinitions(unittest.TestCase):
    def test_rest_late_long_boundaries(self):
        r = an.recovery(days([0.49, 0.5, (1, 3), (1, 2), 8, 7.99, 4]), END)
        w = r["week"]
        self.assertEqual(w["rest_days"], 1)   # 0.49 only
        self.assertEqual(w["late_days"], 1)   # 3 late prompts, not 2
        self.assertEqual(w["long_days"], 1)   # 8 h, not 7.99
        self.assertEqual(w["known_days"], 7)

    def test_ac3a_normal_week(self):
        r = an.recovery(days(NORMAL_WEEK), END)
        self.assertEqual(r["week"]["rest_days"], 2)
        self.assertEqual(r["week"]["late_days"], 0)
        self.assertEqual(r["week"]["active_h"], 20)
        self.assertEqual(r["work_streak"], 0)  # yesterday (END) was empty

    def test_ac3b_unknown_day_is_neither_and_breaks_streak(self):
        r = an.recovery(days([4, 4, 4, None, 4, 4, 4]), END)
        self.assertEqual(r["week"]["known_days"], 6)
        self.assertEqual(r["week"]["rest_days"], 0)
        self.assertEqual(r["work_streak"], 3)

    def test_missing_days_count_as_unknown(self):
        r = an.recovery(days([4, 4]), END)
        self.assertEqual(r["week"]["known_days"], 2)
        self.assertEqual(r["week"]["rest_days"], 0)

    def test_today_is_excluded(self):
        recs = days(NORMAL_WEEK, END) + days([12], END + timedelta(days=1))
        r = an.recovery(recs, END)
        self.assertEqual(r["week"]["active_h"], 20)


class Baseline(unittest.TestCase):
    def test_ac3c_too_few_known_days(self):
        base = [None] * 15 + [4] * 13          # 13 known days in the 28
        r = an.recovery(days(base + NORMAL_WEEK), END)
        self.assertTrue(all(v is None for v in r["baseline"].values()))

    def test_baseline_is_median_of_weeks(self):
        weeks = ([4] * 7) * 2 + NORMAL_WEEK * 2   # rest 0, 0, 2, 2
        r = an.recovery(days(weeks + NORMAL_WEEK), END)
        self.assertEqual(r["baseline"]["rest_days"], 1)


class Flags(unittest.TestCase):
    def flags(self, week, base_week=NORMAL_WEEK):
        return an.recovery(with_baseline(week, base_week), END)["flags"]

    def test_fewer_rest_days(self):
        self.assertIn("fewer_rest_days", self.flags([4, 4, 4, 4, 4, 4, 0]))      # 1 vs 2
        self.assertNotIn("fewer_rest_days", self.flags(NORMAL_WEEK))             # 2 vs 2
        one_rest = [4, 4, 4, 4, 4, 4, 0]
        self.assertNotIn("fewer_rest_days", self.flags(one_rest, one_rest))      # 1 vs 1

    def test_more_late_days(self):
        late1 = [(4, 3), 4, 4, 4, 4, 0, 0]
        self.assertIn("more_late_days",
                      self.flags([(4, 3)] * 3 + [4, 4, 0, 0], late1))            # 3 vs 1
        self.assertNotIn("more_late_days",
                         self.flags([(4, 3)] * 2 + [4, 4, 4, 0, 0], late1))      # 2 vs 1

    def test_more_long_days(self):
        self.assertIn("more_long_days", self.flags([8, 8, 4, 4, 4, 0, 0]))       # 2 vs 0
        self.assertNotIn("more_long_days", self.flags([8, 4, 4, 4, 4, 0, 0]))    # 1 vs 0

    def test_long_streak(self):
        r12 = an.recovery(days([0] + [4] * 12), END)
        r11 = an.recovery(days([0] + [4] * 11), END)
        self.assertEqual(r12["work_streak"], 12)
        self.assertIn("long_streak", r12["flags"])
        self.assertNotIn("long_streak", r11["flags"])

    def test_ac4b_no_baseline_only_long_streak(self):
        r = an.recovery(days([(4, 5)] * 12), END)
        self.assertTrue(all(v is None for v in r["baseline"].values()))
        self.assertEqual(r["flags"], ["long_streak"])

    def test_ac4c_sparse_week_raises_nothing(self):
        r = an.recovery(with_baseline([None, None, None, 4, 4, 4, 4]), END)
        self.assertEqual(r["week"]["known_days"], 4)
        self.assertEqual(r["flags"], [])


class RecoveryDebt(unittest.TestCase):
    def test_ac5_pure(self):
        # latest week first
        self.assertEqual(an.recovery_debt([[], ["x"], ["x"], ["x"]]), 0)
        self.assertEqual(an.recovery_debt([["x"], ["x"], ["x"], []]), 3)
        self.assertEqual(an.recovery_debt([["x"]] * 20), 8)  # capped

    def test_three_weeks_without_rest(self):
        r = an.recovery(days(NORMAL_WEEK * 8 + [4] * 21), END)
        self.assertEqual(r["debt_weeks"], 3)
        self.assertEqual(len(r["weeks"]), 8)
        self.assertEqual(r["weeks"][3]["flags"], [])


class AnalyzerOutput(unittest.TestCase):
    def test_ac1b_separate_layers_no_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data.json"
            subprocess.run(
                [sys.executable, "-I", str(ROOT / "scripts" / "analyze_sessions.py"),
                 "--projects-dir", str(ROOT / "examples" / "synthetic" / "projects"),
                 "--history", str(Path(tmp) / "none.jsonl"), "--days", "60",
                 "--out", str(Path(tmp) / "r.html"), "--json", str(out)],
                check=True, capture_output=True)
            data = json.loads(out.read_text())
        self.assertIn("recovery", data)
        self.assertIn("checkins", data)
        keys = json.dumps(data["recovery"]) + " ".join(data)
        self.assertNotRegex(keys.lower(), r"score|risk")


if __name__ == "__main__":
    unittest.main()
