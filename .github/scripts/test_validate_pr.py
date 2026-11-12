#!/usr/bin/env python3
"""Tests for validate_pr.py. Run: python3 -m unittest discover -s .github/scripts"""

from __future__ import annotations

import datetime as dt
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_pr  # noqa: E402

TODAY = dt.date(2026, 11, 5)


def png(width: int = 800, height: int = 600) -> bytes:
    """Smallest byte string the validator accepts as a PNG header."""
    return validate_pr.PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def item(**overrides) -> dict:
    data = {
        "name": "Hello World",
        "version": "1.0",
        "author_username": "alice",
        "release_date": "2026-10-01",
        "license": "MIT",
        "price_usd": "0",
        "download_url": "https://github.com/alice/hello-world/archive/refs/tags/v1.0.zip",
        "demo_url": "",
        "information_url": "https://github.com/alice/hello-world",
        "description": "Says hello.",
        "features": {"0": "Says <code>hello</code>."},
    }
    data.update(overrides)
    return data


def author(github: str = "https://github.com/alice", **overrides) -> dict:
    data = {"name": "Alice", "email": "", "website": "", "github": github}
    data.update(overrides)
    return data


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.git("init", "-q", "-b", "master")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.write("README.md", "readme\n")
        self.write_json("authors/alice.json", author())
        self.write_json("authors/bob.json", author("https://github.com/bob", name="Bob"))
        self.write_json("items/hello-world/metadata.json", item())
        self.write("items/hello-world/screenshot.png", png())
        self.write_json("items/legacyTheme/metadata.json", item(author_username="bob", demo_url="http://example.com"))
        self.commit("base")
        self.git("checkout", "-q", "-b", "pr")

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers ----------------------------------------------------------

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True, text=True).stdout

    def write(self, path: str, content: str | bytes) -> None:
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(full, mode) as fh:
            fh.write(content)

    def write_json(self, path: str, data: dict) -> None:
        self.write(path, json.dumps(data, indent="\t", ensure_ascii=False) + "\n")

    def write_index(self, path: str, content: bytes) -> None:
        """Commit a file straight into git, bypassing the (maybe case-insensitive) filesystem."""
        sha = subprocess.run(["git", "-C", self.repo, "hash-object", "-w", "--stdin"], input=content,
                             check=True, capture_output=True).stdout.decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"100644,{sha},{path}")
        self.git("commit", "-q", "-m", f"add {path}")
        self.index_only = True  # the working tree no longer matches; don't `git add -A` over it

    def commit(self, msg: str = "change") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def validate(self, login: str | None = "alice"):
        if not getattr(self, "index_only", False):
            self.commit()
        git = validate_pr.Git(self.repo)
        validator = validate_pr.Validator(git, git.resolve("master"), git.resolve("pr"), login, TODAY)
        report, changes = validator.run()
        return report, report.eligible(bool(changes))

    def all_errors(self, report) -> str:
        return "\n".join(m for msgs in report.errors.values() for m in msgs)

    def all_warnings(self, report) -> str:
        return "\n".join(m for msgs in report.warnings.values() for m in msgs)


