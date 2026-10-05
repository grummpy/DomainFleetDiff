from domain_fleet.models import CheckStatus, Kind

EXPECTED = {
    "saltydogcustoms": {
        "kind": Kind.LIVE,
        "diffs": [],
        "ready": ["pr-18"],
    },
    "grassandherb": {
        "kind": Kind.LIVE,
        "diffs": ["content"],
        "ready": ["deploy"],
    },
    "funtimerental": {
        "kind": Kind.STUB,
        "diffs": [],
        "ready": ["replace-placeholder"],
    },
    "bornfreethreads": {
        "kind": Kind.LIVE,
        "diffs": ["config"],
        "ready": ["config-php_version"],
    },
    "victorydraw": {
        "kind": Kind.STUB,
        "diffs": [],
        "ready": ["create-repo", "deploy-key"],
    },
    "whdecklog": {
        "kind": Kind.LIVE,
        "diffs": [],
        "ready": [],
        "done": ["noop"],
    },
    "deckereverafter": {
        "kind": Kind.LIVE,
        "diffs": [],
        "ready": [],
        "blocked": ["pr-12"],
    },
    "reliablerealtymanagement": {
        "kind": Kind.STUB,
        "diffs": ["content"],
        "ready": ["deploy"],
    },
    "kingslandgeorgiapd": {
        "kind": Kind.LIVE,
        "diffs": [],
        "ready": [],
        "info": ["stale-bot"],
    },
    "corruptofficertracker": {
        "kind": Kind.STUB,
        "diffs": [],
        "ready": ["pr-4"],
        "info": ["after-merge"],
    },
}


def test_sample_fleet_has_the_ten_sites_and_the_hub(sample_fleet):
    assert sample_fleet.hub.repo == "grummpy/my_domains"
    assert [site.slug for site in sample_fleet.sites] == list(EXPECTED)


def test_sample_scan_matches_the_demo_narrative(sample_report):
    summary = sample_report.summary
    assert summary.sites == 10
    assert summary.live == 6
    assert summary.stub == 4
    assert summary.unknown == 0
    assert summary.content_diffs == 2
    assert summary.config_diffs == 1
    assert summary.merge_ready == 8
    assert sample_report.scanned_at == "2026-10-01T00:00:00Z"

    by_slug = {card.slug: card for card in sample_report.cards}
    assert set(by_slug) == set(EXPECTED)
    for slug, expected in EXPECTED.items():
        card = by_slug[slug]
        assert card.kind == expected["kind"], slug
        assert [diff.kind.value for diff in card.diffs] == expected["diffs"], slug
        ready = [item.id for item in card.checks if item.status == CheckStatus.READY]
        assert ready == expected["ready"], slug
        for status_name, ids in (("done", "done"), ("blocked", "blocked"), ("info", "info")):
            if status_name in expected:
                found = [item.id for item in card.checks if item.status.value == status_name]
                assert found == expected[status_name], slug


def test_stub_and_drift_sort_ahead_of_healthy_sites(sample_report):
    kinds = [card.kind for card in sample_report.cards]
    assert kinds[0] == Kind.STUB
    assert kinds[-1] == Kind.LIVE
    # A live site with a diff stays with the other live cards, ahead of quiet ones.
    live = [card for card in sample_report.cards if card.kind == Kind.LIVE]
    assert live[0].diffs
    assert live[-1].slug == "whdecklog"


def test_content_diff_shas_stay_distinct_in_the_short_form(sample_report):
    card = next(item for item in sample_report.cards if item.slug == "grassandherb")
    summary = card.diffs[0].summary
    assert "b22aaa0" in summary
    assert "b22bbb0" in summary


def test_reliable_realty_is_stub_even_though_the_brand_is_in_the_body(sample_report):
    card = next(item for item in sample_report.cards if item.slug == "reliablerealtymanagement")
    assert card.kind == Kind.STUB
    assert any("real build" in reason for reason in card.reasons)
    assert any("stub catalog" in reason for reason in card.reasons)


def test_victorydraw_suggests_a_repo_under_the_hub_owner(sample_report):
    card = next(item for item in sample_report.cards if item.slug == "victorydraw")
    text = " ".join(item.text for item in card.checks)
    assert "grummpy/victorydraw" in text
    assert "not in grummpy/my_domains" in text


def test_round_trip_json(sample_report):
    from domain_fleet.models import ScanReport

    restored = ScanReport.from_dict(sample_report.to_dict())
    assert restored.to_dict() == sample_report.to_dict()
