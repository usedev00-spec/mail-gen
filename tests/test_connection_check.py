import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    CONNECTION_STATUS_DISPLAY,
    RichHideMyEmail,
    _classify_connection_error,
    build_connection_table,
    AccountConfig,
)


class _DummyConsole:
    def log(self, *args, **kwargs):
        pass


def _hme(**kwargs):
    """A RichHideMyEmail with cookie loading stubbed out (no filesystem)."""
    with mock.patch.object(RichHideMyEmail, "_load_cookies", lambda self: None):
        hme = RichHideMyEmail(cookie_file="x.txt", console=_DummyConsole())
    for key, value in kwargs.items():
        setattr(hme, key, value)
    return hme


class ClassifyConnectionErrorTest(unittest.TestCase):
    def test_global_session_is_expired(self):
        response = {"error": {"errorMessage": "GLOBAL_SESSION expired"}}
        self.assertEqual(_classify_connection_error(response), "expired")

    def test_unauthorized_is_expired(self):
        self.assertEqual(
            _classify_connection_error({"reason": "Unauthorized"}), "expired"
        )

    def test_rate_limit_is_rate_limited(self):
        response = {"error": 1, "reason": "Apple rate limit reached (HTTP 429)"}
        self.assertEqual(_classify_connection_error(response), "rate_limited")

    def test_network_error_is_error(self):
        response = {"error": 1, "reason": "Network error: boom"}
        self.assertEqual(_classify_connection_error(response), "error")

    def test_non_dict_is_error(self):
        self.assertEqual(_classify_connection_error(None), "error")


class CheckConnectionTest(unittest.TestCase):
    def test_no_cookie_reports_no_cookie(self):
        hme = _hme(cookies="", cookie_error="missing cookie file")
        result = asyncio.run(hme.check_connection())
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "no_cookie")
        self.assertEqual(result["detail"], "missing cookie file")

    def test_successful_list_reports_ok_with_counts(self):
        hme = _hme(cookies="session=abc", mail_host_resolved=True)
        payload = {
            "success": True,
            "result": {
                "hmeEmails": [
                    {"isActive": True},
                    {"isActive": False},
                    {"isActive": True},
                ]
            },
        }
        with mock.patch.object(
            hme, "list_email", mock.AsyncMock(return_value=payload)
        ):
            result = asyncio.run(hme.check_connection())
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["active"], 2)
        self.assertTrue(result["mail_host_resolved"])

    def test_expired_session_reports_expired(self):
        hme = _hme(cookies="session=stale")
        payload = {"error": {"errorMessage": "global_session_error"}}
        with mock.patch.object(
            hme, "list_email", mock.AsyncMock(return_value=payload)
        ):
            result = asyncio.run(hme.check_connection())
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "expired")

    def test_empty_response_reports_error(self):
        hme = _hme(cookies="session=abc")
        with mock.patch.object(
            hme, "list_email", mock.AsyncMock(return_value=None)
        ):
            result = asyncio.run(hme.check_connection())
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["detail"], "Empty response from Apple")


class BuildConnectionTableTest(unittest.TestCase):
    def test_every_status_has_a_display_entry(self):
        # Table rendering looks up each status; a missing key would crash it.
        for status in ("ok", "no_cookie", "expired", "rate_limited", "error"):
            self.assertIn(status, CONNECTION_STATUS_DISPLAY)

    def test_table_builds_for_mixed_results(self):
        results = [
            (
                AccountConfig(name="a", cookie_file="a.txt"),
                {"ok": True, "status": "ok", "detail": "5 alias(es), 4 active",
                 "total": 5, "active": 4, "mail_host_resolved": True},
            ),
            (
                AccountConfig(name="b", cookie_file="b.txt"),
                {"ok": False, "status": "expired", "detail": "stale",
                 "total": 0, "active": 0, "mail_host_resolved": False},
            ),
        ]
        table = build_connection_table(results)
        self.assertEqual(table.row_count, 2)


if __name__ == "__main__":
    unittest.main()