class OwnershipTests(RepoTestCase):
    def test_owner_update_is_eligible(self):
        self.write_json("items/hello-world/metadata.json", item(version="1.1", release_date="2026-11-01"))
        report, eligible = self.validate("alice")
        self.assertTrue(report.ok, report.errors)
        self.assertTrue(eligible, report.manual)

    def test_owner_login_is_case_insensitive(self):
        self.write_json("items/hello-world/metadata.json", item(version="1.1", release_date="2026-11-01"))
        _, eligible = self.validate("Alice")
        self.assertTrue(eligible)

    def test_non_owner_needs_review(self):
        self.write_json("items/hello-world/metadata.json", item(description_ru="Привет."))
        report, eligible = self.validate("mallory")
        self.assertTrue(report.ok, report.errors)
        self.assertFalse(eligible)
        self.assertIn("belongs to author", "\n".join(report.manual))

    def test_ownership_comes_from_base_not_pr(self):
        # Mallory rewrites alice's author file to point at herself in the same PR.
        self.write_json("authors/alice.json", author("https://github.com/mallory"))
        self.write_json("items/hello-world/metadata.json", item(version="9.9"))
        _, eligible = self.validate("mallory")
        self.assertFalse(eligible)

    def test_owner_changing_github_profile_needs_review(self):
        self.write_json("authors/alice.json", author("https://github.com/alice-new"))
        report, eligible = self.validate("alice")
        self.assertFalse(eligible)
        self.assertIn("controls theme ownership", "\n".join(report.manual))

    def test_changing_author_username_needs_review(self):
        self.write_json("items/hello-world/metadata.json", item(author_username="bob"))
        _, eligible = self.validate("alice")
        self.assertFalse(eligible)

    def test_download_domain_change_needs_review(self):
        self.write_json("items/hello-world/metadata.json", item(download_url="https://evil.example/theme.zip"))
        report, eligible = self.validate("alice")
        self.assertFalse(eligible)
        self.assertIn("different site", "\n".join(report.manual))

    def test_download_same_domain_is_eligible(self):
        self.write_json("items/hello-world/metadata.json",
                        item(download_url="https://github.com/alice/hello-world/archive/refs/tags/v1.1.zip"))
        _, eligible = self.validate("alice")
        self.assertTrue(eligible)

    def test_download_moved_to_another_github_account_needs_review(self):
        self.write_json("items/hello-world/metadata.json",
                        item(download_url="https://github.com/mallory/hello-world/archive/v1.1.zip"))
        _, eligible = self.validate("alice")
        self.assertFalse(eligible)

    def test_download_to_codeload_of_same_account_is_eligible(self):
        self.write_json("items/hello-world/metadata.json",
                        item(download_url="https://codeload.github.com/alice/hello-world/zip/refs/tags/v1.1"))
        _, eligible = self.validate("alice")
        self.assertTrue(eligible)

    def test_new_theme_needs_review(self):
        self.write_json("items/new-theme/metadata.json", item(name="New"))
        self.write("items/new-theme/screenshot.png", png())
        report, eligible = self.validate("alice")
        self.assertTrue(report.ok, report.errors)
        self.assertFalse(eligible)

    def test_maintainer_file_needs_review(self):
        self.write("README.md", "changed\n")
        report, eligible = self.validate("alice")
        self.assertTrue(report.ok)
        self.assertFalse(eligible)

    def test_mixed_owned_and_not_owned_needs_review(self):
        self.write_json("items/hello-world/metadata.json", item(version="1.1"))
        self.write_json("items/legacyTheme/metadata.json", item(author_username="bob", version="2.0", demo_url="http://example.com"))
        _, eligible = self.validate("alice")
        self.assertFalse(eligible)

    def test_no_author_given_is_never_eligible(self):
        self.write_json("items/hello-world/metadata.json", item(version="1.1"))
        _, eligible = self.validate(None)
        self.assertFalse(eligible)


class LayoutTests(RepoTestCase):
    def test_folder_outside_items_is_an_error(self):
        self.write_json("hello-world/metadata.json", item())
        report, _ = self.validate()
        self.assertIn("items/hello-world/metadata.json", self.all_errors(report))

    def test_wrong_screenshot_name_is_an_error(self):
        self.write_index("items/hello-world/screenShot.png", png())
        report, _ = self.validate()
        self.assertIn("Rename it to `screenshot.png`", self.all_errors(report))

    def test_new_theme_requires_lowercase_folder(self):
        self.write_json("items/MyTheme/metadata.json", item())
        self.write("items/MyTheme/screenshot.png", png())
        report, _ = self.validate()
        self.assertIn("lowercase", self.all_errors(report))

    def test_new_theme_name_collision_is_case_insensitive(self):
        self.write_index("items/legacytheme/metadata.json", json.dumps(item()).encode())
        self.write_index("items/legacytheme/screenshot.png", png())
        report, _ = self.validate()
        self.assertIn("already exists", self.all_errors(report))

    def test_new_theme_requires_screenshot(self):
        self.write_json("items/new-theme/metadata.json", item())
        report, _ = self.validate()
        self.assertIn("`screenshot.png` is missing", self.all_errors(report))

    def test_legacy_camelcase_folder_is_allowed(self):
        self.write_json("items/legacyTheme/metadata.json", item(author_username="bob", version="1.1", demo_url="http://example.com"))
        report, _ = self.validate("bob")
        self.assertTrue(report.ok, report.errors)

    def test_symlink_is_rejected_without_being_followed(self):
        os.remove(os.path.join(self.repo, "items/hello-world/metadata.json"))
        os.symlink("/etc/passwd", os.path.join(self.repo, "items/hello-world/metadata.json"))
        report, eligible = self.validate()
        self.assertIn("regular file", self.all_errors(report))
        self.assertNotIn("root:", self.all_errors(report))
        self.assertFalse(eligible)

    def test_unknown_author_is_an_error(self):
        self.write_json("items/hello-world/metadata.json", item(author_username="Alice"))
        report, _ = self.validate()
        self.assertIn("authors/Alice.json` does not exist", self.all_errors(report))


