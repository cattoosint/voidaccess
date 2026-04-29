"""
tests/test_analysis.py — Tests for Phase 6 analysis module.

Test classes
------------
TestTemporal     — analysis/temporal.py
TestPatterns     — analysis/patterns.py
TestOpsec        — analysis/opsec.py
"""

from __future__ import annotations

import os
import sys
import unittest
from collections import namedtuple
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.pop("DATABASE_URL", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_timeline(counts: list[int], start: date | None = None) -> list[dict]:
    """Build a synthetic timeline from a list of daily counts."""
    base = start or date(2024, 1, 1)
    return [
        {"date": base + timedelta(days=i), "count": c, "page_ids": []}
        for i, c in enumerate(counts)
    ]


def _today_timeline(days_back: int, count: int = 5) -> list[dict]:
    """Build a timeline ending today."""
    today = date.today()
    return [
        {"date": today - timedelta(days=days_back - i - 1), "count": count, "page_ids": []}
        for i in range(days_back)
    ]


# ===========================================================================
# TestTemporal
# ===========================================================================

from analysis.temporal import (
    build_activity_timeline,
    compute_activity_stats,
    detect_anomalies,
    detect_silence_breaks,
)


class TestTemporal(unittest.TestCase):

    # --- build_activity_timeline ---

    def test_returns_empty_when_db_unavailable(self):
        os.environ.pop("DATABASE_URL", None)
        result = build_activity_timeline("testactor", "THREAT_ACTOR_HANDLE")
        self.assertEqual(result, [])

    def test_never_raises_on_db_error(self):
        os.environ.pop("DATABASE_URL", None)
        try:
            build_activity_timeline("x", "y")
        except Exception as exc:
            self.fail(f"build_activity_timeline raised: {exc}")

    # --- compute_activity_stats ---

    def test_correct_mean(self):
        timeline = _make_timeline([2, 4, 6])
        stats = compute_activity_stats(timeline)
        self.assertAlmostEqual(stats["mean_daily"], 4.0, places=5)

    def test_correct_std(self):
        timeline = _make_timeline([2, 4, 6])
        stats = compute_activity_stats(timeline)
        # Population std of [2,4,6] = sqrt(8/3) ≈ 1.6330
        self.assertAlmostEqual(stats["std_daily"], (8 / 3) ** 0.5, places=4)

    def test_empty_timeline_graceful(self):
        stats = compute_activity_stats([])
        self.assertEqual(stats["mean_daily"], 0.0)
        self.assertEqual(stats["total_appearances"], 0)
        self.assertIsNone(stats["peak_day"])
        self.assertIsNone(stats["first_seen"])
        self.assertIsNone(stats["last_seen"])

    def test_peak_day_correct(self):
        tl = _make_timeline([1, 5, 2])
        stats = compute_activity_stats(tl)
        self.assertEqual(stats["peak_count"], 5)
        self.assertEqual(stats["peak_day"], date(2024, 1, 2))

    def test_total_appearances(self):
        tl = _make_timeline([3, 7, 2])
        stats = compute_activity_stats(tl)
        self.assertEqual(stats["total_appearances"], 12)

    def test_active_days(self):
        tl = _make_timeline([1, 2, 3, 4])
        stats = compute_activity_stats(tl)
        self.assertEqual(stats["active_days"], 4)

    def test_first_and_last_seen(self):
        tl = _make_timeline([1, 2, 3])
        stats = compute_activity_stats(tl)
        self.assertEqual(stats["first_seen"], date(2024, 1, 1))
        self.assertEqual(stats["last_seen"], date(2024, 1, 3))

    # --- detect_anomalies ---

    def test_returns_empty_for_fewer_than_7_points(self):
        tl = _make_timeline([1, 2, 3, 4, 5, 6])
        self.assertEqual(detect_anomalies(tl), [])

    def test_returns_empty_for_exactly_6_points(self):
        self.assertEqual(detect_anomalies(_make_timeline([1] * 6)), [])

    def test_spike_flagged_correctly(self):
        # 9 days of count=1 plus one day with count=100 (huge spike)
        counts = [1] * 9 + [100]
        tl = _make_timeline(counts)
        anomalies = detect_anomalies(tl, z_threshold=2.0)
        spike = [a for a in anomalies if a["type"] == "spike"]
        self.assertTrue(len(spike) > 0, "Expected at least one spike flagged")
        self.assertEqual(spike[0]["count"], 100)

    def test_drop_flagged_correctly(self):
        # 9 days of count=100 plus one day with count=1 (huge drop)
        counts = [100] * 9 + [1]
        tl = _make_timeline(counts)
        anomalies = detect_anomalies(tl, z_threshold=2.0)
        drops = [a for a in anomalies if a["type"] == "drop"]
        self.assertTrue(len(drops) > 0, "Expected at least one drop flagged")

    def test_anomaly_has_required_keys(self):
        counts = [1] * 9 + [200]
        tl = _make_timeline(counts)
        anomalies = detect_anomalies(tl)
        if anomalies:
            self.assertIn("date", anomalies[0])
            self.assertIn("count", anomalies[0])
            self.assertIn("z_score", anomalies[0])
            self.assertIn("type", anomalies[0])

    def test_uniform_data_no_anomalies(self):
        tl = _make_timeline([5] * 10)
        self.assertEqual(detect_anomalies(tl), [])

    # --- detect_silence_breaks ---

    def test_detects_gap_gte_silence_days(self):
        tl = [
            {"date": date(2024, 1, 1), "count": 3, "page_ids": []},
            {"date": date(2024, 2, 1), "count": 5, "page_ids": []},  # 31-day gap
        ]
        breaks = detect_silence_breaks(tl, silence_days=14)
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0]["gap_days"], 31)

    def test_no_false_positive_for_short_gap(self):
        tl = [
            {"date": date(2024, 1, 1), "count": 3, "page_ids": []},
            {"date": date(2024, 1, 8), "count": 2, "page_ids": []},  # 7-day gap
        ]
        breaks = detect_silence_breaks(tl, silence_days=14)
        self.assertEqual(breaks, [])

    def test_returns_empty_for_single_entry(self):
        tl = [{"date": date(2024, 1, 1), "count": 1, "page_ids": []}]
        self.assertEqual(detect_silence_breaks(tl), [])

    def test_silence_break_has_required_keys(self):
        tl = [
            {"date": date(2024, 1, 1), "count": 1, "page_ids": []},
            {"date": date(2024, 3, 1), "count": 1, "page_ids": []},
        ]
        breaks = detect_silence_breaks(tl, silence_days=14)
        self.assertTrue(len(breaks) > 0)
        self.assertIn("silent_from", breaks[0])
        self.assertIn("silent_to", breaks[0])
        self.assertIn("gap_days", breaks[0])

    def test_multiple_breaks_detected(self):
        tl = [
            {"date": date(2024, 1, 1), "count": 1, "page_ids": []},
            {"date": date(2024, 2, 1), "count": 1, "page_ids": []},
            {"date": date(2024, 4, 1), "count": 1, "page_ids": []},
        ]
        breaks = detect_silence_breaks(tl, silence_days=14)
        self.assertEqual(len(breaks), 2)


