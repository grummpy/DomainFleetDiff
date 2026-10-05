"""Merge-ready next steps for one site.

The scan never merges a pull request and never deploys. Rows with status
``ready`` are safe for the owner or that site's bot to do next. ``blocked``
rows explain the gate. ``info`` rows are watch items. ``done`` means observed
deployment metadata matches the observed repository HEAD and hub values.
"""

from __future__ import annotations

from datetime import datetime

from domain_fleet.models import (
    Check,
    CheckStatus,
    Classification,
    Diff,
    DiffKind,
    Kind,
    Observation,
    PullRequest,
    SiteSpec,
)
from domain_fleet.signals import is_placeholder_repo, parse_time, short_sha


def suggested_repo(hub_repo: str, site: SiteSpec) -> str:
    if site.github_repo:
        return site.github_repo
    owner = hub_repo.split("/", 1)[0]
    return f"{owner}/{site.slug}"


def build_checklist(
    site: SiteSpec,
    observation: Observation,
    classification: Classification,
    diffs: tuple[Diff, ...],
    *,
    hub_repo: str,
    stale_commit_days: int,
    min_content_files: int,
    now: datetime,
) -> tuple[Check, ...]:
    checks: list[Check] = []
    github = observation.github
    pr_blocked = False

    if github is not None:
        for pull in github.open_prs:
            status, text = _pull_row(pull)
            if status != CheckStatus.READY:
                pr_blocked = True
            checks.append(Check(id=f"pr-{pull.number}", status=status, text=text))

    content = next((item for item in diffs if item.kind == DiffKind.CONTENT), None)
    if content is not None:
        checks.append(_deploy_row(site, content, pr_blocked=pr_blocked))

    for item in diffs:
        if item.kind == DiffKind.CONFIG:
            checks.append(
                Check(
                    id=f"config-{item.field}",
                    status=CheckStatus.READY,
                    text=_config_text(site, item),
                )
            )

    # Drift deliberately ignores unavailable fields so fixture snapshots can
    # be partial. A lack of a diff is therefore not proof of alignment.
    alignment_gaps = _deployment_alignment_gaps(site, observation)
    if classification.kind == Kind.LIVE and alignment_gaps:
        checks.append(
            Check(
                id="verify-deployment",
                status=CheckStatus.INFO,
                text=(
                    "Deployment alignment is unverified; record "
                    + ", ".join(alignment_gaps)
                    + "."
                ),
            )
        )

    placeholder = github is not None and is_placeholder_repo(github, min_content_files)
    ready_prs = [item for item in checks if item.id.startswith("pr-") and item.status == CheckStatus.READY]

    if not site.github_repo:
        repo_name = suggested_repo(hub_repo, site)
        checks.append(
            Check(
                id="create-repo",
                status=CheckStatus.READY,
                text=(
                    f"Create {repo_name} from the hub site template and register it in {hub_repo}"
                ),
            )
        )
        checks.append(
            Check(
                id="deploy-key",
                status=CheckStatus.READY,
                text=(
                    f"Issue a Hostinger deploy key for bot {site.bot} and store it with the bot, "
                    f"not in {hub_repo}"
                ),
            )
        )
    elif placeholder and not ready_prs and github is not None:
        checks.append(
            Check(
                id="replace-placeholder",
                status=CheckStatus.READY,
                text=(
                    f"Replace the Hostinger placeholder in {site.github_repo} "
                    f"(HEAD {short_sha(github.head_sha)}: {github.head_subject})"
                ),
            )
        )

    if classification.kind == Kind.STUB and placeholder and ready_prs:
        labels = ", ".join("#" + item.id.removeprefix("pr-") for item in ready_prs)
        checks.append(
            Check(
                id="after-merge",
                status=CheckStatus.INFO,
                text=(
                    f"After {labels} merges, rerun the scan and deploy main. "
                    "Hostinger is still serving the default page."
                ),
            )
        )

    if classification.kind == Kind.LIVE and github is not None and github.head_at:
        age_days = (now - parse_time(github.head_at)).days
        if age_days >= stale_commit_days:
            who = github.author or site.bot
            checks.append(
                Check(
                    id="stale-bot",
                    status=CheckStatus.INFO,
                    text=(
                        f"Last commit {github.head_at[:10]} by {who} is {age_days} days old "
                        f"(policy {stale_commit_days}). Confirm {site.bot} is still scheduled."
                    ),
                )
            )

    actionable = {CheckStatus.READY, CheckStatus.BLOCKED, CheckStatus.INFO}
    if (
        classification.kind == Kind.LIVE
        and not diffs
        and not alignment_gaps
        and not any(item.status in actionable for item in checks)
    ):
        sha = short_sha(github.head_sha) if github is not None else "HEAD"
        checks.append(
            Check(
                id="noop",
                status=CheckStatus.DONE,
                text=(
                    f"No action. Observed deployed commit matches observed HEAD {sha} "
                    "and observed configuration matches the hub."
                ),
            )
        )

    if classification.kind == Kind.UNKNOWN and not checks:
        checks.append(
            Check(
                id="gather",
                status=CheckStatus.INFO,
                text=(
                    "Not enough signals. Record a homepage observation and a repo HEAD, then rescan."
                ),
            )
        )

    return tuple(checks)


