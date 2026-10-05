"""Decide stub vs live for one site.

Deployed-stub wins. A real repository does not make a Hostinger placeholder
page live — that gap is a content diff and a deploy checklist row instead.
"""

from __future__ import annotations

from domain_fleet.models import Classification, Kind, Observation, SiteSpec
from domain_fleet.signals import (
    deployed_stub_reasons,
    first_brand,
    is_placeholder_repo,
    is_real_repo,
)


def classify_site(
    site: SiteSpec,
    observation: Observation,
    *,
    min_content_files: int,
) -> Classification:
    page = observation.hostinger
    github = observation.github
    deployed = deployed_stub_reasons(page)
    if deployed:
        reasons = list(deployed)
        if is_real_repo(github, min_content_files):
            reasons.append("repo has a real build, but the deployed page is still a placeholder")
        return Classification(Kind.STUB, tuple(reasons))

    live = _live_reasons(site, observation, min_content_files)
    if live:
        return Classification(Kind.LIVE, tuple(live))

    repo_stub = _repo_stub_reasons(site, observation, min_content_files)
    if repo_stub:
        return Classification(Kind.STUB, tuple(repo_stub))

    return Classification(Kind.UNKNOWN, ("not enough signals to call the site live or stub",))


def _live_reasons(
    site: SiteSpec,
    observation: Observation,
    min_content_files: int,
) -> list[str]:
    page = observation.hostinger
    github = observation.github
    real = is_real_repo(github, min_content_files)
    if page is not None:
        reasons: list[str] = []
        marker = first_brand(site.brand_markers, page.title, page.body_excerpt)
        if marker:
            reasons.append(f"deployed page matches brand marker {marker!r}")
        if page.fingerprint == "custom":
            reasons.append("deployed fingerprint is custom")
        if real and not reasons:
            reasons.append("deployed page is not a placeholder and the repo has a real build")
        return reasons
    # A repository observation describes source code, not a deployment. Do
    # not promote it to ``live`` when no homepage/deployment observation was
    # collected: fixture-only data is not an operational verification.
    return []


def _repo_stub_reasons(
    site: SiteSpec,
    observation: Observation,
    min_content_files: int,
) -> list[str]:
    github = observation.github
    reasons: list[str] = []
    if not site.github_repo and github is None:
        reasons.append("no GitHub repo is linked in the hub")
    if github is not None and is_placeholder_repo(github, min_content_files):
        count = len(github.content_files)
        noun = "file" if count == 1 else "files"
        reasons.append(
            "repo history is only a placeholder commit "
            f"({github.head_subject!r}) with {count} content {noun}"
        )
    return reasons