class MetadataTests(RepoTestCase):
    def errors_for(self, **overrides) -> str:
        self.write_json("items/hello-world/metadata.json", item(**overrides))
        report, _ = self.validate()
        return self.all_errors(report)

    def test_removing_a_translation_is_flagged(self):
        self.write_json("items/hello-world/metadata.json", item(description_ru="Привет."))
        self.commit("add ru")
        self.git("checkout", "-q", "master")
        self.git("merge", "-q", "--ff-only", "pr")
        self.git("checkout", "-q", "pr")
        self.write_json("items/hello-world/metadata.json", item(version="1.1"))
        report, eligible = self.validate("alice")
        self.assertIn("Removes the translation `description_ru`", self.all_warnings(report))
        self.assertFalse(eligible)

    def test_valid_update_has_no_errors(self):
        self.assertEqual(self.errors_for(version="1.2.3"), "")

    def test_invalid_json(self):
        self.write("items/hello-world/metadata.json", '{"name": "x",}')
        report, _ = self.validate()
        self.assertIn("Invalid JSON", self.all_errors(report))

    def test_duplicate_keys(self):
        self.write("items/hello-world/metadata.json", json.dumps(item())[:-1] + ', "description": "again"}')
        report, _ = self.validate()
        self.assertIn("duplicate key", self.all_errors(report))

    def test_bom(self):
        self.write("items/hello-world/metadata.json", b"\xef\xbb\xbf" + json.dumps(item()).encode())
        report, _ = self.validate()
        self.assertIn("BOM", self.all_errors(report))

    def test_required_field(self):
        self.assertIn("`license`", self.errors_for(license=""))

    def test_placeholder(self):
        self.assertIn("placeholder", self.errors_for(description="_DESCRIPTION_"))

    def test_identifier_with_underscores_is_not_a_placeholder(self):
        text = "Set <code>$NUMBER_STICKY_PAGES_HOME_PAGE</code> and <code>$_DEFAULT_COVER_IMAGE</code> in MY_CONSTANT_NAME."
        self.assertEqual(self.errors_for(description=text, features={"0": text}), "")

    def test_problems_already_on_master_do_not_block_other_changes(self):
        # A theme on master has several old problems; a translator only adds Russian text.
        old = item(author_username="nobody", price_usd="", license="", release_date="2023-24-11",
                   description_de="_DESCRIPTION_GERMAN_", features_es="none")
        self.write_json("items/hello-world/metadata.json", old)
        self.commit("old problems")
        self.git("checkout", "-q", "master")
        self.git("merge", "-q", "--ff-only", "pr")
        self.git("checkout", "-q", "pr")
        self.write_json("items/hello-world/metadata.json", dict(old, description_ru="Привет."))
        report, _ = self.validate("mallory")
        self.assertTrue(report.ok, report.errors)
        warnings = self.all_warnings(report)
        for expected in ("`price_usd` is missing or empty", "`license` is missing or empty", "`release_date` must be a real date",
                         "placeholder", "`features_es` must be an object", "shows no author"):
            self.assertIn(expected, warnings)

    def test_empty_price_is_reported_once(self):
        self.assertEqual(self.errors_for(price_usd="").count("price_usd"), 1)

    def test_script_tag_in_description(self):
        self.assertIn("HTML that is not allowed", self.errors_for(description="Hi <script>alert(1)</script>"))

    def test_attribute_on_allowed_tag(self):
        self.assertIn("HTML that is not allowed", self.errors_for(features={"0": '<b onclick="x()">hi</b>'}))

    def test_allowed_tags_and_entities(self):
        self.assertEqual(self.errors_for(description="Uses <code>&lt;title&gt;</code> and <b>bold</b>, a < b."), "")

    def test_javascript_url(self):
        self.assertIn("`download_url`", self.errors_for(download_url="javascript:alert(1)"))

    def test_url_with_quote(self):
        self.assertIn("quotes", self.errors_for(demo_url='https://x.example/" onmouseover="x'))

    def test_http_url_new_value(self):
        self.assertIn("must use `https://`", self.errors_for(demo_url="http://example.com"))

    def test_price(self):
        # Each call commits on top of the previous one; the check always compares master...pr.
        for bad in ("free", "$5", "-2", "1.999", True):
            with self.subTest(price=bad):
                self.assertIn("price_usd", self.errors_for(price_usd=bad))
        for good in ("0", "-1", "4.99", 19, "0.50"):
            with self.subTest(price=good):
                self.assertEqual(self.errors_for(price_usd=good), "")

    def test_dates(self):
        self.assertIn("real date", self.errors_for(release_date="2023-24-11"))
        self.assertIn("real date", self.errors_for(release_date="18.10.24"))
        self.assertIn("in the future", self.errors_for(release_date="2027-01-01"))

    def test_version(self):
        self.assertIn("`version`", self.errors_for(version="latest"))

    def test_unchanged_legacy_problem_is_only_a_warning(self):
        # legacyTheme has an http:// demo_url on master; bob only bumps the version.
        self.write_json("items/legacyTheme/metadata.json",
                        item(author_username="bob", version="1.1", demo_url="http://example.com"))
        report, eligible = self.validate("bob")
        self.assertTrue(report.ok, report.errors)
        self.assertIn("must use `https://`", self.all_warnings(report))
        self.assertTrue(eligible)


