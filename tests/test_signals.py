from domain_fleet.adapters.hostinger import hostinger_from_normalized
from domain_fleet.classify import classify_site
from domain_fleet.models import Observation, SiteSpec
from domain_fleet.signals import (
    STUB_BODY_MARKERS,
    STUB_TITLE_MARKERS,
    content_files_from_tree,
    signals_from_html,
)

COMING_SOON = """
<html><head>
<title>Website Coming Soon</title>
<style>.x { color: red; }</style>
</head>
<body><div class="default-website-template">placeholder</div>
<script>alert("ignore me")</script>
</body></html>
"""

LIVE_PAGE = """
<html><head><title>Salty Dog Customs | Boat lettering and vinyl</title></head>
<body><p>Salty Dog Customs paints hull names and vinyl for boats on the coast.
Browse the gallery, read how the gelcoat is prepped, and send a quote request
for a transom name or a hull stripe.</p></body></html>
"""


def test_catalogs_are_the_documented_rules():
    assert "coming soon" in STUB_TITLE_MARKERS
    assert "parked domain" in STUB_TITLE_MARKERS
    assert "default-website-template" in STUB_BODY_MARKERS
    assert "you have successfully created a website with hostinger" in STUB_BODY_MARKERS


def test_coming_soon_html_is_a_default_template():
    signals = signals_from_html(COMING_SOON)
    assert signals["title"] == "Website Coming Soon"
    assert signals["is_default_template"] is True
    assert signals["fingerprint"] == "default"
    assert "alert" not in signals["body_excerpt"]
    assert "color: red" not in signals["body_excerpt"]


def test_brand_html_is_custom_and_classifies_live():
    signals = signals_from_html(LIVE_PAGE)
    assert signals["fingerprint"] == "custom"
    assert signals["is_default_template"] is False
    page = hostinger_from_normalized({**signals, "php_version": "8.2", "ssl": True})
    site = SiteSpec(
        slug="saltydogcustoms",
        domain="saltydogcustoms.com",
        name="Salty Dog Customs",
        bot="saltydog-bot",
        github_repo="grummpy/saltydogcustoms",
        brand_markers=("Salty Dog",),
        php_version="8.2",
        ssl=True,
        document_root="public_html",
    )
    result = classify_site(site, Observation(page, None), min_content_files=2)
    assert result.kind.value == "live"


def test_tree_keeps_page_files_and_drops_dotfiles():
    files = content_files_from_tree(
        {
            "tree": [
                {"path": "index.html", "type": "blob"},
                {"path": "css/site.css", "type": "blob"},
                {"path": ".github/workflows/pytest.yml", "type": "blob"},
                {"path": "assets", "type": "tree"},
                {"path": "photo.png", "type": "blob"},
            ]
        }
    )
    assert files == ["index.html", "css/site.css"]
