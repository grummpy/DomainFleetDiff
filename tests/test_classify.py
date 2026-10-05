import pytest

from domain_fleet.classify import classify_site
from domain_fleet.models import GithubObservation, HostingerObservation, Observation, SiteSpec


def _site(**overrides) -> SiteSpec:
    data = dict(
        slug="example",
        domain="example.com",
        name="Example",
        bot="example-bot",
        github_repo="grummpy/example",
        brand_markers=("Example",),
        php_version="8.2",
        ssl=True,
        document_root="public_html",
    )
    data.update(overrides)
    return SiteSpec(**data)


def _page(**overrides) -> HostingerObservation:
    data = dict(
        title="Example | Real build",
        body_excerpt="Example ships a real homepage with several sections of copy.",
        is_default_template=False,
        fingerprint="custom",
        php_version="8.2",
        ssl=True,
        document_root="public_html",
        deployed_sha="abc",
        last_deploy_at="2026-09-01T00:00:00Z",
    )
    data.update(overrides)
    return HostingerObservation(**data)


def _github(**overrides) -> GithubObservation:
    data = dict(
        repo="grummpy/example",
        branch="main",
        head_sha="abc",
        head_subject="Publish the homepage",
        head_at="2026-09-01T00:00:00Z",
        author="example-bot",
        content_files=("index.html", "about.html"),
        open_prs=(),
    )
    data.update(overrides)
    return GithubObservation(**data)


def test_default_template_stays_stub_when_the_repo_is_real():
    result = classify_site(
        _site(),
        Observation(_page(title="Coming Soon", is_default_template=True, fingerprint="default"), _github()),
        min_content_files=2,
    )
    assert result.kind.value == "stub"
    assert any("real build" in reason for reason in result.reasons)


def test_brand_on_a_placeholder_does_not_upgrade_it():
    result = classify_site(
        _site(),
        Observation(
            _page(
                title="Coming Soon",
                body_excerpt="Example will live here. You have successfully created a website with Hostinger.",
                is_default_template=True,
                fingerprint="default",
            ),
            None,
        ),
        min_content_files=2,
    )
    assert result.kind.value == "stub"


def test_placeholder_commit_is_stub_without_a_deploy():
    result = classify_site(
        _site(),
        Observation(
            None,
            _github(head_subject="Create Hostinger website", content_files=("index.html",)),
        ),
        min_content_files=2,
    )
    assert result.kind.value == "stub"
    assert "placeholder commit" in result.reasons[0]


def test_missing_repo_is_stub():
    result = classify_site(
        _site(github_repo=None),
        Observation(None, None),
        min_content_files=2,
    )
    assert result.kind.value == "stub"
    assert "no GitHub repo" in result.reasons[0]


def test_linked_repo_without_observation_is_unknown():
    result = classify_site(_site(), Observation(None, None), min_content_files=2)
    assert result.kind.value == "unknown"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Parked Domain", "stub"),
        ("Under Construction", "stub"),
        ("Future home of Example", "stub"),
        ("Example | Shop", "live"),
    ],
)
def test_title_catalog(title, expected):
    fingerprint = "default" if expected == "stub" else "custom"
    default = expected == "stub"
    result = classify_site(
        _site(),
        Observation(_page(title=title, is_default_template=default, fingerprint=fingerprint), _github()),
        min_content_files=2,
    )
    assert result.kind.value == expected
