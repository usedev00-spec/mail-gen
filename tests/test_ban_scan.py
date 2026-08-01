import asyncio
import csv
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from banscan import (
    BAN_SIGNAL_KEYS,
    _build_search_criteria,
    _process_records,
    build_flagged_rows,
    classify_deactivate_probe,
    export_flagged_aliases,
    extract_recipient_addresses,
    load_gmail_config,
    map_banned_to_accounts,
    resolve_ban_signals,
    resolve_export_format,
    scan_ban_recipients,
)


class _DummyConsole:
    def log(self, *args, **kwargs):
        pass


class _FakeHME:
    def __init__(self, deactivate_ok=True, delete_ok=True):
        self.calls = []
        self._deactivate_ok = deactivate_ok
        self._delete_ok = delete_ok

    async def deactivate_email(self, anonymous_id):
        self.calls.append(("deactivate", anonymous_id))
        return {"success": self._deactivate_ok, "error": {"errorMessage": "no"}}

    async def delete_email(self, anonymous_id):
        self.calls.append(("delete", anonymous_id))
        return {"success": self._delete_ok, "error": {"errorMessage": "no"}}

    def _format_error_message(self, response):
        return "err"


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


class BuildFlaggedRowsTest(unittest.TestCase):
    def setUp(self):
        self.banned_by_account = {
            "iPhone1": [
                {"hme": "a@icloud.com", "label": "Amazon A", "isActive": True},
                {"hme": "b@icloud.com", "label": "Amazon B", "isActive": False},
            ],
            "iPhone2": [
                {"hme": "c@icloud.com", "label": "Amazon C", "isActive": True},
            ],
        }

    def test_deactivate_mode_keeps_only_active_aliases(self):
        rows = build_flagged_rows(self.banned_by_account, False)
        self.assertEqual(
            [(r["account"], r["alias"]) for r in rows],
            [("iPhone1", "a@icloud.com"), ("iPhone2", "c@icloud.com")],
        )

    def test_delete_mode_keeps_every_banned_alias(self):
        rows = build_flagged_rows(self.banned_by_account, True)
        self.assertEqual(
            {r["alias"] for r in rows},
            {"a@icloud.com", "b@icloud.com", "c@icloud.com"},
        )

    def test_row_carries_label_and_state(self):
        rows = build_flagged_rows(self.banned_by_account, True)
        inactive = next(r for r in rows if r["alias"] == "b@icloud.com")
        self.assertEqual(inactive["label"], "Amazon B")
        self.assertFalse(inactive["active"])


class ResolveExportFormatTest(unittest.TestCase):
    def test_explicit_choice_wins(self):
        self.assertEqual(resolve_export_format("out.csv", "txt"), "txt")

    def test_inferred_from_extension(self):
        self.assertEqual(resolve_export_format("out.txt"), "txt")
        self.assertEqual(resolve_export_format("OUT.TXT"), "txt")
        self.assertEqual(resolve_export_format("out.csv"), "csv")

    def test_defaults_to_csv_without_txt_extension(self):
        self.assertEqual(resolve_export_format("flagged"), "csv")


