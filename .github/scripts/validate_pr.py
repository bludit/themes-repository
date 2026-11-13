#!/usr/bin/env python3
"""Validate a pull request against the themes repository rules.

The script compares two git revisions (the base branch and the PR head) and
checks every theme and author touched by the PR. It reads the PR's files with
git plumbing (`git ls-tree`, `git cat-file`) and never checks them out, so a
PR cannot plant symlinks or code that this script would follow or run.

It gives one of three verdicts:

* 👍 Ready to merge: every rule passes (file and field names, values, links
  with --check-links), so themes.bludit.com can show the change, and nothing
  needs a closer look.
* 👍 Listing OK, waiting for a maintainer review: the files are correct, but a
  maintainer must check something first, for example a new theme's code,
  which this script never reads.
* 👎 Not ready to merge: the comment lists what the contributor must fix.

It also previews each theme as the site will show it. Nothing is merged
automatically.

Usage (locally, from the repository root):

    python3 .github/scripts/validate_pr.py --base origin/master --head HEAD \
        --author <your-github-login>

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import html
import http.client
import ipaddress
import json
import re
import socket
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

# New theme folders and author files: lowercase words separated by dashes.
SLUG_NEW = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# What the site's nginx rewrite accepts; existing legacy names are allowed.
SLUG_LEGACY = re.compile(r"^[A-Za-z0-9_-]+$")
SLUG_MAX = 64

ITEM_FILES = {"metadata.json", "screenshot.png"}

# Files only maintainers should change. Valid, but never auto-merged.
MAINTAINER_PATHS = re.compile(r"^(\.github/|templates/|README\.md$|\.gitignore$|LICENSE)")

REQUIRED_ITEM_FIELDS = (
    "name",
    "version",
    "author_username",
    "release_date",
    "license",
    "price_usd",
    "description",
)
# download_url is required for new themes (a few legacy themes have none).
REQUIRED_NEW_ITEM_FIELDS = ("download_url",)

ITEM_TEXT_FIELDS = {"name", "license", "credits"}
ITEM_KNOWN_FIELDS = {
    "name", "version", "author_username", "release_date", "license",
    "price_usd", "description", "features", "download_url", "download_url_v2",
    "download_url_v4", "demo_url", "information_url", "credits", "credits_url",
}
LANG_FIELD = re.compile(r"^(description|features)_([a-z]{2})$")
# ISO 639-1 codes. Translations in languages the site doesn't show yet are kept.
ISO_LANGS = set("""
aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv dz ee
el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is
it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms
mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk
sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi
yo za zh zu""".split())
# Common wrong codes for the site's languages.
LANG_ALIASES = {"sp": "es", "esp": "es", "spa": "es", "ge": "de", "ger": "de", "deu": "de", "rus": "ru", "eng": "en"}
# Fields that are links and may change the download target.
DOWNLOAD_FIELDS = ("download_url", "download_url_v2", "download_url_v4")
# Links shown as buttons on the site. A dead one blocks the merge, except the demo.
LINK_FIELDS = DOWNLOAD_FIELDS + ("information_url", "demo_url")
BLOCKING_LINK_FIELDS = DOWNLOAD_FIELDS + ("information_url",)
# Languages of themes.bludit.com besides English.
SITE_LANGS = ("es", "de", "ru")

AUTHOR_KNOWN_FIELDS = {
    "name", "email", "website", "twitter", "facebook", "github", "gitlab",
    "youtube", "reddit", "pinterest", "flickr", "vk", "mastodon", "linkedin",
    "contact_url", "google_plus", "telegram",
}
AUTHOR_NON_URL_FIELDS = {"name", "email"}

# Text is printed unescaped on themes.bludit.com, so only these plain tags
# (no attributes) are allowed. Anything else that looks like markup is rejected.
ALLOWED_TAGS = re.compile(r"</?(?:code|b|i|strong|em)>")
MARKUP = re.compile(r"<[A-Za-z/!?]")
# A leftover template value such as `_NAME_`, but not part of an identifier
# like `$NUMBER_STICKY_PAGES_HOME_PAGE`.
PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9$])_[A-Z][A-Z_]{2,}_(?![A-Za-z0-9])")

VERSION = re.compile(r"^v?\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?$")
PRICE = re.compile(r"^(?:-1|0|[1-9]\d{0,3}(?:\.\d{1,2})?|0\.\d{1,2})$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GITHUB_PROFILE = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/?$")
HOSTNAME = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
EMAIL = re.compile(r"^[^@\s\"'<>]+@[^@\s\"'<>]+\.[^@\s\"'<>]+$")

MAX_JSON_BYTES = 64 * 1024
MAX_PNG_BYTES = 1024 * 1024
WARN_PNG_BYTES = 500 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

REGULAR_FILE_MODES = {"100644", "100755"}

MARKER = "<!-- theme-validator -->"

USER_AGENT = "bludit-themes-check (+https://github.com/bludit/themes-repository)"
LINK_TIMEOUT = 10.0
MAX_LINKS = 20


# --------------------------------------------------------------------------
# Git access (read-only, no checkout of the PR)
# --------------------------------------------------------------------------

class Git:
    def __init__(self, repo: str):
        self.repo = repo

    def _run(self, *args: str) -> bytes:
        result = subprocess.run(
            ["git", "-C", self.repo, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
        return result.stdout

    def resolve(self, rev: str) -> str:
        return self._run("rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()

    def merge_base(self, a: str, b: str) -> str:
        return self._run("merge-base", a, b).decode().strip()

    def changed(self, base: str, head: str) -> list[tuple[str, str]]:
        """(status, path) for every file changed on head since the merge base."""
        out = self._run("diff", "--no-renames", "--name-status", "-z", f"{base}...{head}")
        parts = out.decode("utf-8", errors="surrogateescape").split("\0")
        pairs = []
        for i in range(0, len(parts) - 1, 2):
            pairs.append((parts[i][:1], parts[i + 1]))
        return pairs

    def entry(self, rev: str, path: str) -> tuple[str, str, int] | None:
        """(mode, type, size) of a path at rev, or None if missing."""
        out = self._run("ls-tree", "-l", "-z", rev, "--", path).decode("utf-8", errors="surrogateescape")
        for record in out.split("\0"):
            if not record:
                continue
            meta, _, name = record.partition("\t")
            if name != path:
                continue
            mode, otype, _sha, size = meta.split()
            return mode, otype, int(size) if size != "-" else 0
        return None

    def read(self, rev: str, path: str) -> bytes:
        return self._run("cat-file", "blob", f"{rev}:{path}")

    def list_dir(self, rev: str, path: str) -> list[str]:
        out = self._run("ls-tree", "--name-only", "-z", rev, "--", path.rstrip("/") + "/")
        return [p.rsplit("/", 1)[-1] for p in out.decode("utf-8", errors="surrogateescape").split("\0") if p]


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

@dataclass
class Report:
    errors: dict[str, list[str]] = field(default_factory=dict)
    warnings: dict[str, list[str]] = field(default_factory=dict)
    manual: list[str] = field(default_factory=list)
    owned: list[str] = field(default_factory=list)
    # (scope, field, url) of new or changed links, for check_links().
    links: list[tuple[str, str, str]] = field(default_factory=list)
    # slug -> rows of (label, Markdown value) showing what the site will display.
    previews: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    def error(self, scope: str, msg: str) -> None:
        self.errors.setdefault(scope, []).append(msg)

    def warn(self, scope: str, msg: str) -> None:
        self.warnings.setdefault(scope, []).append(msg)

    def needs_review(self, msg: str) -> None:
        if msg not in self.manual:
            self.manual.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors

    def eligible(self, has_changes: bool) -> bool:
        """Low risk: the PR author owns everything it changes and nothing needs a closer look."""
        return self.ok and has_changes and not self.manual and bool(self.owned)

    def verdict(self, has_changes: bool) -> str:
        """`changes`: the author must fix something. `review`: the listing is valid but a maintainer
        must look at something first (for example a new theme's code). `ready`: nothing left to do."""
        if not self.ok or not has_changes:
            return "changes"
        return "review" if self.manual else "ready"


def show(value: object, limit: int = 60) -> str:
    """Render untrusted text safely inside inline code in a Markdown comment."""
    text = str(value).replace("`", "'").replace("\r", " ").replace("\n", " ")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return f"`{text}`" if text else "`(empty)`"


# --------------------------------------------------------------------------
# Field checks
# --------------------------------------------------------------------------

def parse_json(raw: bytes, scope: str, report: Report) -> dict | None:
    if raw.startswith(b"\xef\xbb\xbf"):
        report.error(scope, "File starts with a UTF-8 BOM. Save it as UTF-8 without BOM (the site's PHP parser rejects it).")
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error(scope, f"File is not valid UTF-8 ({exc.reason} at byte {exc.start}). Save it with UTF-8 encoding.")
        return None

    def no_duplicates(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError(f"duplicate key {key!r}")
            seen[key] = value
        return seen

    def no_constants(name):
        raise ValueError(f"{name} is not valid JSON")

    try:
        data = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=no_constants)
    except json.JSONDecodeError as exc:
        hint = ""
        if exc.msg.startswith("Expecting ',' delimiter"):
            hint = " A comma is probably missing at the end of the previous line."
        elif exc.msg.startswith("Expecting property name"):
            hint = " A trailing comma before `}` is the usual cause."
        elif exc.msg.startswith("Extra data"):
            hint = " There is extra text after the closing `}`."
        elif exc.msg.startswith("Invalid control character"):
            hint = " Line breaks and tabs inside text must be written as `\\n` and `\\t`."
        report.error(scope, f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno}).{hint}")
        return None
    except ValueError as exc:
        report.error(scope, f"Invalid JSON: {exc}.")
        return None
    if not isinstance(data, dict):
        report.error(scope, "The file must contain a JSON object `{ ... }`.")
        return None
    return data


