"""Fleet records shared by the loader, scan, and report."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    STUB = "stub"
    LIVE = "live"
    UNKNOWN = "unknown"


class DiffKind(StrEnum):
    CONTENT = "content"
    CONFIG = "config"


class CheckStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    DONE = "done"
    INFO = "info"


class FleetError(Exception):
    """Configuration or adapter error a person can fix without a traceback."""


@dataclass(frozen=True)
class Hub:
    repo: str
    branch: str
    role: str


@dataclass(frozen=True)
class Policy:
    stale_commit_days: int
    min_content_files: int


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    mergeable: bool | None
    checks: str
    draft: bool

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "mergeable": self.mergeable,
            "checks": self.checks,
            "draft": self.draft,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PullRequest:
        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            mergeable=data.get("mergeable"),
            checks=str(data["checks"]),
            draft=bool(data["draft"]),
        )


@dataclass(frozen=True)
class HostingerObservation:
    title: str
    body_excerpt: str
    is_default_template: bool
    fingerprint: str
    php_version: str | None
    ssl: bool | None
    document_root: str | None
    deployed_sha: str | None
    last_deploy_at: str | None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "body_excerpt": self.body_excerpt,
            "is_default_template": self.is_default_template,
            "fingerprint": self.fingerprint,
            "php_version": self.php_version,
            "ssl": self.ssl,
            "document_root": self.document_root,
            "deployed_sha": self.deployed_sha,
            "last_deploy_at": self.last_deploy_at,
        }


@dataclass(frozen=True)
class GithubObservation:
    repo: str
    branch: str
    head_sha: str | None
    head_subject: str | None
    head_at: str | None
    author: str | None
    content_files: tuple[str, ...]
    open_prs: tuple[PullRequest, ...]

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "branch": self.branch,
            "head_sha": self.head_sha,
            "head_subject": self.head_subject,
            "head_at": self.head_at,
            "author": self.author,
            "content_files": list(self.content_files),
            "open_prs": [pr.to_dict() for pr in self.open_prs],
        }


@dataclass(frozen=True)
class Observation:
    hostinger: HostingerObservation | None
    github: GithubObservation | None


@dataclass(frozen=True)
class SiteSpec:
    slug: str
    domain: str
    name: str
    bot: str
    github_repo: str | None
    brand_markers: tuple[str, ...]
    php_version: str | None
    ssl: bool | None
    document_root: str | None


@dataclass(frozen=True)
class Fleet:
    hub: Hub
    policy: Policy
    sites: tuple[SiteSpec, ...]
    observations: dict[str, Observation]
    path: str


@dataclass(frozen=True)
class Classification:
    kind: Kind
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Diff:
    kind: DiffKind
    field: str
    summary: str
    deployed: str
    expected: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "field": self.field,
            "summary": self.summary,
            "deployed": self.deployed,
            "expected": self.expected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Diff:
        return cls(
            kind=DiffKind(data["kind"]),
            field=str(data["field"]),
            summary=str(data["summary"]),
            deployed=str(data["deployed"]),
            expected=str(data["expected"]),
        )


@dataclass(frozen=True)
class Check:
    id: str
    status: CheckStatus
    text: str

    def to_dict(self) -> dict:
        return {"id": self.id, "status": self.status.value, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict) -> Check:
        return cls(id=str(data["id"]), status=CheckStatus(data["status"]), text=str(data["text"]))


@dataclass(frozen=True)
class SiteCard:
    slug: str
    domain: str
    name: str
    bot: str
    github_repo: str | None
    kind: Kind
    reasons: tuple[str, ...]
    diffs: tuple[Diff, ...]
    checks: tuple[Check, ...]
    head_sha: str | None
    head_subject: str | None
    head_at: str | None
    author: str | None
    deployed_sha: str | None
    last_deploy_at: str | None
    open_prs: tuple[PullRequest, ...]

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "domain": self.domain,
            "name": self.name,
            "bot": self.bot,
            "github_repo": self.github_repo,
            "kind": self.kind.value,
            "reasons": list(self.reasons),
            "diffs": [diff.to_dict() for diff in self.diffs],
            "checks": [check.to_dict() for check in self.checks],
            "head_sha": self.head_sha,
            "head_subject": self.head_subject,
            "head_at": self.head_at,
            "author": self.author,
            "deployed_sha": self.deployed_sha,
            "last_deploy_at": self.last_deploy_at,
            "open_prs": [pr.to_dict() for pr in self.open_prs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> SiteCard:
        repo = data.get("github_repo")
        return cls(
            slug=str(data["slug"]),
            domain=str(data["domain"]),
            name=str(data["name"]),
            bot=str(data["bot"]),
            github_repo=str(repo) if repo else None,
            kind=Kind(data["kind"]),
            reasons=tuple(str(item) for item in data.get("reasons", [])),
            diffs=tuple(Diff.from_dict(item) for item in data.get("diffs", [])),
            checks=tuple(Check.from_dict(item) for item in data.get("checks", [])),
            head_sha=data.get("head_sha"),
            head_subject=data.get("head_subject"),
            head_at=data.get("head_at"),
            author=data.get("author"),
            deployed_sha=data.get("deployed_sha"),
            last_deploy_at=data.get("last_deploy_at"),
            open_prs=tuple(PullRequest.from_dict(item) for item in data.get("open_prs", [])),
        )


@dataclass(frozen=True)
class Summary:
    sites: int
    live: int
    stub: int
    unknown: int
    content_diffs: int
    config_diffs: int
    merge_ready: int

    def to_dict(self) -> dict:
        return {
            "sites": self.sites,
            "live": self.live,
            "stub": self.stub,
            "unknown": self.unknown,
            "content_diffs": self.content_diffs,
            "config_diffs": self.config_diffs,
            "merge_ready": self.merge_ready,
        }


@dataclass(frozen=True)
class ScanReport:
    schema: int
    scanned_at: str
    source: str
    fleet: str
    hub_repo: str
    hub_branch: str
    summary: Summary
    cards: tuple[SiteCard, ...]

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "scanned_at": self.scanned_at,
            "source": self.source,
            "fleet": self.fleet,
            "hub": {"repo": self.hub_repo, "branch": self.hub_branch},
            "summary": self.summary.to_dict(),
            "sites": [card.to_dict() for card in self.cards],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ScanReport:
        if data.get("schema") != 1:
            raise FleetError("scan JSON schema must be 1")
        hub = data.get("hub") or {}
        summary = data.get("summary") or {}
        try:
            cards = tuple(SiteCard.from_dict(item) for item in data["sites"])
            counted = Summary(
                sites=int(summary["sites"]),
                live=int(summary["live"]),
                stub=int(summary["stub"]),
                unknown=int(summary["unknown"]),
                content_diffs=int(summary["content_diffs"]),
                config_diffs=int(summary["config_diffs"]),
                merge_ready=int(summary["merge_ready"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FleetError(f"scan JSON is missing fields: {exc}") from exc
        return cls(
            schema=1,
            scanned_at=str(data.get("scanned_at", "")),
            source=str(data.get("source", "")),
            fleet=str(data.get("fleet", "")),
            hub_repo=str(hub.get("repo", "")),
            hub_branch=str(hub.get("branch", "")),
            summary=counted,
            cards=cards,
        )
