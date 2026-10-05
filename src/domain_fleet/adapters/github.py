"""Map GitHub REST payloads into a repo observation.

The functions are pure. A bot that already has a token performs the HTTP
calls and passes the JSON here. This module does not read ``GITHUB_TOKEN``
and does not open a socket.
"""

from __future__ import annotations

from typing import Protocol

from domain_fleet.models import FleetError, GithubObservation, PullRequest
from domain_fleet.signals import commit_subject, content_files_from_tree


class GitHubTransport(Protocol):
    """Return a normalized repo snapshot for ``owner/name``.

    See ``normalize_repo_snapshot`` for the mapping from REST JSON.
    """

    def fetch_repo(self, full_name: str) -> dict:
        """Normalized snapshot. Implementations perform their own HTTP."""


def normalize_repo_snapshot(
    *,
    full_name: str,
    branch: str,
    commit: dict,
    tree: dict,
    pulls: list[dict],
    checks_by_number: dict[int, str],
) -> dict:
    """Fold the four REST reads a bot already made into one snapshot.

    ``commit`` is one object from ``GET /repos/{owner}/{repo}/commits``.
    ``tree`` is ``GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1``.
    ``pulls`` is ``GET /repos/{owner}/{repo}/pulls?state=open``.
    ``checks_by_number`` is computed by the caller from check-runs
    (``passing``, ``failing``, or ``pending``). GitHub does not put that
    summary on the pull object itself.
    """
    commit_body = commit.get("commit") or {}
    message = str((commit_body.get("message") or ""))
    author_block = commit.get("author") or {}
    commit_author = (commit_body.get("author") or {})
    normalized_pulls = [
        normalize_pull(pull, checks=checks_by_number.get(int(pull["number"]), "pending"))
        for pull in pulls
    ]
    return {
        "repo": full_name,
        "branch": branch,
        "head_sha": commit.get("sha"),
        "head_subject": commit_subject(message),
        "head_at": commit_author.get("date"),
        "author": author_block.get("login"),
        "content_files": content_files_from_tree(tree),
        "open_prs": normalized_pulls,
    }


def normalize_pull(pull: dict, *, checks: str) -> dict:
    if checks not in {"passing", "failing", "pending"}:
        raise FleetError(f"checks for PR {pull.get('number')} must be passing, failing, or pending")
    mergeable = pull.get("mergeable")
    if mergeable is not None and not isinstance(mergeable, bool):
        raise FleetError(f"PR {pull.get('number')} mergeable must be true, false, or null")
    return {
        "number": int(pull["number"]),
        "title": str(pull.get("title") or ""),
        "mergeable": mergeable,
        "checks": checks,
        "draft": bool(pull.get("draft", False)),
    }


def github_from_normalized(payload: dict) -> GithubObservation:
    pulls = tuple(
        PullRequest(
            number=int(item["number"]),
            title=str(item["title"]),
            mergeable=item.get("mergeable"),
            checks=str(item["checks"]),
            draft=bool(item["draft"]),
        )
        for item in payload.get("open_prs", [])
    )
    files = payload.get("content_files") or []
    return GithubObservation(
        repo=str(payload["repo"]),
        branch=str(payload.get("branch") or "main"),
        head_sha=payload.get("head_sha"),
        head_subject=payload.get("head_subject"),
        head_at=payload.get("head_at"),
        author=payload.get("author"),
        content_files=tuple(str(path) for path in files),
        open_prs=pulls,
    )
