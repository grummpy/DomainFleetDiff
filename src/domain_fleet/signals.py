"""Stub catalogs and pure homepage signals.

The catalogs are the product rules. Classification and ``signals_from_html``
both use these tuples, so a homepage a bot already downloaded is judged the
same way as a fixture observation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser

from domain_fleet.models import GithubObservation, HostingerObservation

# Substrings, compared case-insensitively against the page title only.
STUB_TITLE_MARKERS: tuple[str, ...] = (
    "coming soon",
    "parked domain",
    "domain parked",
    "under construction",
    "default web site",
    "this site is hosted",
    "future home of",
)

# Substrings compared against the visible body, not the title.
# Kept specific so a real page that mentions "coming soon" in a sentence
# is not marked stub from the body alone.
STUB_BODY_MARKERS: tuple[str, ...] = (
    "hostinger-coming-soon",
    "you have successfully created a website with hostinger",
    "parked free, courtesy of",
    "hpanel-default",
    "default-website-template",
)

# Full first-line subjects, compared case-insensitively after stripping.
# A match counts only when the repo also has fewer than min_content_files.
PLACEHOLDER_COMMIT_SUBJECTS: tuple[str, ...] = (
    "initial commit",
    "create hostinger website",
    "add default index",
    "hostinger default page",
)

CONTENT_SUFFIXES: tuple[str, ...] = (
    ".html",
    ".htm",
    ".css",
    ".js",
    ".md",
    ".php",
    ".txt",
)


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short_sha(value: str | None) -> str:
    if not value:
        return "unknown"
    return value[:7]


def first_marker(text: str, markers: tuple[str, ...]) -> str | None:
    haystack = text.casefold()
    for marker in markers:
        if marker.casefold() in haystack:
            return marker
    return None


def first_brand(markers: tuple[str, ...], *parts: str) -> str | None:
    haystack = "\n".join(parts).casefold()
    for marker in markers:
        token = marker.strip()
        if token and token.casefold() in haystack:
            return token
    return None


def commit_subject(message: str) -> str:
    lines = message.splitlines() or [""]
    return lines[0].strip()


def is_placeholder_subject(subject: str | None) -> bool:
    if not subject:
        return False
    return subject.strip().casefold() in PLACEHOLDER_COMMIT_SUBJECTS


def is_placeholder_repo(github: GithubObservation, min_content_files: int) -> bool:
    if not is_placeholder_subject(github.head_subject):
        return False
    return len(github.content_files) < min_content_files


def is_real_repo(github: GithubObservation | None, min_content_files: int) -> bool:
    if github is None or is_placeholder_repo(github, min_content_files):
        return False
    return len(github.content_files) >= min_content_files


def deployed_stub_reasons(page: HostingerObservation | None) -> list[str]:
    if page is None:
        return []
    reasons: list[str] = []
    if page.is_default_template:
        reasons.append("Hostinger marked the page as the default template")
    title_hit = first_marker(page.title, STUB_TITLE_MARKERS)
    if title_hit:
        reasons.append(f"title matches stub catalog ({title_hit})")
    body_hit = first_marker(page.body_excerpt, STUB_BODY_MARKERS)
    if body_hit:
        reasons.append(f"body matches stub catalog ({body_hit})")
    # signals_from_html sets both the template flag and fingerprint together.
    # Repeating that as two reasons hides the title or body phrase that matched.
    if page.fingerprint == "default" and not page.is_default_template:
        reasons.append("content fingerprint is the Hostinger default")
    return reasons


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._skip:
            return
        self.body_parts.append(data)


def _collapse(text: str) -> str:
    return " ".join(text.split())


def signals_from_html(page_html: str) -> dict[str, object]:
    """Read title, excerpt, and stub flags from a homepage the caller already has.

    This does not fetch. Title markers are applied to ``<title>`` only. Body
    markers are applied to visible text. A long non-matching page is ``custom``.
    """
    parser = _VisibleText()
    parser.feed(page_html)
    parser.close()
    title = _collapse("".join(parser.title_parts))
    excerpt = _collapse("".join(parser.body_parts))[:400]
    title_hit = first_marker(title, STUB_TITLE_MARKERS)
    body_hit = first_marker(excerpt, STUB_BODY_MARKERS)
    is_default = bool(title_hit or body_hit)
    if is_default:
        fingerprint = "default"
    elif len(excerpt) >= 80:
        fingerprint = "custom"
    else:
        fingerprint = "unknown"
    return {
        "title": title,
        "body_excerpt": excerpt,
        "is_default_template": is_default,
        "fingerprint": fingerprint,
    }


def content_files_from_tree(tree: dict) -> list[str]:
    """Keep page-like blobs from a GitHub git tree payload.

    Dot-paths and non-blobs are dropped. ``tree`` is the JSON object from
    ``GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1``.
    """
    files: list[str] = []
    for node in tree.get("tree", []):
        if node.get("type") != "blob":
            continue
        path = str(node.get("path", ""))
        if not path or path.startswith(".") or "/." in path:
            continue
        lowered = path.casefold()
        if lowered.endswith(CONTENT_SUFFIXES):
            files.append(path)
    return files
