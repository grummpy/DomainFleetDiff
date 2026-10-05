from datetime import datetime, timezone

from domain_fleet.checklist import build_checklist
from domain_fleet.classify import classify_site
from domain_fleet.drift import diff_site
from domain_fleet.models import GithubObservation, HostingerObservation, Observation, PullRequest, SiteSpec


def _site() -> SiteSpec:
    return SiteSpec(
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


def _page(**overrides) -> HostingerObservation:
    data = dict(
        title="Example | Real build",
        body_excerpt="Example homepage",
        is_default_template=False,
        fingerprint="custom",
        php_version="8.2",
        ssl=True,
        document_root="public_html",
        deployed_sha="aaa111",
        last_deploy_at=None,
    )
    data.update(overrides)
    return HostingerObservation(**data)


def _pull(**overrides) -> PullRequest:
    data = dict(number=4, title="Ship it", mergeable=True, checks="passing", draft=False)
    data.update(overrides)
    return PullRequest(**data)


def _github(**overrides) -> GithubObservation:
    data = dict(
        repo="grummpy/example",
        branch="main",
        head_sha="aaa111",
        head_subject="Publish the homepage",
        head_at="2026-09-01T00:00:00Z",
        author="example-bot",
        content_files=("index.html", "about.html"),
        open_prs=(),
    )
    data.update(overrides)
    return GithubObservation(**data)


def _rows(observation: Observation, site: SiteSpec | None = None):
    spec = site or _site()
    kind = classify_site(spec, observation, min_content_files=2)
    diffs = diff_site(spec, observation, min_content_files=2)
    checks = build_checklist(
        spec,
        observation,
        kind,
        diffs,
        hub_repo="grummpy/my_domains",
        stale_commit_days=90,
        min_content_files=2,
        now=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    return kind, diffs, checks


def test_sha_mismatch_is_a_content_diff_without_an_unsupported_redeploy_claim():
    kind, diffs, checks = _rows(Observation(_page(), _github(head_sha="bbb222")))
    assert kind.kind.value == "live"
    assert diffs[0].kind.value == "content"
    assert diffs[0].field == "sha"
    assert checks[0].id == "verify-deployment-sha"
    assert checks[0].status.value == "info"
    assert "behind" not in checks[0].text
    assert "validate them before any deployment action" in checks[0].text


def test_php_drift_is_config():
    _, diffs, checks = _rows(Observation(_page(php_version="8.1"), _github()))
    assert [item.field for item in diffs] == ["php_version"]
    assert checks[0].id == "config-php_version"
    assert "from 8.1 to 8.2" in checks[0].text


def test_failing_checks_block_the_pull_request():
    github = _github(open_prs=(_pull(checks="failing", title="Add ceremony timeline", number=12),))
    _, _, checks = _rows(Observation(_page(), github))
    assert checks[0].status.value == "blocked"
    assert "failing" in checks[0].text


def test_draft_and_conflicts_and_unknown_mergeability():
    for pull, needle in (
        (_pull(draft=True), "draft"),
        (_pull(mergeable=False), "conflicts"),
        (_pull(mergeable=None), "unknown"),
        (_pull(checks="pending"), "waiting"),
    ):
        _, _, checks = _rows(Observation(_page(), _github(open_prs=(pull,))))
        assert checks[0].status.value == "blocked"
        assert needle in checks[0].text


def test_aligned_live_site_is_done():
    _, diffs, checks = _rows(Observation(_page(), _github()))
    assert diffs == ()
    assert checks[0].id == "noop"
    assert checks[0].status.value == "done"


def test_partial_deployment_observation_is_not_reported_as_aligned():
    page = _page(deployed_sha=None, php_version=None, ssl=None, document_root=None)
    _, diffs, checks = _rows(Observation(page, _github()))
    assert diffs == ()
    assert checks[0].id == "verify-deployment"
    assert checks[0].status.value == "info"
    assert "deployed commit SHA" in checks[0].text
    assert "observed PHP version" in checks[0].text
    assert not any(item.status.value == "done" for item in checks)


def test_stale_live_commit_is_info_and_not_a_failure_row():
    github = _github(head_at="2026-04-02T15:00:00Z")
    _, _, checks = _rows(Observation(_page(deployed_sha="aaa111"), github))
    assert checks[0].id == "stale-bot"
    assert checks[0].status.value == "info"
    assert "days old" in checks[0].text


def test_unpublished_real_repo_asks_for_a_deploy():
    page = _page(
        title="Coming Soon",
        is_default_template=True,
        fingerprint="default",
        deployed_sha=None,
    )
    kind, diffs, checks = _rows(Observation(page, _github()))
    assert kind.kind.value == "stub"
    assert diffs[0].field == "unpublished"
    assert checks[0].status.value == "ready"
    assert checks[0].id == "deploy"


def test_placeholder_with_a_merge_ready_pr_does_not_deploy_main_yet():
    github = _github(
        head_subject="Create Hostinger website",
        head_sha="ccc333",
        content_files=("index.html",),
        open_prs=(_pull(number=4, title="Replace the coming-soon page with the public index"),),
    )
    page = _page(title="Coming Soon", is_default_template=True, fingerprint="default", deployed_sha="ccc333")
    _, diffs, checks = _rows(Observation(page, github))
    assert diffs == ()
    by_id = {item.id: item for item in checks}
    assert by_id["pr-4"].status.value == "ready"
    assert by_id["after-merge"].status.value == "info"
    assert "replace-placeholder" not in by_id