def check_text(scope: str, key: str, value: str, strict: bool, report: Report) -> None:
    if PLACEHOLDER.search(value):
        (report.error if strict else report.warn)(
            scope, f"`{key}` still contains a template placeholder: {show(value)}. "
                   "Replace it with real text, or leave the field empty (`\"\"`) if it does not apply.")
    stripped = ALLOWED_TAGS.sub("", value)
    if MARKUP.search(stripped):
        bad = MARKUP.search(stripped)
        snippet = stripped[bad.start(): bad.start() + 30]
        msg = (f"`{key}` contains HTML that is not allowed: {show(snippet)}. "
               "Only `<code>`, `<b>`, `<i>`, `<strong>` and `<em>` without attributes are allowed. "
               "To show a tag as text, write `&lt;` and `&gt;`, for example `&lt;title&gt;`.")
        (report.error if strict else report.warn)(scope, msg)


def check_field_name(scope: str, key: str, known: set[str], template: str, report: Report) -> bool:
    """Error for a field name the website doesn't read, with the likely intended name. True when known."""
    if key in known:
        return True
    lang = LANG_FIELD.match(key)
    if lang and lang.group(1) in known:
        code = lang.group(2)
        if code == "en":
            report.error(scope, f"{show(key)} is not a field: English goes in `{lang.group(1)}`.")
            return False
        if code in ISO_LANGS:
            if code not in SITE_LANGS:
                report.warn(scope, f"{show(key)} is kept, but themes.bludit.com only shows "
                                   + ", ".join(f"`{lang.group(1)}_{c}`" for c in SITE_LANGS) + " for now.")
            return True
        hint = (f" Did you mean `{lang.group(1)}_{LANG_ALIASES[code]}`?" if code in LANG_ALIASES
                else " Use a two-letter ISO 639-1 code, for example `description_es`, `description_de` or `description_ru`.")
        report.error(scope, f"{show(key)}: `{code}` is not a language code.{hint}")
        return False
    normalized = re.sub(r"[\s.-]+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())).lower()
    candidates = sorted(known)
    guess = normalized if normalized in known else None
    if guess is None:
        m = re.match(r"^(description|features)_?([a-z]{2,3})$", normalized)
        if m and m.group(2) in LANG_ALIASES:
            code = LANG_ALIASES[m.group(2)]
            guess = m.group(1) if code == "en" else f"{m.group(1)}_{code}"
    if guess is None:
        close = difflib.get_close_matches(normalized, candidates + [f"{k}_{c}" for k in ("description", "features")
                                                                    for c in SITE_LANGS], n=1, cutoff=0.75)
        guess = close[0] if close else None
    hint = f" Did you mean `{guess}`?" if guess else f" See `{template}` for the field names."
    report.error(scope, f"Unknown field {show(key)}; the website ignores it.{hint}")
    return False


def check_url(scope: str, key: str, value: object, strict: bool, report: Report) -> str | None:
    """Return the URL host when valid, else None."""
    if not isinstance(value, str):
        report.error(scope, f"`{key}` must be a string.")
        return None
    if value == "":
        return None
    problem = None
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:  # for example an unmatched `[` in the host
        parsed = urllib.parse.SplitResult("", "", "", "", "")
    if re.search(r"[\s\"'<>`\\]", value):
        problem = "contains spaces, quotes or angle brackets"
    elif parsed.scheme not in ("https", "http") or not parsed.netloc:
        problem = "must be a full URL starting with `https://`"
    elif parsed.scheme != "https":
        problem = "must use `https://`"
    elif not HOSTNAME.match((parsed.hostname or "").rstrip(".")):
        problem = "has no valid domain name"
    if problem:
        (report.error if strict else report.warn)(
            scope, f"`{key}` {problem}: {show(value)}. Write the full address, for example "
                   "`https://github.com/<user>/<repo>`, or leave it empty (`\"\"`).")
        return None
    return (parsed.hostname or "").lower()


GITHUB_HOSTS = {"github.com", "www.github.com", "codeload.github.com", "raw.githubusercontent.com",
                "objects.githubusercontent.com", "gitlab.com", "bitbucket.org"}


def download_origin(url: object) -> str | None:
    """Who controls a download link: the host, plus the account on code-hosting sites."""
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not host:
        return None
    if host in GITHUB_HOSTS:
        account = parts.path.strip("/").split("/", 1)[0].lower()
        host = "github.com" if "github" in host else host
        return f"{host}/{account}"
    return host


def github_login(url: object) -> str | None:
    """Login from an author's `github` field, tolerant of legacy formats."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    url = url.replace("https://www.github.com/", "https://github.com/")
    match = GITHUB_PROFILE.match(url)
    return match.group(1).lower() if match else None


# --------------------------------------------------------------------------
# Theme (items/<slug>/) validation
# --------------------------------------------------------------------------

class Validator:
    def __init__(self, git: Git, base: str, head: str, author: str | None, today: dt.date):
        self.git = git
        self.base = base
        self.head = head
        self.author = author.lower() if author else None
        self.today = today
        self.report = Report()

    # -- helpers ----------------------------------------------------------

    def read_json(self, rev: str, path: str, scope: str, report: Report | None = None) -> dict | None:
        report = report or self.report
        entry = self.git.entry(rev, path)
        if entry is None:
            return None
        mode, otype, size = entry
        if otype != "blob" or mode not in REGULAR_FILE_MODES:
            report.error(scope, f"{show(path, 120)} must be a regular file (symlinks and submodules are not allowed).")
            return None
        if size > MAX_JSON_BYTES:
            report.error(scope, f"{show(path, 120)} is too large ({size} bytes, max {MAX_JSON_BYTES}).")
            return None
        return parse_json(self.git.read(rev, path), scope, report)

    def base_json(self, path: str) -> dict | None:
        """Read a file from the base branch as the website would, tolerating legacy problems."""
        entry = self.git.entry(self.base, path)
        if entry is None or entry[1] != "blob" or entry[0] not in REGULAR_FILE_MODES or entry[2] > MAX_JSON_BYTES:
            return None
        try:
            data = json.loads(self.git.read(self.base, path).decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def owner_login(self, username: str) -> str | None:
        data = self.base_json(f"authors/{username}.json")
        return github_login(data.get("github")) if data else None

    def existing_slugs(self) -> set[str]:
        return {s.lower() for s in self.git.list_dir(self.base, "items")}

    # -- items ------------------------------------------------------------

    def check_item(self, slug: str, changes: dict[str, str]) -> None:
        scope = f"items/{slug}"
        meta_path = f"{scope}/metadata.json"
        base_meta = self.base_json(meta_path)
        is_new = base_meta is None and self.git.entry(self.base, meta_path) is None

        # Folder name
        if is_new:
            if not SLUG_NEW.match(slug) or len(slug) > SLUG_MAX:
                report_slug = slug.lower().replace("_", "-").replace(" ", "-")
                self.report.error(scope, f"Folder name {show(slug)} must be lowercase letters, numbers and dashes, "
                                         f"for example {show(report_slug)}.")
            elif slug.lower() in self.existing_slugs():
                self.report.error(scope, f"A theme named {show(slug)} already exists (names are case-insensitive). "
                                         "Choose another folder name, or update the existing theme if it is yours.")
        elif not SLUG_LEGACY.match(slug):
            self.report.error(scope, f"Folder name {show(slug)} contains characters the website cannot route.")

        # Files in the folder
        for name, status in sorted(changes.items()):
            if "/" in name:
                self.report.error(scope, f"Subfolders are not allowed: {show(f'{scope}/{name}')}. "
                                         "Only `metadata.json` and `screenshot.png` go in the theme folder.")
            elif name not in ITEM_FILES and status != "D":
                hint = ""
                if name.lower().startswith("screenshot"):
                    hint = " Rename it to `screenshot.png` (lowercase) and make sure it is a PNG image."
                elif name.lower() == "metadata.json":
                    hint = " The file name must be `metadata.json` in lowercase."
                self.report.error(scope, f"Unexpected file {show(name)}. Only `metadata.json` and `screenshot.png` are allowed.{hint}")

        head_meta_entry = self.git.entry(self.head, meta_path)
        if head_meta_entry is None:
            if is_new:
                self.report.error(scope, "`metadata.json` is missing. Copy it from `templates/item.json`.")
            else:
                self.report.needs_review(f"Deletes the theme {show(slug)}.")
            return

        meta = self.read_json(self.head, meta_path, scope)
        if meta is not None:
            self.check_metadata(scope, meta, base_meta, is_new)

        # Screenshot
        shot_path = f"{scope}/screenshot.png"
        shot_status = changes.get("screenshot.png")
        if shot_status in ("A", "M", "T"):
            self.check_png(scope, shot_path)
        elif shot_status == "D":
            self.report.needs_review(f"Deletes the screenshot of {show(slug)}.")
        has_shot = self.git.entry(self.head, shot_path) is not None
        misnamed_shot = any(n.lower().startswith("screenshot") and n not in ITEM_FILES and st != "D"
                            for n, st in changes.items())
        if not has_shot and is_new and not misnamed_shot:
            self.report.error(scope, "`screenshot.png` is missing. Add a PNG screenshot, 800x600 px recommended.")
        if meta is not None:
            self.report.previews[slug] = self.preview(meta, has_shot)

        # Ownership and auto-merge
        if is_new:
            self.report.needs_review(f"Adds a new theme {show(slug)}. The bot does not read theme code: "
                                     "download it and review the code before merging.")
            return
        owner = base_meta.get("author_username") if isinstance(base_meta, dict) else None
        owner_gh = self.owner_login(owner) if isinstance(owner, str) else None
        if self.author and owner_gh and owner_gh == self.author:
            self.report.owned.append(scope)
            if not has_shot and shot_status != "D":
                self.report.warn(scope, "This theme has no `screenshot.png`; the site shows a placeholder. Consider adding one.")
        elif not isinstance(owner, str):
            self.report.needs_review(f"Changes {show(slug)}, whose `metadata.json` on `master` cannot be read, so its owner is unknown.")
        elif not owner_gh:
            self.report.needs_review(f"Changes {show(slug)}, which belongs to author {show(owner)}; "
                                     f"`authors/{owner}.json` has no valid GitHub profile.")
        else:
            self.report.needs_review(f"Changes {show(slug)}, which belongs to author {show(owner)} (GitHub {show(owner_gh)}).")
        if meta is not None and base_meta is not None:
            removed = sorted(k for k, v in base_meta.items()
                             if LANG_FIELD.match(k) and v and not meta.get(k))
            if removed:
                listed = ", ".join(f"`{k}`" for k in removed)
                self.report.warn(scope, f"Removes the translation {listed}. If that was not on purpose, put it back.")
                self.report.needs_review(f"Removes translations from {show(slug)}: {listed}.")
            if meta.get("author_username") != base_meta.get("author_username"):
                self.report.needs_review(f"Changes the `author_username` of {show(slug)}.")
            for key in DOWNLOAD_FIELDS:
                old_origin = download_origin(base_meta.get(key, ""))
                new_origin = download_origin(meta.get(key, ""))
                if new_origin and new_origin != old_origin:
                    self.report.needs_review(f"Changes `{key}` of {show(slug)} to a different site ({show(new_origin)}). "
                                             "Check that the new download is the same theme.")

    def check_metadata(self, scope: str, meta: dict, base_meta: dict | None, is_new: bool) -> None:
        base_meta = base_meta or {}

        def changed(key: str) -> bool:
            return is_new or meta.get(key) != base_meta.get(key)

        def flag(key: str):
            """Error for a value this PR adds or changes; warning for one that is already on the base branch."""
            return self.report.error if changed(key) else self.report.warn

        def blank(value: object) -> bool:
            return value is None or (isinstance(value, str) and not value.strip())

        required = REQUIRED_ITEM_FIELDS + (REQUIRED_NEW_ITEM_FIELDS if is_new else ())
        for key in required:
            if blank(meta.get(key)):
                flag(key)(scope, f"Required field `{key}` is missing or empty. See `templates/item.json` for an example.")
        if not is_new and not meta.get("download_url"):
            self.report.warn(scope, "`download_url` is empty.")

        for key, value in meta.items():
            strict = changed(key)
            lang = LANG_FIELD.match(key)
            base_kind = lang.group(1) if lang else key
            added = key not in base_meta  # even when its value is null
            if (strict or added) and not check_field_name(scope, key, ITEM_KNOWN_FIELDS, "templates/item.json", self.report):
                continue

            if base_kind == "features":
                items = value.values() if isinstance(value, dict) else value if isinstance(value, list) else None
                if items is None:
                    flag(key)(scope, f"`{key}` must be an object like `{{\"0\": \"...\", \"1\": \"...\"}}`.")
                    continue
                for feature in items:
                    if not isinstance(feature, str):
                        flag(key)(scope, f"Every entry in `{key}` must be text.")
                    else:
                        check_text(scope, key, feature, strict, self.report)
            elif key.endswith("url"):
                if check_url(scope, key, value, strict, self.report) and strict and key in LINK_FIELDS:
                    self.report.links.append((scope, key, value))
            elif key == "price_usd":
                if blank(value):
                    continue  # already reported as a missing required field
                if isinstance(value, bool) or not isinstance(value, (str, int, float)) or not PRICE.match(str(value)):
                    flag(key)(scope, f"`price_usd` must be `0` (free), `-1` (variable/external price) "
                                     f"or a price like `9` or `4.99`, got {show(value)}.")
            elif isinstance(value, str):
                if base_kind in ITEM_TEXT_FIELDS or base_kind == "description":
                    check_text(scope, key, value, strict, self.report)
                elif PLACEHOLDER.search(value):
                    flag(key)(scope, f"`{key}` still contains a template placeholder: {show(value)}. "
                                     "Replace it with the real value, or leave it empty (`\"\"`) if it does not apply.")
            elif key in ITEM_KNOWN_FIELDS or lang:
                flag(key)(scope, f"`{key}` must be text, got {show(type(value).__name__)}.")

        version = meta.get("version")
        if isinstance(version, str) and version and not VERSION.match(version) and changed("version"):
            self.report.error(scope, f"`version` must look like `1.0` or `2.3.1`, got {show(version)}.")

        date = meta.get("release_date")
        if isinstance(date, str) and date:
            parsed = None
            if DATE.match(date):
                try:
                    parsed = dt.date.fromisoformat(date)
                except ValueError:
                    parsed = None
            if parsed is None:
                flag("release_date")(scope, f"`release_date` must be a real date in `YYYY-MM-DD` format, got {show(date)}.")
            elif parsed > self.today + dt.timedelta(days=2):
                flag("release_date")(scope, f"`release_date` {show(date)} is in the future. Use the date of the release, today at the latest.")
            elif not is_new and changed("version") and not changed("release_date"):
                self.report.warn(scope, "`version` changed but `release_date` did not. The site sorts themes by release date.")

        username = meta.get("author_username")
        if isinstance(username, str) and username:
            if not SLUG_LEGACY.match(username):
                flag("author_username")(scope, f"`author_username` {show(username)} is not a valid username. "
                                               "It must be the name of your file in `authors/`, without `.json`.")
            elif self.git.entry(self.head, f"authors/{username}.json") is None:
                if changed("author_username"):
                    self.report.error(scope, f"`author_username` is {show(username)} but `authors/{username}.json` does not exist. "
                                             "Add it in this PR (copy `templates/author.json`).")
                else:
                    self.report.warn(scope, f"`author_username` is {show(username)} but `authors/{username}.json` does not exist, "
                                            "so the site shows no author for this theme.")

        for key in ("name", "description"):
            value = meta.get(key)
            if isinstance(value, str) and len(value) > {"name": 80, "description": 600}[key] and changed(key):
                self.report.warn(scope, f"`{key}` is long ({len(value)} characters); keep it short for the theme list.")

    def preview(self, meta: dict, has_shot: bool) -> list[tuple[str, str]]:
        """What themes.bludit.com will show for this theme, as the site's PHP reads it."""
        def text(key: str, limit: int = 60) -> str:
            value = meta.get(key)
            return show(value, limit) if isinstance(value, str) and value.strip() else "—"

        author_name = None
        username = meta.get("author_username")
        if isinstance(username, str) and SLUG_LEGACY.match(username):
            data = self.read_json(self.head, f"authors/{username}.json", "preview", Report())
            if data and isinstance(data.get("name"), str) and data["name"].strip():
                author_name = data["name"]

        price = meta.get("price_usd")
        price = "" if isinstance(price, bool) else str(price)
        if price == "-1":
            paid, price_label = True, "Paid: *Buy from $1* button"
        elif PRICE.match(price) and float(price) > 0:
            paid, price_label = True, f"Paid: *Buy ${price}* button"
        else:
            paid, price_label = False, "Free: *Download* button"

        features = meta.get("features")
        features = features.values() if isinstance(features, dict) else features if isinstance(features, list) else []
        langs = ["en"] + [lang for lang in SITE_LANGS
                          if isinstance(meta.get(f"description_{lang}"), str) and meta[f"description_{lang}"].strip()]

        rows = [
            ("Name", text("name")),
            ("Made by", show(author_name) if author_name else "❌ author not found"),
            ("Version", text("version", 20)),
            ("Last update", text("release_date", 20)),
            ("Price", price_label),
            ("Description", text("description", 120)),
            ("Features", str(sum(1 for f in features if isinstance(f, str) and f.strip()))),
        ]
        labels = {"download_url": "Buy link" if paid else "Download (Bludit v3)",
                  "download_url_v2": "Download (Bludit v2)", "download_url_v4": "Download (Bludit v4)"}
        for key in DOWNLOAD_FIELDS:
            if isinstance(meta.get(key), str) and meta[key].strip():
                rows.append((labels[key], text(key, 100)))
        if not any(isinstance(meta.get(k), str) and meta[k].strip() for k in DOWNLOAD_FIELDS):
            rows.append(("Download", "❌ no download button"))
        rows += [
            ("More information", text("information_url", 100)),
            ("Live demo", text("demo_url", 100)),
            ("Languages", ", ".join(langs) + ("" if len(langs) > len(SITE_LANGS) else " (other languages show a *not translated yet* notice)")),
            ("Screenshot", "yes" if has_shot else "none, the site shows a default image"),
        ]
        return rows

    def check_png(self, scope: str, path: str) -> None:
        mode, otype, size = self.git.entry(self.head, path)
        if otype != "blob" or mode not in REGULAR_FILE_MODES:
            self.report.error(scope, "`screenshot.png` must be a regular file.")
            return
        if size > MAX_PNG_BYTES:
            self.report.error(scope, f"`screenshot.png` is {size // 1024} KB; the maximum is {MAX_PNG_BYTES // 1024} KB. "
                                     "Resize it or compress it (for example with TinyPNG or `pngquant`).")
            return
        data = self.git.read(self.head, path)
        if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR" or len(data) < 24:
            kind = "a JPEG" if data[:3] == b"\xff\xd8\xff" else "not a PNG"
            self.report.error(scope, f"`screenshot.png` is {kind} image. Export it as a real PNG; renaming the file is not enough.")
            return
        width, height = struct.unpack(">II", data[16:24])
        if width < 300 or height < 150 or width > 2400 or height > 2400:
            self.report.error(scope, f"`screenshot.png` is {width}x{height} px; use between 300x150 and 2400x2400 (800x600 recommended).")
        elif width != 800:
            self.report.warn(scope, f"`screenshot.png` is {width}x{height} px; 800x600 is recommended.")
        if size > WARN_PNG_BYTES:
            self.report.warn(scope, f"`screenshot.png` is {size // 1024} KB; under {WARN_PNG_BYTES // 1024} KB loads faster.")

    # -- authors ----------------------------------------------------------

    def check_author(self, username: str, status: str) -> None:
        path = f"authors/{username}.json"
        scope = path
        base_data = self.base_json(path)
        is_new = base_data is None and self.git.entry(self.base, path) is None

        if is_new and (not SLUG_NEW.match(username) or len(username) > SLUG_MAX):
            self.report.error(scope, f"Author file name {show(username + '.json')} must be lowercase letters, numbers "
                                     "and dashes, for example `max-power.json`.")

        if self.git.entry(self.head, path) is None:
            self.report.needs_review(f"Deletes the author {show(username)}.")
            return

        data = self.read_json(self.head, path, scope)
        if data is None:
            return
        base_data = base_data or {}

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            (self.report.error if is_new or name != base_data.get("name") else self.report.warn)(
                scope, "Required field `name` is missing or empty.")
        else:
            check_text(scope, "name", name, is_new or name != base_data.get("name"), self.report)

        for key, value in data.items():
            strict = is_new or value != base_data.get(key)
            if (strict or key not in base_data) and not check_field_name(
                    scope, key, AUTHOR_KNOWN_FIELDS, "templates/author.json", self.report):
                continue
            if not isinstance(value, str):
                (self.report.error if strict else self.report.warn)(scope, f"`{key}` must be text.")
                continue
            if key == "email":
                if value and not EMAIL.match(value):
                    (self.report.error if strict else self.report.warn)(scope, f"`email` is not a valid address: {show(value)}.")
            elif key == "telegram":
                check_text(scope, key, value, strict, self.report)
            elif key not in AUTHOR_NON_URL_FIELDS:
                check_url(scope, key, value, strict, self.report)

        gh = data.get("github", "")
        if is_new or gh != base_data.get("github"):
            if not isinstance(gh, str) or not GITHUB_PROFILE.match(gh):
                self.report.error(scope, "`github` must be your GitHub profile, like `https://github.com/your-login`. "
                                         "It is how the repository knows which themes you own.")
            elif self.author and github_login(gh) != self.author:
                self.report.warn(scope, f"`github` points to {show(github_login(gh))}, but this PR was opened by {show(self.author)}.")

        # Ownership
        if is_new:
            self.report.needs_review(f"Adds a new author {show(username)}.")
            return
        owner_gh = github_login(base_data.get("github"))
        if not self.author or owner_gh != self.author:
            self.report.needs_review(f"Changes the author {show(username)}, which is linked to "
                                     f"{show(owner_gh) if owner_gh else 'no valid GitHub profile'}.")
        else:
            self.report.owned.append(scope)
        if gh != base_data.get("github"):
            self.report.needs_review(f"Changes the GitHub profile of {show(username)}, which controls theme ownership.")

    # -- entry point ------------------------------------------------------

    def run(self) -> tuple[Report, list[tuple[str, str]]]:
        changes = self.git.changed(self.base, self.head)
        items: dict[str, dict[str, str]] = {}
        authors: dict[str, str] = {}
        repo_files: list[str] = []

        for status, path in changes:
            parts = path.split("/")
            if parts[0] == "items" and len(parts) >= 3:
                items.setdefault(parts[1], {})["/".join(parts[2:])] = status
            elif parts[0] == "authors" and len(parts) == 2 and path.endswith(".json"):
                authors[parts[1][:-5]] = status
            elif MAINTAINER_PATHS.match(path):
                repo_files.append(path)
            elif status == "D":
                self.report.needs_review(f"Deletes {show(path)}.")
            else:
                hint = ""
                if len(parts) == 2 and parts[1] in ITEM_FILES:
                    hint = f" Move it to {show(f'items/{parts[0]}/{parts[1]}')}."
                elif parts[0] == "items":
                    hint = " Theme files go in their own folder: `items/<theme-name>/`."
                elif parts[0] == "authors":
                    hint = " Author files go directly in `authors/` and end in `.json`."
                self.report.error(path, f"File is in the wrong place.{hint}")

        if repo_files:
            listed = ", ".join(show(p) for p in repo_files[:3]) + (f" and {len(repo_files) - 3} more" if len(repo_files) > 3 else "")
            self.report.needs_review(f"Changes repository files: {listed}.")
        for slug in sorted(items):
            self.check_item(slug, items[slug])
        for username in sorted(authors):
            self.check_author(username, authors[username])

        if not self.author:
            self.report.needs_review("No PR author was given, so ownership could not be checked.")
        return self.report, changes


# --------------------------------------------------------------------------
# Link check (optional, needs network)
# --------------------------------------------------------------------------

NO_SUCH_HOST = "the domain does not exist"


class LinkError(Exception):
    pass


def require_public_host(url: str) -> None:
    """Refuse links that resolve to private addresses, so the check cannot probe the runner's network."""
    host = urllib.parse.urlsplit(url).hostname
    if not host:
        raise LinkError("no host")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise LinkError(NO_SUCH_HOST) from None
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise LinkError("it points to a private network address")


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme not in ("http", "https"):
            raise LinkError("it redirects to a non-web address")
        require_public_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_status(url: str, timeout: float = LINK_TIMEOUT) -> tuple[int | None, str]:
    """(HTTP status, reason) after redirects; status is None when there was no HTTP answer."""
    opener = urllib.request.build_opener(_PublicRedirects)
    for method in ("HEAD", "GET"):
        headers = {"User-Agent": USER_AGENT}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        try:
            require_public_host(url)
            with opener.open(urllib.request.Request(url, method=method, headers=headers), timeout=timeout) as resp:
                return resp.status, ""
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (400, 403, 405, 501):
                continue  # some servers refuse HEAD; ask again with GET
            return exc.code, str(exc.reason)
        except LinkError as exc:
            return None, str(exc)
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, LinkError):
                return None, str(exc.reason)
            if isinstance(exc.reason, socket.gaierror):
                return None, NO_SUCH_HOST
            return None, str(exc.reason)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            return None, str(exc) or type(exc).__name__
    return None, "no answer"


