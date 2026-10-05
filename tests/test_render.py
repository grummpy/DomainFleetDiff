from domain_fleet.render import render_html, render_text


def test_text_report_lists_counts_and_a_ready_row(sample_report):
    text = render_text(sample_report)
    assert "6 live · 4 stub · 0 unknown · 2 content · 1 config · 8 merge-ready" in text
    assert "STUB    corruptofficertracker.com" in text
    assert '[ready  ] Merge #4 "Replace the coming-soon page with the public index"' in text
    assert "whdecklog.com" in text
    assert "[done   ]" in text


def test_html_escapes_markup_and_lists_every_domain(sample_report):
    from domain_fleet.models import SiteCard

    hostile = SiteCard(
        slug="xss",
        domain="xss.example",
        name="<script>alert(1)</script>",
        bot="bot",
        github_repo="grummpy/xss",
        kind=sample_report.cards[0].kind,
        reasons=("<img src=x onerror=alert(1)>",),
        diffs=(),
        checks=sample_report.cards[0].checks[:1],
        head_sha=None,
        head_subject=None,
        head_at=None,
        author=None,
        deployed_sha=None,
        last_deploy_at=None,
        open_prs=(),
    )
    report = type(sample_report)(
        schema=sample_report.schema,
        scanned_at=sample_report.scanned_at,
        source=sample_report.source,
        fleet=sample_report.fleet,
        hub_repo=sample_report.hub_repo,
        hub_branch=sample_report.hub_branch,
        summary=sample_report.summary,
        cards=(hostile,),
    )
    page = render_html(report)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x" not in page

    full = render_html(sample_report)
    for domain in (
        "saltydogcustoms.com",
        "grassandherb.com",
        "funtimerental.com",
        "bornfreethreads.com",
        "victorydraw.com",
        "whdecklog.com",
        "deckereverafter.com",
        "reliablerealtymanagement.com",
        "kingslandgeorgiapd.com",
        "corruptofficertracker.com",
    ):
        assert domain in full
    assert "Advisory only" in full
    assert 'data-filter="stub"' in full