class ScreenshotTests(RepoTestCase):
    def test_jpeg_renamed_to_png(self):
        self.write("items/hello-world/screenshot.png", b"\xff\xd8\xff\xe0" + b"0" * 100)
        report, _ = self.validate()
        self.assertIn("JPEG", self.all_errors(report))

    def test_too_small(self):
        self.write("items/hello-world/screenshot.png", png(100, 100))
        report, _ = self.validate()
        self.assertIn("100x100", self.all_errors(report))

    def test_too_large_file(self):
        self.write("items/hello-world/screenshot.png", png() + b"\0" * (validate_pr.MAX_PNG_BYTES + 1))
        report, _ = self.validate()
        self.assertIn("maximum", self.all_errors(report))

    def test_non_recommended_size_is_warning(self):
        self.write("items/hello-world/screenshot.png", png(1280, 720))
        report, eligible = self.validate()
        self.assertTrue(report.ok)
        self.assertIn("800x600 is recommended", self.all_warnings(report))
        self.assertTrue(eligible)


class AuthorTests(RepoTestCase):
    def test_new_author_requires_github(self):
        self.write_json("authors/carol.json", author(""))
        report, _ = self.validate("carol")
        self.assertIn("`github` must be your GitHub profile", self.all_errors(report))

    def test_new_author_filename(self):
        self.write_json("authors/Carol Smith.json", author("https://github.com/carol"))
        report, _ = self.validate("carol")
        self.assertIn("must be lowercase", self.all_errors(report))

    def test_author_url_fields(self):
        self.write_json("authors/alice.json", author(website="alice.example"))
        report, _ = self.validate("alice")
        self.assertIn("`website`", self.all_errors(report))

    def test_owner_updates_own_author_file(self):
        self.write_json("authors/alice.json", author(website="https://alice.example"))
        report, eligible = self.validate("alice")
        self.assertTrue(report.ok, report.errors)
        self.assertTrue(eligible)


class CommentSafetyTests(RepoTestCase):
    def test_hostile_path_is_rendered_inside_code(self):
        self.write_index("items/x/a`@everyone\n## hi.json", b"{}")
        report, _ = self.validate()
        md = validate_pr.render(report, False, True)
        self.assertNotIn("\n## hi", md)
        self.assertNotIn("`@everyone", md)