class ExportFlaggedAliasesTest(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"account": "iPhone1", "label": "Amazon A", "alias": "a@icloud.com", "active": True},
            {"account": "iPhone2", "label": "Amazon C", "alias": "c@icloud.com", "active": False},
        ]

    def _write(self, fmt, rows=None):
        fd, path = tempfile.mkstemp(suffix=f".{fmt}")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        export_flagged_aliases(self.rows if rows is None else rows, path, fmt)
        return path

    def test_txt_is_one_alias_per_line(self):
        with open(self._write("txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "a@icloud.com\nc@icloud.com\n")

    def test_csv_has_header_and_localized_state(self):
        with open(self._write("csv"), newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], ["Compte", "Label", "Alias", "État"])
        self.assertEqual(rows[1], ["iPhone1", "Amazon A", "a@icloud.com", "actif"])
        self.assertEqual(rows[2], ["iPhone2", "Amazon C", "c@icloud.com", "inactif"])

    def test_empty_rows_still_write_csv_header(self):
        with open(self._write("csv", rows=[]), newline="", encoding="utf-8") as f:
            self.assertEqual(list(csv.reader(f)), [["Compte", "Label", "Alias", "État"]])

    def test_empty_rows_write_empty_txt(self):
        with open(self._write("txt", rows=[]), encoding="utf-8") as f:
            self.assertEqual(f.read(), "")


@mock.patch("banscan.random.uniform", return_value=0)
class ProcessRecordsTest(unittest.TestCase):
    def _run(self, hme, records, action):
        return asyncio.run(
            _process_records(hme, records, _DummyConsole(), "acc", action)
        )

    def test_deactivate_only_calls_deactivate(self, _uniform):
        hme = _FakeHME()
        rec = {"hme": "a@icloud.com", "anonymousId": "id-a", "isActive": True}
        done, failed = self._run(hme, [rec], "deactivate")
        self.assertEqual(done, ["a@icloud.com"])
        self.assertEqual(failed, [])
        self.assertEqual(hme.calls, [("deactivate", "id-a")])

    def test_delete_active_deactivates_then_deletes(self, _uniform):
        hme = _FakeHME()
        rec = {"hme": "a@icloud.com", "anonymousId": "id-a", "isActive": True}
        done, failed = self._run(hme, [rec], "delete")
        self.assertEqual(done, ["a@icloud.com"])
        self.assertEqual(hme.calls, [("deactivate", "id-a"), ("delete", "id-a")])

    def test_delete_inactive_deletes_directly(self, _uniform):
        hme = _FakeHME()
        rec = {"hme": "b@icloud.com", "anonymousId": "id-b", "isActive": False}
        done, failed = self._run(hme, [rec], "delete")
        self.assertEqual(done, ["b@icloud.com"])
        self.assertEqual(hme.calls, [("delete", "id-b")])

    def test_delete_skips_delete_when_deactivate_fails(self, _uniform):
        hme = _FakeHME(deactivate_ok=False)
        rec = {"hme": "a@icloud.com", "anonymousId": "id-a", "isActive": True}
        done, failed = self._run(hme, [rec], "delete")
        self.assertEqual(done, [])
        self.assertEqual(len(failed), 1)
        # Deletion must NOT be attempted if deactivation failed.
        self.assertEqual(hme.calls, [("deactivate", "id-a")])


class ResolveBanSignalsTest(unittest.TestCase):
    def test_default_returns_all_signals_in_order(self):
        self.assertEqual(
            [s["key"] for s in resolve_ban_signals()], BAN_SIGNAL_KEYS
        )

    def test_keys_filter_selects_a_subset(self):
        self.assertEqual(
            [s["key"] for s in resolve_ban_signals(keys=["on-hold"])], ["on-hold"]
        )

    def test_appeal_deactivates_and_on_hold_deletes_by_default(self):
        by_key = {s["key"]: s for s in resolve_ban_signals()}
        self.assertEqual(by_key["appeal"]["action"], "deactivate")
        self.assertEqual(by_key["on-hold"]["action"], "delete")

    def test_force_delete_upgrades_every_action(self):
        signals = resolve_ban_signals(force_delete=True)
        self.assertTrue(all(s["action"] == "delete" for s in signals))

    def test_legacy_top_level_query_overrides_appeal_only(self):
        by_key = {
            s["key"]: s
            for s in resolve_ban_signals(
                {"text_query": "custom-token", "subject_query": ""}
            )
        }
        self.assertEqual(by_key["appeal"]["text_query"], "custom-token")
        # on-hold keeps its own subject-only query, untouched by the legacy fields.
        self.assertEqual(by_key["on-hold"]["text_query"], "")
        self.assertTrue(by_key["on-hold"]["subject_query"])

    def test_signals_config_override_tunes_a_single_signal(self):
        signal = resolve_ban_signals(
            {"signals": {"on-hold": {"subject_query": "on hold", "action": "deactivate"}}},
            keys=["on-hold"],
        )[0]
        self.assertEqual(signal["subject_query"], "on hold")
        self.assertEqual(signal["action"], "deactivate")

    def test_on_hold_search_is_subject_only(self):
        criteria = _build_search_criteria(resolve_ban_signals(keys=["on-hold"])[0])
        self.assertEqual(criteria[0], "SUBJECT")
        self.assertNotIn("TEXT", criteria)


class LoadGmailConfigTest(unittest.TestCase):
    def _write(self, payload):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def _load(self, payload, env=None):
        path = self._write(payload)
        cleared = {"GMAIL_ADDRESS": "", "GMAIL_APP_PASSWORD": ""}
        with mock.patch.dict(os.environ, {**cleared, **(env or {})}, clear=False):
            if not env:
                os.environ.pop("GMAIL_ADDRESS", None)
                os.environ.pop("GMAIL_APP_PASSWORD", None)
            return load_gmail_config(path, allow_prompt=False)

    def test_single_account_is_backward_compatible(self):
        config = self._load({"address": "a@gmail.com", "app_password": "pw"})
        self.assertEqual(len(config["accounts"]), 1)
        self.assertEqual(config["accounts"][0]["address"], "a@gmail.com")

    def test_accounts_list_yields_every_inbox(self):
        config = self._load(
            {
                "accounts": [
                    {"name": "g1", "address": "a@gmail.com", "app_password": "pw1"},
                    {"address": "b@gmail.com", "app_password": "pw2"},
                ]
            }
        )
        self.assertEqual(
            [a["address"] for a in config["accounts"]], ["a@gmail.com", "b@gmail.com"]
        )
        # name defaults to the address; imap host/port defaults are applied.
        self.assertEqual(config["accounts"][1]["name"], "b@gmail.com")
        self.assertEqual(config["accounts"][0]["imap_host"], "imap.gmail.com")
        self.assertEqual(config["accounts"][0]["imap_port"], 993)

    def test_account_missing_password_raises(self):
        with self.assertRaises(ValueError):
            self._load({"accounts": [{"address": "a@gmail.com"}]})

    def test_env_vars_pin_a_single_inbox(self):
        config = self._load(
            {
                "accounts": [
                    {"address": "a@gmail.com", "app_password": "pw1"},
                    {"address": "b@gmail.com", "app_password": "pw2"},
                ]
            },
            env={"GMAIL_ADDRESS": "env@gmail.com", "GMAIL_APP_PASSWORD": "envpw"},
        )
        self.assertEqual(len(config["accounts"]), 1)
        self.assertEqual(config["accounts"][0]["address"], "env@gmail.com")


class BuildFlaggedRowsCallableTest(unittest.TestCase):
    def setUp(self):
        self.banned_by_account = {
            "iPhone1": [
                {"hme": "a@icloud.com", "label": "A", "isActive": True},
                {"hme": "b@icloud.com", "label": "B", "isActive": False},
            ]
        }

    def test_per_record_action_flags_delete_even_when_inactive(self):
        actions = {"a@icloud.com": "deactivate", "b@icloud.com": "delete"}
        rows = build_flagged_rows(self.banned_by_account, lambda r: actions[r["hme"]])
        by_alias = {r["alias"]: r for r in rows}
        # active + deactivate is flagged; inactive + delete is still flagged.
        self.assertEqual(set(by_alias), {"a@icloud.com", "b@icloud.com"})
        self.assertEqual(by_alias["a@icloud.com"]["action"], "deactivate")
        self.assertEqual(by_alias["b@icloud.com"]["action"], "delete")

    def test_inactive_deactivate_is_not_flagged(self):
        rows = build_flagged_rows(
            {"iPhone1": [{"hme": "c@icloud.com", "isActive": False}]},
            lambda r: "deactivate",
        )
        self.assertEqual(rows, [])


class _FakeIMAP:
    """Minimal in-memory IMAP double for scan_ban_recipients."""

    def __init__(self, search_map, headers):
        self._search_map = search_map
        self._headers = headers
        self.logged_out = False

    def login(self, address, password):
        return ("OK", [b""])

    def list(self):
        return ("OK", [b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"'])

    def select(self, mailbox, readonly=False):
        return ("OK", [b"1"])

    def search(self, charset, *criteria):
        ids = self._search_map.get(" ".join(criteria), [])
        return ("OK", [b" ".join(ids)] if ids else [b""])

    def fetch(self, num, spec):
        raw = self._headers.get(num)
        if raw is None:
            return ("NO", None)
        return ("OK", [(b"1 (BODY[HEADER] {0}", raw)])

    def logout(self):
        self.logged_out = True
        return ("BYE", [b""])


class ScanBanRecipientsTest(unittest.TestCase):
    def test_groups_recipients_per_signal(self):
        signals = resolve_ban_signals()  # appeal + on-hold
        appeal_key = " ".join(_build_search_criteria(signals[0]))
        on_hold_key = " ".join(_build_search_criteria(signals[1]))
        search_map = {appeal_key: [b"1"], on_hold_key: [b"2"]}
        headers = {
            b"1": b"To: appeal.alias@icloud.com\r\nSubject: baa-customer-appeal\r\n\r\n",
            b"2": b"To: hold.alias@icloud.com\r\nSubject: temporarily on hold\r\n\r\n",
        }
        fake = _FakeIMAP(search_map, headers)
        account = {"address": "dest@gmail.com", "app_password": "pw"}
        with mock.patch("banscan.imaplib.IMAP4_SSL", return_value=fake):
            result = scan_ban_recipients(account, signals)
        self.assertEqual(result["appeal"], (1, {"appeal.alias@icloud.com"}))
        self.assertEqual(result["on-hold"], (1, {"hold.alias@icloud.com"}))
        self.assertTrue(fake.logged_out)


if __name__ == "__main__":
    unittest.main()
