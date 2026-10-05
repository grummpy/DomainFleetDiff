"""Turn a fleet plus observations into sorted site cards."""

from __future__ import annotations

from datetime import datetime

from domain_fleet.checklist import build_checklist
from domain_fleet.classify import classify_site
from domain_fleet.drift import diff_site
from domain_fleet.models import (
    DiffKind,
    Fleet,
    Kind,
    Observation,
    ScanReport,
    SiteCard,
    Summary,
)
from domain_fleet.signals import format_time

_KIND_RANK = {Kind.STUB: 0, Kind.UNKNOWN: 1, Kind.LIVE: 2}


def scan_fleet(
    fleet: Fleet,
    observations: dict[str, Observation],
    *,
    source: str,
    now: datetime,
) -> ScanReport:
    cards: list[SiteCard] = []
    for site in fleet.sites:
        observation = observations.get(site.slug, Observation(None, None))
        classification = classify_site(
            site, observation, min_content_files=fleet.policy.min_content_files
        )
        diffs = diff_site(site, observation, min_content_files=fleet.policy.min_content_files)
        checks = build_checklist(
            site,
            observation,
            classification,
            diffs,
            hub_repo=fleet.hub.repo,
            stale_commit_days=fleet.policy.stale_commit_days,
            min_content_files=fleet.policy.min_content_files,
            now=now,
        )
        github = observation.github
        page = observation.hostinger
        cards.append(
            SiteCard(
                slug=site.slug,
                domain=site.domain,
                name=site.name,
                bot=site.bot,
                github_repo=site.github_repo,
                kind=classification.kind,
                reasons=classification.reasons,
                diffs=diffs,
                checks=checks,
                head_sha=github.head_sha if github else None,
                head_subject=github.head_subject if github else None,
                head_at=github.head_at if github else None,
                author=github.author if github else None,
                deployed_sha=page.deployed_sha if page else None,
                last_deploy_at=page.last_deploy_at if page else None,
                open_prs=github.open_prs if github else (),
            )
        )

    cards.sort(key=lambda card: (_KIND_RANK[card.kind], 0 if card.diffs else 1, card.domain))
    ordered = tuple(cards)
    return ScanReport(
        schema=1,
        scanned_at=format_time(now),
        source=source,
        fleet=fleet.path,
        hub_repo=fleet.hub.repo,
        hub_branch=fleet.hub.branch,
        summary=_summarize(ordered),
        cards=ordered,
    )


def _summarize(cards: tuple[SiteCard, ...]) -> Summary:
    return Summary(
        sites=len(cards),
        live=sum(1 for card in cards if card.kind == Kind.LIVE),
        stub=sum(1 for card in cards if card.kind == Kind.STUB),
        unknown=sum(1 for card in cards if card.kind == Kind.UNKNOWN),
        content_diffs=sum(1 for card in cards for diff in card.diffs if diff.kind == DiffKind.CONTENT),
        config_diffs=sum(1 for card in cards for diff in card.diffs if diff.kind == DiffKind.CONFIG),
        merge_ready=sum(1 for card in cards for check in card.checks if check.status.value == "ready"),
    )