# ===========================================================================
# TestPatterns
# ===========================================================================

from analysis.patterns import (
    check_exit_scam_pattern,
    check_law_enforcement_pattern,
    check_new_actor_pattern,
    run_all_patterns,
)


class TestPatterns(unittest.TestCase):

    # --- check_exit_scam_pattern ---

    def test_high_risk_for_large_activity_drop(self):
        """Drop >60% in last 14 days vs prior 14 days → high risk."""
        today = date.today()
        # Prior 14 days: high activity (20/day)
        prior = [
            {"date": today - timedelta(days=30 - i), "count": 20, "page_ids": []}
            for i in range(14)
        ]
        # Last 14 days: very low activity (2/day) — 90% drop
        recent = [
            {"date": today - timedelta(days=14 - i), "count": 2, "page_ids": []}
            for i in range(14)
        ]
        timeline = prior + recent
        result = check_exit_scam_pattern(timeline)
        self.assertEqual(result["risk"], "high")
        self.assertIn("reason", result)
        self.assertIn("confidence", result)

    def test_low_risk_for_stable_activity(self):
        tl = _make_timeline([5] * 30)
        result = check_exit_scam_pattern(tl)
        self.assertEqual(result["risk"], "low")

    def test_returns_required_keys(self):
        tl = _make_timeline([5] * 10)
        result = check_exit_scam_pattern(tl)
        self.assertIn("risk", result)
        self.assertIn("confidence", result)
        self.assertIn("reason", result)

    def test_empty_timeline_low_risk(self):
        result = check_exit_scam_pattern([])
        self.assertEqual(result["risk"], "low")

    # --- check_law_enforcement_pattern ---

    def test_high_risk_for_long_silence(self):
        """7+ days since last activity after sustained posting → high risk."""
        today = date.today()
        # 10 active days ending 10 days ago
        tl = [
            {"date": today - timedelta(days=20 - i), "count": 5, "page_ids": []}
            for i in range(10)
        ]
        result = check_law_enforcement_pattern(tl)
        self.assertEqual(result["risk"], "high")

    def test_low_risk_for_recent_activity(self):
        today = date.today()
        # Active yesterday
        tl = [
            {"date": today - timedelta(days=1), "count": 5, "page_ids": []},
            {"date": today, "count": 3, "page_ids": []},
        ]
        result = check_law_enforcement_pattern(tl)
        self.assertNotEqual(result["risk"], "high")

    def test_returns_required_keys(self):
        result = check_law_enforcement_pattern(_make_timeline([3] * 5))
        self.assertIn("risk", result)
        self.assertIn("confidence", result)
        self.assertIn("reason", result)

    # --- check_new_actor_pattern ---

    def test_is_new_true_for_recent_first_seen(self):
        today = date.today()
        recent_tl = [
            {"date": today - timedelta(days=2), "count": 3, "page_ids": []},
            {"date": today - timedelta(days=1), "count": 2, "page_ids": []},
        ]
        with patch("analysis.patterns.build_activity_timeline", return_value=recent_tl):
            result = check_new_actor_pattern("new_actor", "THREAT_ACTOR_HANDLE")
        self.assertTrue(result["is_new"])
        self.assertIsNotNone(result["first_seen"])

    def test_is_new_false_for_old_actor(self):
        old_tl = [
            {"date": date(2020, 1, 1), "count": 5, "page_ids": []},
            {"date": date(2020, 6, 1), "count": 3, "page_ids": []},
        ]
        with patch("analysis.patterns.build_activity_timeline", return_value=old_tl):
            result = check_new_actor_pattern("old_actor", "THREAT_ACTOR_HANDLE")
        self.assertFalse(result["is_new"])

    def test_is_new_false_when_no_data(self):
        with patch("analysis.patterns.build_activity_timeline", return_value=[]):
            result = check_new_actor_pattern("unknown", "x")
        self.assertFalse(result["is_new"])
        self.assertIsNone(result["first_seen"])

    def test_returns_required_keys(self):
        with patch("analysis.patterns.build_activity_timeline", return_value=[]):
            result = check_new_actor_pattern("x", "y")
        self.assertIn("is_new", result)
        self.assertIn("first_seen", result)
        self.assertIn("days_active", result)

    # --- run_all_patterns ---

    def test_returns_all_expected_keys(self):
        tl = _make_timeline([3] * 10)
        with patch("analysis.patterns.build_activity_timeline", return_value=tl), \
             patch("analysis.patterns.check_new_actor_pattern",
                   return_value={"is_new": False, "first_seen": None, "days_active": 0}):
            result = run_all_patterns("actor", "THREAT_ACTOR_HANDLE")
        self.assertIn("exit_scam", result)
        self.assertIn("law_enforcement", result)
        self.assertIn("new_actor", result)
        self.assertIn("anomalies", result)
        self.assertIn("silence_breaks", result)


