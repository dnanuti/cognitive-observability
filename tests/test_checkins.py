"""Phase 6 and 8 acceptance checks: monthly check and personal validation
(SPEC-v3.md sections 4 and 5).

Run: python3 -m unittest discover -s tests
"""
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_sessions as an  # noqa: E402

SPEC = (ROOT / "SPEC-v3.md").read_text(encoding="utf-8")
BATTERY = (ROOT / ".claude" / "skills" / "battery" / "SKILL.md").read_text(encoding="utf-8")
OBSERVE = (ROOT / ".claude" / "skills" / "observe" / "SKILL.md").read_text(encoding="utf-8")

# Verbatim COPSOQ III wording (SPEC-v3.md 4.1-4.2). Must appear exactly in both
# the spec and the battery skill.
VERBATIM = [
    "These questions are about how you have been during the last 4 weeks.",
    "How often have you felt worn out?",
    "How often have you been physically exhausted?",
    "How often have you been emotionally exhausted?",
    "How often have you felt tired?",
    "How often do you not have time to complete all your work tasks?",
    "Can you influence the amount of work assigned to you?",
    "Is your work recognized and appreciated by the management?",
    "How often do you get help and support from your colleagues, if needed?",
    "Is the work distributed fairly?",
    "Is your work meaningful?",
    "Do you feel that your work drains so much of your energy that it has a "
    "negative effect on your private life?",
    "All the time", "A large part of the time", "Part of the time",
    "A small part of the time", "Not at all",
    "Always", "Often", "Sometimes", "Seldom", "Never/hardly ever",
    "To a very large extent", "To a large extent", "Somewhat",
    "To a small extent", "To a very small extent",
    "I do not have colleagues",
]


def ci(ts, inst, value):
    return {"ts": datetime.fromisoformat(ts).astimezone(), "instrument": inst, "value": value}


class Wording(unittest.TestCase):
    def test_ac7_verbatim_in_spec_and_skill(self):
        for s in VERBATIM:
            with self.subTest(s=s):
                self.assertIn(s, SPEC)
                self.assertIn(s, BATTERY)

    def test_ac6_observe_cadence_rules_present(self):
        self.assertIn("bo1", OBSERVE)
        self.assertIn("28 days", OBSERVE)
        self.assertIn("/battery month", BATTERY)


class Parsing(unittest.TestCase):
    def test_parser_reads_new_keys_and_na(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mem = Path(tmp) / "-p" / "memory"
            mem.mkdir(parents=True)
            (mem / "checkins.md").write_text(
                "2026-11-01 17:30 · bo1 · 75 · observe\n"
                "2026-11-01 17:30 · sc1 · na · observe\n"
                "2026-11-01 17:31 · mw1 · skip · observe\n"
                "2026-11-01 17:31 · tlx-mental · 8 · nudge\n", encoding="utf-8")
            got = an.load_checkins(tmp, datetime(2026, 10, 1).astimezone())
        self.assertEqual([(c["instrument"], c["value"]) for c in got],
                         [("bo1", 75), ("tlx-mental", 8)])

    def test_ac9_one_block_one_check(self):
        lines = [ci("2026-11-01T17:30", k, v) for k, v in
                 [("bo1", 75), ("bo2", 50), ("bo3", 75), ("bo4", 100),
                  ("qd2", 75), ("in3", 25), ("re1", 50), ("ju4", 50),
                  ("mw1", 75), ("wf2", 75)]]
        lines.append(ci("2026-11-01T17:30", "samn-perelli", 5))   # not part of it
        checks = an.monthly_checks(lines)
        self.assertEqual(len(checks), 1)
        c = checks[0]
        self.assertEqual(c["exhaustion"], 75.0)
        self.assertEqual(c["answered"], 4)
        self.assertEqual(c["causes"], {"qd2": 75, "in3": 25, "re1": 50, "ju4": 50,
                                       "mw1": 75, "wf2": 75})

    def test_three_of_four_scores_two_does_not(self):
        three = [ci("2026-11-01T17:30", k, 50) for k in ("bo1", "bo2", "bo3")]
        two = [ci("2026-12-01T17:30", k, 50) for k in ("bo1", "bo2")]
        a, b = an.monthly_checks(three + two)
        self.assertEqual(a["exhaustion"], 50.0)
        self.assertIsNone(b["exhaustion"])

    def test_blocks_more_than_an_hour_apart_are_separate(self):
        x = [ci("2026-11-01T17:30", "bo1", 50), ci("2026-11-01T18:31", "bo2", 50)]
        self.assertEqual(len(an.monthly_checks(x)), 2)


class Spearman(unittest.TestCase):
    def test_monotonic(self):
        self.assertEqual(an.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertEqual(an.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_ties_and_constant(self):
        self.assertAlmostEqual(an.spearman([1, 1, 2, 3], [1, 2, 3, 4]), 0.949, places=3)
        self.assertIsNone(an.spearman([2, 2, 2], [1, 2, 3]))


def week_days(end, rest_days, active_per_day=4.0):
    """Seven daily records ending on `end` with the given number of rest days."""
    out = []
    for i in range(7):
        d = end - timedelta(days=6 - i)
        h = 0 if i >= 7 - rest_days else active_per_day
        out.append({"date": d.isoformat(), "no_data": False, "active_h": h, "late_prompts": 0})
    return out


class Validation(unittest.TestCase):
    def build(self, n_weeks):
        """Weekly burnout answers that rise exactly as rest days fall."""
        daily, checkins = [], []
        start = date(2026, 6, 7)  # Sunday
        for w in range(n_weeks):
            end = start + timedelta(days=7 * w)
            rest = [3, 2, 1, 0][w % 4]
            daily += week_days(end, rest)
            report = end + timedelta(days=1)
            checkins.append(ci(f"{report}T17:30", "burnout", 5 - rest - 1))
        return daily, checkins

    def test_ac10a_perfect_pairs(self):
        daily, checkins = self.build(8)
        v = an.validation(daily, checkins)
        self.assertEqual(v["burnout"]["n"], 8)
        self.assertEqual(v["burnout"]["rho"]["rest_days"], -1.0)

    def test_ac10a_seven_pairs_not_enough(self):
        daily, checkins = self.build(7)
        v = an.validation(daily, checkins)
        self.assertEqual(v["burnout"]["n"], 7)
        self.assertIsNone(v["burnout"]["rho"])

    def test_sparse_weeks_are_not_paired(self):
        daily, checkins = self.build(8)
        daily = [d for d in daily if d["date"] > "2026-06-04"]  # first week: 3 known days
        self.assertEqual(an.validation(daily, checkins)["burnout"]["n"], 7)


if __name__ == "__main__":
    unittest.main()