class RenderTests(unittest.TestCase):
    def test_untrusted_text_cannot_break_out_of_code_span(self):
        self.assertEqual(validate_pr.show("a`b\nc"), "`a'b c`")

    def test_marker_present(self):
        report = validate_pr.Report()
        self.assertTrue(validate_pr.render(report, False, True).startswith(validate_pr.MARKER))

    def test_verdicts(self):
        report = validate_pr.Report()
        self.assertIn("## 👍 Ready to merge", validate_pr.render(report, False, True))
        self.assertIn("## 👎 Not ready to merge", validate_pr.render(report, False, False))
        report.error("items/x", "broken")
        self.assertIn("## 👎 Not ready to merge: 1 thing to fix", validate_pr.render(report, False, True))
        self.assertNotIn("auto", validate_pr.render(report, False, True).lower().replace("automatically", ""))

    def test_not_ready_lists_numbered_fixes_for_the_author(self):
        report = validate_pr.Report()
        report.error("items/x", "First fix.")
        report.error("authors/x.json", "Second fix.")
        report.warn("items/x", "A hint.")
        md = validate_pr.render(report, False, True, "kusalo")
        self.assertIn("@kusalo, thanks for the PR!", md)
        self.assertIn("1. **`authors/x.json`**: Second fix.", md)
        self.assertIn("2. **`items/x`**: First fix.", md)
        self.assertIn("- ⚠️ **`items/x`**: A hint.", md)
        self.assertLess(md.index("First fix."), md.index("A hint."))

    def test_odd_author_login_is_not_mentioned(self):
        report = validate_pr.Report()
        report.error("items/x", "Fix.")
        self.assertNotIn("@", validate_pr.render(report, False, True, "x y\n## z"))

    def test_valid_but_needs_review_is_not_ready_to_merge(self):
        report = validate_pr.Report()
        report.needs_review("Adds a new theme `x`.")
        self.assertEqual(report.verdict(True), "review")
        md = validate_pr.render(report, False, True, "alice")
        self.assertIn("## 👍 Listing OK, waiting for a maintainer review", md)
        self.assertNotIn("Ready to merge", md)
        self.assertIn("- [ ] Adds a new theme `x`.", md)

    def test_ready_only_when_nothing_needs_review(self):
        report = validate_pr.Report()
        report.owned.append("items/x")
        self.assertEqual(report.verdict(True), "ready")
        self.assertIn("## 👍 Ready to merge", validate_pr.render(report, True, True))

    def test_preview_cell_cannot_break_table(self):
        report = validate_pr.Report()
        report.previews["x"] = [("Name", validate_pr.show("a | b"))]
        self.assertIn("| Name | `a &#124; b` |", validate_pr.render(report, False, True))


class FieldNameTests(RepoTestCase):
    def errors_for(self, extra: dict, path="items/hello-world/metadata.json", base=None):
        data = dict(base or item())
        data.update(extra)
        self.write_json(path, data)
        report, _ = self.validate()
        return report

    def test_misnamed_fields_are_errors_with_a_suggestion(self):
        cases = {
            "Name": "`name`",
            "downloadUrl": "`download_url`",
            "download-url": "`download_url`",
            "descripton": "`description`",
            "information_link": None,
            "description_sp": "`description_es`",
            "descriptionDE": "`description_de`",
            "features_ger": "`features_de`",
            "author": None,
        }
        for key, guess in cases.items():
            with self.subTest(key=key):
                report = self.errors_for({key: "x"})
                errors = self.all_errors(report)
                self.assertTrue("Unknown field" in errors or "not a language code" in errors, errors)
                if guess:
                    self.assertIn(f"Did you mean {guess}?", errors)

    def test_description_en_is_an_error(self):
        self.assertIn("English goes in `description`", self.all_errors(self.errors_for({"description_en": "x"})))

    def test_unknown_language_code_is_an_error(self):
        self.assertIn("not a language code", self.all_errors(self.errors_for({"description_xq": "x"})))

    def test_language_not_shown_on_site_is_a_warning(self):
        report = self.errors_for({"description_pt": "Olá."})
        self.assertTrue(report.ok, report.errors)
        self.assertIn("only shows", self.all_warnings(report))

    def test_site_languages_are_fine(self):
        report = self.errors_for({"description_es": "Hola.", "features_ru": {"0": "Привет."}})
        self.assertEqual(self.all_errors(report), "")
        self.assertEqual(self.all_warnings(report), "")

    def test_unchanged_legacy_unknown_field_is_ignored(self):
        self.write_json("items/legacyTheme/metadata.json", item(author_username="bob", demo_url="http://example.com",
                                                                 homepage="https://x.example.com"))
        self.commit("legacy field")
        self.git("checkout", "-q", "master")
        self.git("merge", "-q", "--ff-only", "pr")
        self.git("checkout", "-q", "pr")
        self.write_json("items/legacyTheme/metadata.json", item(author_username="bob", demo_url="http://example.com",
                                                                 homepage="https://x.example.com", version="1.1"))
        report, _ = self.validate("bob")
        self.assertTrue(report.ok, report.errors)

    def test_new_unknown_field_set_to_null_is_an_error(self):
        self.assertIn("Did you mean `download_url`?", self.all_errors(self.errors_for({"downloadUrl": None})))

    def test_translation_fields_are_not_allowed_in_author_files(self):
        report = self.errors_for({"description_es": ""}, path="authors/alice.json", base=author())
        self.assertIn("Unknown field `description_es`", self.all_errors(report))

    def test_misnamed_author_field(self):
        report = self.errors_for({"githubUrl": "https://github.com/alice"}, path="authors/alice.json", base=author())
        self.assertIn("Unknown field `githubUrl`", self.all_errors(report))
        self.assertIn("Did you mean `github`?", self.all_errors(report))


