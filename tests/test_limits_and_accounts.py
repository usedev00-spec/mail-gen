import asyncio
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    MAX_PER_DAY,
    MAX_PER_HOUR,
    AccountConfig,
    count_generated_today,
    load_accounts_config,
    record_generation,
    resolve_effective_limits,
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


if __name__ == "__main__":
    unittest.main()
