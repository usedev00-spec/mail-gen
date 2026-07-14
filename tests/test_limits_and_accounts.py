import asyncio
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    DAY_SECONDS,
    MAX_PER_DAY,
    MAX_PER_HOUR,
    AccountConfig,
    build_generation_schedule,
    count_generated_today,
    filter_accounts,
    load_accounts_config,
    record_generation,
    resolve_effective_limits,
    suggested_duration_hours,
)


class DefaultLimitsTest(unittest.TestCase):
    def test_default_max_per_hour_is_five(self):
        self.assertEqual(MAX_PER_HOUR, 5)

    def test_default_max_per_day_is_fifteen(self):
        self.assertEqual(MAX_PER_DAY, 15)


class ResolveEffectiveLimitsTest(unittest.TestCase):
    def test_daily_limit_is_clamped_without_override(self):
        daily, hourly, warnings = resolve_effective_limits(100, None, False)
        self.assertEqual(daily, MAX_PER_DAY)
        self.assertEqual(hourly, MAX_PER_HOUR)
        self.assertTrue(warnings)

    def test_max_per_hour_is_clamped_without_override(self):
        daily, hourly, warnings = resolve_effective_limits(MAX_PER_DAY, 50, False)
        self.assertEqual(hourly, MAX_PER_HOUR)
        self.assertTrue(warnings)

    def test_values_within_defaults_pass_through_without_warning(self):
        daily, hourly, warnings = resolve_effective_limits(10, 3, False)
        self.assertEqual(daily, 10)
        self.assertEqual(hourly, 3)
        self.assertEqual(warnings, [])

    def test_override_allows_exceeding_defaults(self):
        daily, hourly, warnings = resolve_effective_limits(100, 50, True)
        self.assertEqual(daily, 100)
        self.assertEqual(hourly, 50)
        self.assertEqual(warnings, [])


class OverridePaceTest(unittest.TestCase):
    """Override mode must run at exactly max_per_hour, not the slower
    comfortable pace (e.g. 25 aliases at 5/hour -> 5 h, not 7 h)."""

    def test_suggested_duration_is_count_over_max_per_hour(self):
        self.assertEqual(
            suggested_duration_hours(25, 25, 5, 0, override_limits=True), 5.0
        )

    def test_suggested_duration_without_override_keeps_comfortable_pace(self):
        # 25 / COMFORTABLE_PER_HOUR (4) = 6.25 -> ceil -> 7 h.
        self.assertEqual(suggested_duration_hours(25, 25, 5, 0), 7.0)

    def test_override_still_stretches_when_daily_limit_binds(self):
        # 50 aliases at 25/day can't fit in 10 h: the day window must bind.
        suggested = suggested_duration_hours(50, 25, 5, 0, override_limits=True)
        self.assertGreater(suggested, 24.0)

    def test_25_aliases_in_5_hours_is_not_extended(self):
        import random

        for seed in range(25):
            random.seed(seed)
            schedule = build_generation_schedule(25, 5 * 3600, 25, 5, 0)
            self.assertEqual(len(schedule), 25)
            # The run must finish within the requested 5 h window (the +30 s
            # per-window safety buffer allows at most a few minutes of slack).
            self.assertLessEqual(schedule[-1], 5 * 3600 + 5 * 60)
            # And still never exceed 5 per rolling hour.
            for i in range(5, 25):
                self.assertGreaterEqual(schedule[i] - schedule[i - 5], 3600)


class FilterAccountsTest(unittest.TestCase):
    def setUp(self):
        self.accounts = [
            AccountConfig(name="main", cookie_file="a.txt"),
            AccountConfig(name="iCloud2", cookie_file="b.txt"),
            AccountConfig(name="iCloud3", cookie_file="c.txt"),
        ]

    def test_returns_only_the_named_accounts_in_given_order(self):
        selected = filter_accounts(self.accounts, ["iCloud3", "main"])
        self.assertEqual([a.name for a in selected], ["iCloud3", "main"])

    def test_unknown_name_raises_with_available_accounts_listed(self):
        with self.assertRaises(ValueError) as ctx:
            filter_accounts(self.accounts, ["main", "nope"])
        message = str(ctx.exception)
        self.assertIn("nope", message)
        self.assertIn("iCloud2", message)

    def test_empty_names_returns_empty_list(self):
        self.assertEqual(filter_accounts(self.accounts, []), [])


class LoadAccountsConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

    def _write(self, name, content):
        path = os.path.join(self.tmp_dir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_simplified_schema_name_and_cookie_file_only(self):
        self._write("cookie_a.txt", "session=abc")
        self._write("cookie_b.txt", "session=def")
        accounts_path = self._write(
            "accounts.json",
            json.dumps(
                [
                    {"name": "main", "cookie_file": "cookie_a.txt"},
                    {"name": "secondary", "cookie_file": "cookie_b.txt"},
                ]
            ),
        )

        accounts = load_accounts_config(accounts_path)

        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0], AccountConfig(
            name="main",
            cookie_file=os.path.join(self.tmp_dir.name, "cookie_a.txt"),
        ))
        self.assertEqual(accounts[1].name, "secondary")

    def test_missing_cookie_file_field_raises_clear_error(self):
        accounts_path = self._write(
            "accounts.json", json.dumps([{"name": "main"}])
        )
        with self.assertRaises(ValueError) as ctx:
            load_accounts_config(accounts_path)
        self.assertIn("cookie_file", str(ctx.exception))

    def test_missing_name_field_raises_clear_error(self):
        self._write("cookie_a.txt", "session=abc")
        accounts_path = self._write(
            "accounts.json", json.dumps([{"cookie_file": "cookie_a.txt"}])
        )
        with self.assertRaises(ValueError) as ctx:
            load_accounts_config(accounts_path)
        self.assertIn("name", str(ctx.exception))

    def test_nonexistent_cookie_file_raises_clear_error(self):
        accounts_path = self._write(
            "accounts.json",
            json.dumps([{"name": "main", "cookie_file": "does_not_exist.txt"}]),
        )
        with self.assertRaises(ValueError) as ctx:
            load_accounts_config(accounts_path)
        self.assertIn("does not exist", str(ctx.exception))

    def test_invalid_json_raises_clear_error(self):
        accounts_path = self._write("accounts.json", "{not valid json")
        with self.assertRaises(ValueError) as ctx:
            load_accounts_config(accounts_path)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_missing_accounts_file_raises_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            load_accounts_config(os.path.join(self.tmp_dir.name, "missing.json"))
        self.assertIn("does not exist", str(ctx.exception))

    def test_legacy_per_account_fields_are_ignored_not_crashing(self):
        self._write("cookie_a.txt", "session=abc")
        accounts_path = self._write(
            "accounts.json",
            json.dumps(
                [
                    {
                        "name": "main",
                        "cookie_file": "cookie_a.txt",
                        "count": 15,
                        "daily_limit": 25,
                        "duration_hours": 4,
                    }
                ]
            ),
        )

        accounts = load_accounts_config(accounts_path)

        self.assertEqual(len(accounts), 1)
        self.assertFalse(hasattr(accounts[0], "count"))
        self.assertFalse(hasattr(accounts[0], "daily_limit"))
        self.assertFalse(hasattr(accounts[0], "duration_hours"))


class DailyGenerationCounterTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.log_file = os.path.join(self.tmp_dir.name, "generation_log.jsonl")

    def test_counts_only_todays_entries_for_the_given_account(self):
        now = datetime.datetime.now()
        yesterday = now - datetime.timedelta(days=1)

        asyncio.run(record_generation("main", "a@icloud.com", self.log_file))
        asyncio.run(record_generation("main", "b@icloud.com", self.log_file))
        asyncio.run(record_generation("secondary", "c@icloud.com", self.log_file))

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "account": "main",
                        "email": "old@icloud.com",
                        "timestamp": yesterday.isoformat(timespec="seconds"),
                    }
                )
                + "\n"
            )

        self.assertEqual(
            count_generated_today("main", now, self.log_file), 2
        )
        self.assertEqual(
            count_generated_today("secondary", now, self.log_file), 1
        )
        self.assertEqual(
            count_generated_today("nonexistent", now, self.log_file), 0
        )

    def test_missing_log_file_counts_as_zero(self):
        self.assertEqual(
            count_generated_today("main", log_file=self.log_file), 0
        )


class LargeCountScheduleTest(unittest.TestCase):
    """Regression test: a big count (e.g. 200) must never be truncated down
    to the daily limit — it should just take more days at the safe pace."""

    def test_large_count_is_not_truncated(self):
        count = 200
        hours = suggested_duration_hours(count, MAX_PER_DAY, MAX_PER_HOUR)
        schedule = build_generation_schedule(count, hours * 3600, MAX_PER_DAY, MAX_PER_HOUR)
        self.assertEqual(len(schedule), count)

    def test_large_count_spans_multiple_days(self):
        count = 200
        hours = suggested_duration_hours(count, MAX_PER_DAY, MAX_PER_HOUR)
        schedule = build_generation_schedule(count, hours * 3600, MAX_PER_DAY, MAX_PER_HOUR)
        self.assertGreater(schedule[-1], DAY_SECONDS)

    def test_already_generated_today_delays_schedule_start(self):
        schedule_fresh = build_generation_schedule(5, 0.0, MAX_PER_DAY, MAX_PER_HOUR)
        schedule_full_day = build_generation_schedule(
            5, 0.0, MAX_PER_DAY, MAX_PER_HOUR, already_generated_today=MAX_PER_DAY
        )
        # With today's quota already used up, the very first new alias must
        # wait roughly a full day, unlike a fresh schedule starting at ~0.
        self.assertGreater(schedule_full_day[0], schedule_fresh[0])
        self.assertGreaterEqual(schedule_full_day[0], DAY_SECONDS)


if __name__ == "__main__":
    unittest.main()
