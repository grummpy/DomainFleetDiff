import pytest

from domain_fleet.adapters.github import github_from_normalized, normalize_pull, normalize_repo_snapshot
from domain_fleet.adapters.hostinger import hostinger_from_normalized
from domain_fleet.adapters.live import AdapterNotConfigured, LiveFleetSource
from domain_fleet.fleet_load import load_fleet, sample_fleet_path
from domain_fleet.models import FleetError


def test_live_source_refuses_to_run_without_transports():
    with pytest.raises(AdapterNotConfigured, match="GITHUB_TOKEN"):
        LiveFleetSource(None, None)


class _GitHub:
    def fetch_repo(self, full_name: str) -> dict:
        return {
            "repo": full_name,
            "branch": "main",
            "head_sha": "abc123",
            "head_subject": "Publish",
            "head_at": "2026-09-01T00:00:00Z",
            "author": "bot",
            "content_files": ["index.html", "about.html"],
            "open_prs": [],
        }


class _Hostinger:
    def fetch_website(self, domain: str) -> dict:
        return {
            "title": f"{domain} home",
            "body_excerpt": "hello",
            "is_default_template": False,
            "fingerprint": "custom",
            "php_version": "8.2",
            "ssl": True,
            "document_root": "public_html",
            "deployed_sha": "abc123",
        }


def test_live_source_uses_injected_transports_only():
    fleet = load_fleet(sample_fleet_path())
    loaded = LiveFleetSource(_GitHub(), _Hostinger()).load(fleet)
    assert set(loaded) == {site.slug for site in fleet.sites}
    victory = loaded["victorydraw"]
    assert victory.github is None
    assert victory.hostinger is not None
    salty = loaded["saltydogcustoms"]
    assert salty.github is not None
    assert salty.github.repo == "grummpy/saltydogcustoms"
    assert salty.hostinger.title == "saltydogcustoms.com home"


def test_normalize_commit_takes_the_subject_line_and_filters_the_tree():
    snapshot = normalize_repo_snapshot(
        full_name="grummpy/example",
        branch="main",
        commit={
            "sha": "deadbeef",
            "commit": {
                "message": "Publish the homepage\n\nLonger body that is not the subject.",
                "author": {"date": "2026-09-01T00:00:00Z"},
            },
            "author": {"login": "example-bot"},
        },
        tree={
            "tree": [
                {"path": "index.html", "type": "blob"},
                {"path": "README.md", "type": "blob"},
                {"path": ".gitignore", "type": "blob"},
            ]
        },
        pulls=[
            {
                "number": 9,
                "title": "Add a page",
                "draft": False,
                "mergeable": True,
                "html_url": "https://github.com/grummpy/example/pull/9",
            }
        ],
        checks_by_number={9: "passing"},
    )
    observation = github_from_normalized(snapshot)
    assert observation.head_subject == "Publish the homepage"
    assert observation.author == "example-bot"
    assert observation.content_files == ("index.html", "README.md")
    assert observation.open_prs[0].number == 9
    assert observation.open_prs[0].checks == "passing"


def test_null_mergeable_stays_null():
    payload = normalize_pull({"number": 3, "title": "Wait", "draft": False, "mergeable": None}, checks="pending")
    assert payload["mergeable"] is None


def test_bad_fingerprint_is_rejected():
    with pytest.raises(FleetError):
        hostinger_from_normalized(
            {"title": "x", "is_default_template": False, "fingerprint": "parked"}
        )