def _pull_row(pull: PullRequest) -> tuple[CheckStatus, str]:
    title = pull.title
    if pull.draft:
        return CheckStatus.BLOCKED, f'PR #{pull.number} "{title}" is a draft — mark it ready before merge'
    if pull.checks == "failing":
        return (
            CheckStatus.BLOCKED,
            f'PR #{pull.number} "{title}" is blocked — checks are failing',
        )
    if pull.checks == "pending":
        return (
            CheckStatus.BLOCKED,
            f'PR #{pull.number} "{title}" is waiting on checks',
        )
    if pull.mergeable is False:
        return CheckStatus.BLOCKED, f'PR #{pull.number} "{title}" has merge conflicts'
    if pull.mergeable is None:
        return (
            CheckStatus.BLOCKED,
            f'PR #{pull.number} "{title}" — mergeability is unknown; refresh the pull request',
        )
    if pull.checks != "passing":
        return CheckStatus.BLOCKED, f'PR #{pull.number} "{title}" is blocked — checks are {pull.checks}'
    return CheckStatus.READY, f'Merge #{pull.number} "{title}" — checks passing'


def _deploy_row(site: SiteSpec, diff: Diff, *, pr_blocked: bool) -> Check:
    if diff.field == "sha":
        return Check(
            id="verify-deployment-sha",
            status=CheckStatus.INFO,
            text=(
                "Deployment SHA differs from repository HEAD. Ancestry and the intended "
                "release target were not observed; validate them before any deployment action."
            ),
        )
    if pr_blocked:
        return Check(
            id="deploy",
            status=CheckStatus.BLOCKED,
            text=f"Redeploy {site.domain} after main is updated — {diff.summary}",
        )
    if diff.field == "unpublished":
        repo = site.github_repo or site.slug
        sha = short_sha(diff.expected)
        return Check(
            id="deploy",
            status=CheckStatus.READY,
            text=(
                f"Deploy {repo}@{sha} — Hostinger is still the default placeholder "
                "and the repo has a real build"
            ),
        )
    # Content diffs are currently limited to the SHA and unpublished cases.
    # Keep a conservative fallback if another content-diff kind is added.
    return Check(
        id="verify-deployment-content",
        status=CheckStatus.INFO,
        text=f"Verify deployment content before acting: {diff.summary}",
    )


def _deployment_alignment_gaps(site: SiteSpec, observation: Observation) -> list[str]:
    """Return observations still needed before reporting a verified match."""

    page = observation.hostinger
    github = observation.github
    gaps: list[str] = []
    if page is None:
        return ["a Hostinger deployment observation"]
    if github is None:
        gaps.append("a repository HEAD observation")
    else:
        if not page.deployed_sha:
            gaps.append("the deployed commit SHA")
        if not github.head_sha:
            gaps.append("the repository HEAD SHA")
    configured_fields = (
        ("PHP version", site.php_version, page.php_version),
        ("SSL state", site.ssl, page.ssl),
        ("document root", site.document_root, page.document_root),
    )
    for label, expected, observed in configured_fields:
        if expected is not None and observed is None:
            gaps.append(f"the observed {label}")
    return gaps


def _config_text(site: SiteSpec, diff: Diff) -> str:
    if diff.field == "php_version":
        return (
            f"Set Hostinger PHP for {site.domain} from {diff.deployed} to {diff.expected} "
            f"before the next {site.bot} deploy"
        )
    if diff.field == "ssl":
        return (
            f"Align SSL for {site.domain} with the hub "
            f"(deployed {diff.deployed}, hub {diff.expected}) before the next {site.bot} deploy"
        )
    if diff.field == "document_root":
        return (
            f"Align the document root for {site.domain} with the hub "
            f"(deployed {diff.deployed}, hub {diff.expected})"
        )
    return diff.summary
