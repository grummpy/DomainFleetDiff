"""Load a hub fleet manifest from TOML.

The manifest is meant to live in the hub repo (the sample hub is
``grummpy/my_domains``). Observation tables are optional so a later live
transport can fill them. The fixture source requires those tables.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from domain_fleet.models import (
    Fleet,
    FleetError,
    GithubObservation,
    HostingerObservation,
    Hub,
    Observation,
    Policy,
    PullRequest,
    SiteSpec,
)

_TOP_KEYS = {"schema", "hub", "policy", "sites"}
_HUB_KEYS = {"repo", "branch", "role"}
_POLICY_KEYS = {"stale_commit_days", "min_content_files"}
_SITE_KEYS = {
    "slug",
    "domain",
    "name",
    "bot",
    "github_repo",
    "brand_markers",
    "php_version",
    "ssl",
    "document_root",
    "hostinger",
    "github",
}
_HOSTINGER_KEYS = {
    "title",
    "body_excerpt",
    "is_default_template",
    "fingerprint",
    "php_version",
    "ssl",
    "document_root",
    "deployed_sha",
    "last_deploy_at",
}
_GITHUB_KEYS = {
    "branch",
    "head_sha",
    "head_subject",
    "head_at",
    "author",
    "content_files",
    "pulls",
}
_PULL_KEYS = {"number", "title", "mergeable", "checks", "draft"}
_FINGERPRINTS = {"custom", "default", "unknown"}
_CHECKS = {"passing", "failing", "pending"}


def sample_fleet_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "sample_fleet.toml"


def load_fleet(path: Path) -> Fleet:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FleetError(f"cannot read fleet file {path}: {exc.strerror}") from exc
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise FleetError(f"{path}: invalid TOML ({exc})") from exc
    if not isinstance(data, dict):
        raise FleetError(f"{path}: fleet file must be a TOML table")
    _unknown(data, _TOP_KEYS, f"{path}")
    if data.get("schema") != 1:
        raise FleetError(f"{path}: schema must be 1")

    hub_raw = _table(data.get("hub"), f"{path}: [hub]")
    _unknown(hub_raw, _HUB_KEYS, f"{path}: [hub]")
    hub = Hub(
        repo=_repo_name(_require(hub_raw, "repo", f"{path}: [hub]"), f"{path}: hub.repo"),
        branch=_nonempty(hub_raw.get("branch"), f"{path}: hub.branch"),
        role=_nonempty(hub_raw.get("role"), f"{path}: hub.role"),
    )

    policy_raw = _table(data.get("policy"), f"{path}: [policy]")
    _unknown(policy_raw, _POLICY_KEYS, f"{path}: [policy]")
    policy = Policy(
        stale_commit_days=_positive_int(
            policy_raw.get("stale_commit_days"), f"{path}: policy.stale_commit_days"
        ),
        min_content_files=_positive_int(
            policy_raw.get("min_content_files"), f"{path}: policy.min_content_files"
        ),
    )

    sites_raw = data.get("sites")
    if not isinstance(sites_raw, list) or not sites_raw:
        raise FleetError(f"{path}: [[sites]] must list at least one site")

    sites: list[SiteSpec] = []
    observations: dict[str, Observation] = {}
    seen: set[str] = set()
    for index, site_raw in enumerate(sites_raw):
        label = f"{path}: [[sites]] #{index + 1}"
        site_raw = _table(site_raw, label)
        _unknown(site_raw, _SITE_KEYS, label)
        slug = _slug(_require(site_raw, "slug", label))
        if slug in seen:
            raise FleetError(f"{label}: duplicate slug {slug}")
        seen.add(slug)
        label = f"{path}: site {slug}"
        domain = _domain(_require(site_raw, "domain", label))
        github_repo_raw = site_raw.get("github_repo", "")
        if github_repo_raw in ("", None):
            github_repo = None
        else:
            github_repo = _repo_name(github_repo_raw, f"{label}: github_repo")
        spec = SiteSpec(
            slug=slug,
            domain=domain,
            name=_nonempty(site_raw.get("name"), f"{label}: name"),
            bot=_nonempty(site_raw.get("bot"), f"{label}: bot"),
            github_repo=github_repo,
            brand_markers=_str_tuple(site_raw.get("brand_markers", []), f"{label}: brand_markers"),
            php_version=_optional_str(site_raw.get("php_version"), f"{label}: php_version"),
            ssl=_optional_bool(site_raw.get("ssl"), f"{label}: ssl"),
            document_root=_optional_str(site_raw.get("document_root"), f"{label}: document_root"),
        )
        sites.append(spec)
        observations[slug] = Observation(
            hostinger=_hostinger(site_raw.get("hostinger"), label),
            github=_github(site_raw.get("github"), github_repo, label),
        )

    return Fleet(
        hub=hub,
        policy=policy,
        sites=tuple(sites),
        observations=observations,
        path=str(path),
    )


def _hostinger(raw: object, label: str) -> HostingerObservation | None:
    if raw is None:
        return None
    table = _table(raw, f"{label}: [sites.hostinger]")
    _unknown(table, _HOSTINGER_KEYS, f"{label}: [sites.hostinger]")
    fingerprint = _require(table, "fingerprint", f"{label}: hostinger")
    if fingerprint not in _FINGERPRINTS:
        raise FleetError(f"{label}: hostinger.fingerprint must be custom, default, or unknown")
    return HostingerObservation(
        title=_nonempty(table.get("title"), f"{label}: hostinger.title"),
        body_excerpt=str(table.get("body_excerpt", "")),
        is_default_template=_require_bool(
            table.get("is_default_template"), f"{label}: hostinger.is_default_template"
        ),
        fingerprint=str(fingerprint),
        php_version=_optional_str(table.get("php_version"), f"{label}: hostinger.php_version"),
        ssl=_optional_bool(table.get("ssl"), f"{label}: hostinger.ssl"),
        document_root=_optional_str(
            table.get("document_root"), f"{label}: hostinger.document_root"
        ),
        deployed_sha=_optional_str(table.get("deployed_sha"), f"{label}: hostinger.deployed_sha"),
        last_deploy_at=_optional_str(
            table.get("last_deploy_at"), f"{label}: hostinger.last_deploy_at"
        ),
    )


def _github(raw: object, repo: str | None, label: str) -> GithubObservation | None:
    if raw is None:
        return None
    table = _table(raw, f"{label}: [sites.github]")
    _unknown(table, _GITHUB_KEYS, f"{label}: [sites.github]")
    if not repo:
        raise FleetError(f"{label}: [sites.github] is set but github_repo is empty")
    pulls_raw = table.get("pulls", [])
    if not isinstance(pulls_raw, list):
        raise FleetError(f"{label}: github.pulls must be an array")
    pulls = tuple(_pull(item, f"{label}: pull") for item in pulls_raw)
    return GithubObservation(
        repo=repo,
        branch=_nonempty(table.get("branch"), f"{label}: github.branch"),
        head_sha=_optional_str(table.get("head_sha"), f"{label}: github.head_sha"),
        head_subject=_optional_str(table.get("head_subject"), f"{label}: github.head_subject"),
        head_at=_optional_str(table.get("head_at"), f"{label}: github.head_at"),
        author=_optional_str(table.get("author"), f"{label}: github.author"),
        content_files=_str_tuple(table.get("content_files", []), f"{label}: github.content_files"),
        open_prs=pulls,
    )


def _pull(raw: object, label: str) -> PullRequest:
    table = _table(raw, label)
    _unknown(table, _PULL_KEYS, label)
    checks = _require(table, "checks", label)
    if checks not in _CHECKS:
        raise FleetError(f"{label}: checks must be passing, failing, or pending")
    number = table.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise FleetError(f"{label}: number must be a positive integer")
    mergeable = table.get("mergeable")
    if mergeable is not None and not isinstance(mergeable, bool):
        raise FleetError(f"{label}: mergeable must be true, false, or omitted")
    return PullRequest(
        number=number,
        title=_nonempty(table.get("title"), f"{label}: title"),
        mergeable=mergeable,
        checks=str(checks),
        draft=_require_bool(table.get("draft"), f"{label}: draft"),
    )


def _unknown(table: dict, allowed: set[str], label: str) -> None:
    extra = sorted(set(table) - allowed)
    if extra:
        raise FleetError(f"{label}: unknown keys {', '.join(extra)}")


def _table(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise FleetError(f"{label} must be a table")
    return value


def _require(table: dict, key: str, label: str) -> object:
    if key not in table:
        raise FleetError(f"{label}: missing {key}")
    return table[key]


def _nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FleetError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise FleetError(f"{label} must be a string")
    text = value.strip()
    return text or None


def _optional_bool(value: object, label: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise FleetError(f"{label} must be true or false")
    return value


def _require_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise FleetError(f"{label} must be true or false")
    return value


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise FleetError(f"{label} must be a positive integer")
    return value


def _str_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise FleetError(f"{label} must be an array of non-empty strings")
    return tuple(item.strip() for item in value)


def _slug(value: object) -> str:
    if not isinstance(value, str) or not value.islower() or not value.isalnum():
        raise FleetError(f"slug {value!r} must be lowercase letters and digits")
    return value


def _domain(value: object) -> str:
    if not isinstance(value, str) or "." not in value or " " in value:
        raise FleetError(f"domain {value!r} must be a hostname")
    return value.strip()


def _repo_name(value: object, label: str) -> str:
    if not isinstance(value, str) or value.count("/") != 1:
        raise FleetError(f"{label} must look like owner/name")
    owner, name = value.split("/", 1)
    if not owner.strip() or not name.strip() or " " in value:
        raise FleetError(f"{label} must look like owner/name")
    return value.strip()
