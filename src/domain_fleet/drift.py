"""Content and config drift between the hub, the repo HEAD, and Hostinger."""

from __future__ import annotations

from domain_fleet.models import Diff, DiffKind, Observation, SiteSpec
from domain_fleet.signals import deployed_stub_reasons, is_real_repo, short_sha


def diff_site(
    site: SiteSpec,
    observation: Observation,
    *,
    min_content_files: int,
) -> tuple[Diff, ...]:
    diffs: list[Diff] = []
    page = observation.hostinger
    github = observation.github
    content = _content_diff(page, github, min_content_files)
    if content is not None:
        diffs.append(content)
    if page is not None:
        diffs.extend(_config_diffs(site, page))
    return tuple(diffs)


def _content_diff(page, github, min_content_files: int) -> Diff | None:
    if (
        page is not None
        and github is not None
        and page.deployed_sha
        and github.head_sha
        and page.deployed_sha != github.head_sha
    ):
        return Diff(
            kind=DiffKind.CONTENT,
            field="sha",
            summary=(
                f"deployed {short_sha(page.deployed_sha)} != repo {short_sha(github.head_sha)}"
            ),
            deployed=page.deployed_sha,
            expected=github.head_sha,
        )
    if page is not None and deployed_stub_reasons(page) and is_real_repo(github, min_content_files):
        expected = github.head_sha or ""
        return Diff(
            kind=DiffKind.CONTENT,
            field="unpublished",
            summary=(
                "Hostinger is still the default placeholder; "
                f"repo HEAD {short_sha(expected) if expected else 'unknown'} has a real build"
            ),
            deployed="default-template",
            expected=expected,
        )
    return None


def _config_diffs(site: SiteSpec, page) -> list[Diff]:
    found: list[Diff] = []
    pairs = (
        ("php_version", site.php_version, page.php_version),
        ("ssl", _bool_text(site.ssl), _bool_text(page.ssl)),
        ("document_root", site.document_root, page.document_root),
    )
    for field, expected, deployed in pairs:
        if expected is None or deployed is None or expected == deployed:
            continue
        found.append(
            Diff(
                kind=DiffKind.CONFIG,
                field=field,
                summary=f"{field} deployed {deployed} != hub {expected}",
                deployed=str(deployed),
                expected=str(expected),
            )
        )
    return found


def _bool_text(value: bool | None) -> str | None:
    if value is None:
        return None
    return "true" if value else "false"