class UrlTests(RepoTestCase):
    def errors_for(self, **overrides):
        self.write_json("items/hello-world/metadata.json", item(**overrides))
        report, _ = self.validate()
        return self.all_errors(report)

    def test_host_without_domain_is_an_error(self):
        # The mistake from PR #493: the GitHub path was typed as the host name.
        self.assertIn("valid domain", self.errors_for(information_url="https://amazingmarketingagency/theme"))
        self.assertIn("valid domain", self.errors_for(demo_url="https://localhost/demo"))

    def test_normal_hosts_are_fine(self):
        for url in ("https://github.com/a/b", "https://sub.example.co.uk/x?y=1#z", "https://xn--bcher-kva.example/",
                    "https://example.com.:443/a"):
            with self.subTest(url=url):
                self.assertEqual(self.errors_for(information_url=url), "")


class PreviewTests(RepoTestCase):
    def test_preview_shows_what_the_site_renders(self):
        self.write_json("items/hello-world/metadata.json", item(version="1.1", description_es="Hola."))
        report, _ = self.validate()
        rows = dict(report.previews["hello-world"])
        self.assertEqual(rows["Made by"], "`Alice`")
        self.assertEqual(rows["Version"], "`1.1`")
        self.assertTrue(rows["Languages"].startswith("en, es"))
        self.assertIn("Download (Bludit v3)", rows)
        self.assertEqual(rows["Screenshot"], "yes")

    def test_preview_flags_missing_author_and_paid_label(self):
        self.write_json("items/hello-world/metadata.json", item(author_username="nobody", price_usd="9"))
        report, _ = self.validate()
        rows = dict(report.previews["hello-world"])
        self.assertIn("not found", rows["Made by"])
        self.assertIn("Buy $9", rows["Price"])
        self.assertIn("Buy link", rows)


class LinkCheckTests(RepoTestCase):
    def run_links(self, responses: dict, **overrides):
        self.write_json("items/hello-world/metadata.json", item(**overrides))
        report, _ = self.validate()
        asked = []

        def fake(url):
            asked.append(url)
            return responses.get(url, (200, ""))

        validate_pr.check_links(report, fetch=fake)
        return report, asked

    def test_only_new_or_changed_links_are_opened(self):
        _, asked = self.run_links({}, demo_url="https://demo.example.com/")
        self.assertEqual(asked, ["https://demo.example.com/"])

    def test_dead_download_is_an_error(self):
        url = "https://github.com/alice/hello-world/releases/download/v2/x.zip"
        report, _ = self.run_links({url: (404, "Not Found")}, download_url=url)
        self.assertIn("broken link", self.all_errors(report))
        self.assertEqual(report.verdict(True), "changes")

    def test_missing_domain_on_information_url_is_an_error(self):
        url = "https://gone.example.com/"
        report, _ = self.run_links({url: (None, validate_pr.NO_SUCH_HOST)}, information_url=url)
        self.assertIn("does not exist", self.all_errors(report))

    def test_dead_demo_is_only_a_warning(self):
        url = "https://demo.example.com/"
        report, _ = self.run_links({url: (404, "Not Found")}, demo_url=url)
        self.assertTrue(report.ok, report.errors)
        self.assertIn("broken link", self.all_warnings(report))

    def test_blocked_or_slow_sites_are_only_warnings(self):
        url = "https://shop.example.com/buy"
        for response in ((403, "Forbidden"), (503, "Unavailable"), (None, "timed out")):
            with self.subTest(response=response):
                report, _ = self.run_links({url: response}, information_url=url)
                self.assertTrue(report.ok, report.errors)
                self.assertIn("could not be confirmed", self.all_warnings(report))

    def test_private_addresses_are_refused(self):
        with self.assertRaises(validate_pr.LinkError):
            validate_pr.require_public_host("https://127.0.0.1/")


if __name__ == "__main__":
    unittest.main()