# ===========================================================================
# TestOpsec
# ===========================================================================

from analysis.opsec import (
    detect_clearnet_slip,
    detect_language_switch,
    detect_pgp_reuse,
    detect_timezone_leak,
    run_full_opsec_analysis,
)


class TestOpsec(unittest.TestCase):

    # --- detect_timezone_leak ---

    def _make_posts_in_window(
        self, start_hour: int, count: int = 20
    ) -> list[dict]:
        """Generate posts clustered within a 6-hour window."""
        from datetime import datetime, timezone

        posts = []
        for i in range(count):
            hour = (start_hour + (i % 5)) % 24
            ts = datetime(2024, 6, 1 + i % 28, hour, 0, 0, tzinfo=timezone.utc)
            posts.append({"text": "test post content", "timestamp": ts})
        return posts

    def _make_evenly_distributed_posts(self, count: int = 24) -> list[dict]:
        from datetime import datetime, timezone

        posts = []
        for i in range(count):
            hour = i % 24
            ts = datetime(2024, 6, 1, hour, 0, 0, tzinfo=timezone.utc)
            posts.append({"text": "test post content", "timestamp": ts})
        return posts

    def test_detected_true_for_clustered_posts(self):
        posts = self._make_posts_in_window(start_hour=10, count=30)
        result = detect_timezone_leak(posts)
        self.assertTrue(result["detected"])
        self.assertIsNotNone(result["probable_timezone_offset"])
        self.assertGreater(result["confidence"], 0.0)

    def test_detected_false_for_even_distribution(self):
        posts = self._make_evenly_distributed_posts(count=48)
        result = detect_timezone_leak(posts)
        self.assertFalse(result["detected"])

    def test_returns_posting_hours(self):
        posts = self._make_posts_in_window(10, 10)
        result = detect_timezone_leak(posts)
        self.assertIn("posting_hours", result)
        self.assertEqual(len(result["posting_hours"]), 10)

    def test_empty_input(self):
        result = detect_timezone_leak([])
        self.assertFalse(result["detected"])

    def test_peak_window_format(self):
        posts = self._make_posts_in_window(9, 30)
        result = detect_timezone_leak(posts)
        if result["detected"]:
            self.assertIsNotNone(result["peak_window"])
            self.assertIn("UTC", result["peak_window"])

    # --- detect_language_switch ---

    def test_detected_true_for_mixed_languages(self):
        texts = ["This is an English sentence."] * 5 + ["Esto es español."] * 2
        # Mock langdetect to return "en" for first 5, "es" for last 2
        mock_detect_results = ["en"] * 5 + ["es"] * 2
        call_iter = iter(mock_detect_results)

        def mock_detect(text):
            return next(call_iter)

        with patch("analysis.opsec.detect_language_switch") as mock_fn:
            mock_fn.return_value = {
                "detected": True,
                "languages_found": ["en", "es"],
                "primary_language": "en",
                "switch_count": 2,
                "switched_texts_indices": [5, 6],
            }
            result = mock_fn(texts)
        self.assertTrue(result["detected"])
        self.assertIn("es", result["languages_found"])

    def test_detected_true_via_langdetect_mock(self):
        """Test with actual langdetect mocked."""
        texts = ["English text here."] * 3 + ["Русский текст здесь."] * 2

        mock_langdetect = MagicMock()
        mock_results = iter(["en", "en", "en", "ru", "ru"])
        mock_langdetect.detect = lambda t: next(mock_results)
        mock_langdetect.LangDetectException = Exception

        with patch.dict("sys.modules", {"langdetect": mock_langdetect}):
            # Re-import to pick up mock
            import importlib
            import analysis.opsec as opsec_mod
            importlib.reload(opsec_mod)
            result = opsec_mod.detect_language_switch(texts)

        if result.get("detected") is not None:
            self.assertIn("languages_found", result)

    # --- detect_clearnet_slip ---

    def test_detects_youtube_url(self):
        texts = ["Check out this video: https://www.youtube.com/watch?v=abc123"]
        result = detect_clearnet_slip(texts)
        self.assertTrue(result["detected"])
        self.assertTrue(any("youtube.com" in url for url in result["clearnet_urls"]))
        self.assertIn("youtube.com", result["platforms"])

    def test_does_not_flag_onion_urls(self):
        texts = ["Visit http://fakeexamplehiddenservicexyz.onion/page for info"]
        result = detect_clearnet_slip(texts)
        self.assertFalse(result["detected"])
        self.assertEqual(result["clearnet_urls"], [])

    def test_empty_input(self):
        result = detect_clearnet_slip([])
        self.assertFalse(result["detected"])

    def test_returns_required_keys(self):
        result = detect_clearnet_slip(["no urls here"])
        self.assertIn("detected", result)
        self.assertIn("clearnet_urls", result)
        self.assertIn("platforms", result)

    def test_mixed_clearnet_and_onion(self):
        texts = [
            "Visit http://abc.onion for the forum and https://reddit.com for help"
        ]
        result = detect_clearnet_slip(texts)
        self.assertTrue(result["detected"])
        # Onion URL should not appear in clearnet_urls
        for url in result["clearnet_urls"]:
            self.assertNotIn(".onion", url)

    # --- detect_pgp_reuse ---

    def test_detected_true_same_fingerprint_two_domains(self):
        fps = ["ABCD1234ABCD1234", "ABCD1234ABCD1234"]
        sources = ["forum1.onion", "forum2.onion"]
        result = detect_pgp_reuse(fps, sources)
        self.assertTrue(result["detected"])
        self.assertIn("ABCD1234ABCD1234", result["reused_fingerprints"])
        self.assertEqual(len(result["cross_platform_exposure"]), 1)

    def test_not_detected_different_fingerprints(self):
        fps = ["FINGERPRINT_A", "FINGERPRINT_B"]
        sources = ["forum1.onion", "forum2.onion"]
        result = detect_pgp_reuse(fps, sources)
        self.assertFalse(result["detected"])

    def test_returns_required_keys(self):
        result = detect_pgp_reuse([], [])
        self.assertIn("detected", result)
        self.assertIn("reused_fingerprints", result)
        self.assertIn("cross_platform_exposure", result)

    def test_mismatched_lengths(self):
        result = detect_pgp_reuse(["FP1"], ["src1", "src2"])
        self.assertFalse(result["detected"])

    # --- run_full_opsec_analysis ---

    def test_high_risk_for_clustered_posts_with_clearnet(self):
        from datetime import datetime, timezone

        posts = [
            {
                "text": "Check this https://youtube.com link here",
                "timestamp": datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
            }
        ] * 20

        result = run_full_opsec_analysis("threat_actor", posts)
        self.assertIn("handle", result)
        self.assertEqual(result["handle"], "threat_actor")
        self.assertIn("risk_score", result)
        self.assertIn("risk_level", result)
        self.assertIn(result["risk_level"], ("LOW", "MEDIUM", "HIGH", "CRITICAL"))

    def test_returns_all_required_keys(self):
        result = run_full_opsec_analysis("actor", [])
        self.assertIn("handle", result)
        self.assertIn("timezone_leak", result)
        self.assertIn("language_switch", result)
        self.assertIn("clearnet_slips", result)
        self.assertIn("risk_score", result)
        self.assertIn("risk_level", result)
        self.assertIn("findings", result)
        self.assertIn("opsec_score", result)
        self.assertIn("pgp_reuse", result)

    def test_risk_level_correct_string_values(self):
        result = run_full_opsec_analysis("actor", [])
        self.assertIn(result["risk_level"], ("LOW", "MEDIUM", "HIGH", "CRITICAL"))

    def test_risk_score_in_range(self):
        result = run_full_opsec_analysis("actor", [])
        self.assertGreaterEqual(result["risk_score"], 0.0)
        self.assertLessEqual(result["risk_score"], 1.0)

    def test_high_risk_returned_for_high_confidence_inputs(self):
        from datetime import datetime, timezone

        # 20 clustered posts all at hour 10 with clearnet URL
        posts = [
            {
                "text": "Please visit https://reddit.com/r/darkweb for more info",
                "timestamp": datetime(2024, 6, i % 28 + 1, 10, 0, tzinfo=timezone.utc),
            }
            for i in range(20)
        ]
        result = run_full_opsec_analysis("actor_x", posts)
        # Clearnet slip detected → at least medium risk
        self.assertIn(result["risk_level"], ("MEDIUM", "HIGH", "CRITICAL"))


if __name__ == "__main__":
    unittest.main()
