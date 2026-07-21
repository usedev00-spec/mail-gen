import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from banscan import (
    _build_search_criteria,
    classify_deactivate_probe,
    extract_recipient_addresses,
    map_banned_to_accounts,
)


class ExtractRecipientAddressesTest(unittest.TestCase):
    def test_collects_addresses_from_recipient_headers_only(self):
        raw = (
            b"From: Amazon <no-reply@amazon.com>\r\n"
            b"Subject: baa-customer-appeal\r\n"
            b"To: alias.one@icloud.com\r\n"
            b"Cc: Someone <alias.two@icloud.com>\r\n"
            b"Delivered-To: dest@gmail.com\r\n"
            b"\r\n"
        )
        addresses = extract_recipient_addresses(raw)
        self.assertEqual(
            addresses,
            {"alias.one@icloud.com", "alias.two@icloud.com", "dest@gmail.com"},
        )
        # The From/Subject sender is never treated as a recipient.
        self.assertNotIn("no-reply@amazon.com", addresses)

    def test_extracts_alias_from_received_for_clause(self):
        raw = (
            b"Received: from mx.icloud.com by mail.gmail.com\r\n"
            b" for <hidden.alias3@icloud.com>; Mon, 21 Jul 2026 10:00:00 +0000\r\n"
            b"Subject: baa-customer-appeal\r\n"
            b"\r\n"
        )
        addresses = extract_recipient_addresses(raw)
        self.assertIn("hidden.alias3@icloud.com", addresses)

    def test_lowercases_and_accepts_str_input(self):
        raw = "To: MixedCase.Alias@iCloud.com\r\n\r\n"
        self.assertEqual(
            extract_recipient_addresses(raw), {"mixedcase.alias@icloud.com"}
        )


class MapBannedToAccountsTest(unittest.TestCase):
    def setUp(self):
        self.aliases_by_account = {
            "iPhone1": {
                "a@icloud.com": {"hme": "a@icloud.com", "isActive": True},
                "b@icloud.com": {"hme": "b@icloud.com", "isActive": False},
            },
            "iPhone2": {
                "c@icloud.com": {"hme": "c@icloud.com", "isActive": True},
            },
        }

    def test_groups_banned_aliases_by_owning_account(self):
        banned, orphans = map_banned_to_accounts(
            {"a@icloud.com", "c@icloud.com"}, self.aliases_by_account
        )
        self.assertEqual(set(banned), {"iPhone1", "iPhone2"})
        self.assertEqual([r["hme"] for r in banned["iPhone1"]], ["a@icloud.com"])
        self.assertEqual([r["hme"] for r in banned["iPhone2"]], ["c@icloud.com"])
        self.assertEqual(orphans, set())

    def test_addresses_without_account_are_orphans(self):
        banned, orphans = map_banned_to_accounts(
            {"a@icloud.com", "unknown@gmail.com"}, self.aliases_by_account
        )
        self.assertEqual(set(banned), {"iPhone1"})
        self.assertEqual(orphans, {"unknown@gmail.com"})

    def test_matching_is_case_insensitive(self):
        banned, orphans = map_banned_to_accounts(
            {"A@iCloud.com"}, self.aliases_by_account
        )
        self.assertEqual(set(banned), {"iPhone1"})
        self.assertEqual(orphans, set())


class BuildSearchCriteriaTest(unittest.TestCase):
    def test_default_searches_full_text_for_token_only(self):
        # Amazon relays ban mails via iCloud (baa-customer-appeal_at_amazon_..._
        # @icloud.com), so a FROM amazon filter wrongly excludes them. The token
        # alone must be the default anchor.
        self.assertEqual(
            _build_search_criteria({}),
            ["TEXT", '"baa-customer-appeal"'],
        )

    def test_stale_from_query_is_ignored(self):
        # A leftover from_query in the config must NOT be applied — Amazon relays
        # the ban mail through iCloud, so a FROM amazon filter drops it entirely.
        self.assertEqual(
            _build_search_criteria({"from_query": "amazon"}),
            ["TEXT", '"baa-customer-appeal"'],
        )

    def test_subject_query_is_an_optional_extra_filter(self):
        self.assertEqual(
            _build_search_criteria({"subject_query": "suspended"}),
            ["TEXT", '"baa-customer-appeal"', "SUBJECT", '"suspended"'],
        )

    def test_empty_config_never_yields_empty_criteria(self):
        self.assertEqual(
            _build_search_criteria({"text_query": "", "subject_query": ""}),
            ["ALL"],
        )


class ClassifyDeactivateProbeTest(unittest.TestCase):
    def test_auth_error_is_unauthorized(self):
        self.assertEqual(
            classify_deactivate_probe(
                {"success": False, "error": {"errorMessage": "global_session error"}}
            ),
            "unauthorized",
        )
        self.assertEqual(
            classify_deactivate_probe({"error": 1, "reason": "Unauthorized"}),
            "unauthorized",
        )

    def test_transport_error_is_ambiguous(self):
        self.assertEqual(
            classify_deactivate_probe({"error": 1, "reason": "Request timed out"}),
            "ambiguous",
        )
        self.assertEqual(
            classify_deactivate_probe(
                {"error": 1, "reason": "Apple rate limit reached (HTTP 429)"}
            ),
            "ambiguous",
        )
        self.assertEqual(classify_deactivate_probe("not a dict"), "ambiguous")

    def test_authenticated_bad_id_is_ok(self):
        # Apple accepted the session but rejected the bogus anonymousId.
        self.assertEqual(
            classify_deactivate_probe(
                {"success": False, "error": {"errorMessage": "Resource not found"}}
            ),
            "ok",
        )
        self.assertEqual(classify_deactivate_probe({"success": True}), "ok")


if __name__ == "__main__":
    unittest.main()