def check_links(report: Report, fetch=fetch_status) -> None:
    """Open every new or changed link. Dead download/information links are errors."""
    results: dict[str, tuple[int | None, str]] = {}
    for scope, key, url in report.links[:MAX_LINKS]:
        if url not in results:
            results[url] = fetch(url)
        status, reason = results[url]
        if status is not None and status < 400:
            continue
        dead = status in (404, 410) or reason == NO_SUCH_HOST
        if dead:
            what = f"it returns {status} {reason}".rstrip() if status else reason
            fix = ("Make sure the file exists, for example a file attached to a published GitHub release, "
                   "or `https://github.com/<user>/<repo>/archive/refs/tags/<version>.zip`."
                   if key in DOWNLOAD_FIELDS else "Make sure the page exists and is public.")
            (report.error if key in BLOCKING_LINK_FIELDS else report.warn)(
                scope, f"`{key}` is a broken link ({what}): {show(url, 100)}. {fix}")
        else:
            what = f"it returned {status} {reason}".rstrip() if status else reason
            report.warn(scope, f"`{key}` could not be confirmed ({what}): {show(url, 100)}. "
                               "Please make sure it opens in a browser.")
    if len(report.links) > MAX_LINKS:
        report.needs_review(f"Changes {len(report.links)} links; only the first {MAX_LINKS} were opened.")


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def render(report: Report, eligible: bool, has_changes: bool, author: str | None = None) -> str:
    lines = [MARKER]
    who = f"@{author}" if author and GITHUB_LOGIN.match(author) else "Thanks"
    errors = [(scope, msg) for scope in sorted(report.errors) for msg in report.errors[scope]]

    verdict = report.verdict(has_changes)
    if not has_changes:
        lines += ["## 👎 Not ready to merge", "", "This PR has no changes compared to `master`."]
    elif errors:
        n = len(errors)
        lines += [f"## 👎 Not ready to merge: {n} thing{'s' if n != 1 else ''} to fix", "",
                  f"{who}, thanks for the PR! Please fix {'this' if n == 1 else 'these'} and push again "
                  "to the same branch; this comment updates automatically.", ""]
        lines.extend(f"{i}. **{show(scope, 120)}**: {msg}" for i, (scope, msg) in enumerate(errors, 1))
    elif verdict == "review":
        lines += ["## 👍 Listing OK, waiting for a maintainer review", "",
                  f"{who}, thanks for the PR! The files are correct and themes.bludit.com can show this change "
                  "(see the preview below). A maintainer still needs to check the points below before merging; "
                  "you don't need to do anything unless they ask.", "",
                  "**For the maintainer**"]
        lines.extend(f"- [ ] {reason}" for reason in report.manual)
    else:
        lines += ["## 👍 Ready to merge", "",
                  "All checks passed, and themes.bludit.com can show this change (see the preview below). "
                  "Nothing needs a closer look."]
        if eligible:
            lines.append("Low risk: the PR author owns every theme and author file it changes.")
    lines.append("")

    if report.warnings:
        lines += ["**Suggestions** (optional, they don't block the merge)", ""]
        lines.extend(f"- ⚠️ **{show(scope, 120)}**: {msg}"
                     for scope in sorted(report.warnings) for msg in report.warnings[scope])
        lines.append("")

    if errors and report.manual:
        lines.append("**For the maintainer**, once the problems above are fixed")
        lines.extend(f"- {reason}" for reason in report.manual)
        lines.append("")

    for slug, rows in sorted(report.previews.items()):
        lines.append(f"<details><summary>Preview of <code>{html.escape(slug)}</code> on themes.bludit.com</summary>")
        lines += ["", "| | |", "|---|---|"]
        lines.extend(f"| {label} | {value.replace('|', '&#124;')} |" for label, value in rows)
        lines += ["", "</details>", ""]

    lines.append("<sub>Rules: see the README, section *How to add a theme*. "
                 "Run the same check locally with "
                 "`python3 .github/scripts/validate_pr.py --base origin/master --head HEAD --author <your-github-login>`.</sub>")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=".", help="path to the git repository (default: current directory)")
    parser.add_argument("--base", required=True, help="trusted base revision, e.g. origin/master")
    parser.add_argument("--head", required=True, help="PR head revision")
    parser.add_argument("--author", help="GitHub login of the PR author (enables the ownership check)")
    parser.add_argument("--report-md", help="write the Markdown report to this file")
    parser.add_argument("--github-output", help="append ok=/verdict=/eligible= to this file (GitHub Actions $GITHUB_OUTPUT)")
    parser.add_argument("--check-links", action="store_true", help="open new and changed links (needs network)")
    parser.add_argument("--today", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    git = Git(args.repo)
    base = git.resolve(args.base)
    head = git.resolve(args.head)
    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()

    validator = Validator(git, base, head, args.author, today)
    report, changes = validator.run()
    if args.check_links:
        check_links(report)
    has_changes = bool(changes)
    eligible = report.eligible(has_changes)
    verdict = report.verdict(has_changes)
    markdown = render(report, eligible, has_changes, args.author)

    if args.report_md:
        with open(args.report_md, "w", encoding="utf-8") as fh:
            fh.write(markdown)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"ok={'true' if report.ok else 'false'}\n")
            fh.write(f"verdict={verdict}\n")
            fh.write(f"eligible={'true' if eligible else 'false'}\n")
    sys.stdout.write(markdown)
    return 1 if verdict == "changes" else 0


if __name__ == "__main__":
    sys.exit(main())
