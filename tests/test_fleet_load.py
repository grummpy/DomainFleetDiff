from pathlib import Path

import pytest

from domain_fleet.fleet_load import load_fleet
from domain_fleet.models import FleetError

MINIMAL = """
schema = 1

[hub]
repo = "grummpy/my_domains"
branch = "main"
role = "Registry"

[policy]
stale_commit_days = 90
min_content_files = 2

[[sites]]
slug = "example"
domain = "example.com"
name = "Example"
bot = "example-bot"
github_repo = "grummpy/example"
brand_markers = ["Example"]
"""


def test_specs_only_manifest_loads_without_observations(tmp_path: Path):
    path = tmp_path / "fleet.toml"
    path.write_text(MINIMAL, encoding="utf-8")
    fleet = load_fleet(path)
    assert fleet.sites[0].slug == "example"
    assert fleet.observations["example"].hostinger is None
    assert fleet.observations["example"].github is None


def test_fixture_source_rejects_a_manifest_without_observations(tmp_path: Path):
    from domain_fleet.adapters.fixture import FixtureFleetSource

    path = tmp_path / "fleet.toml"
    path.write_text(MINIMAL, encoding="utf-8")
    fleet = load_fleet(path)
    with pytest.raises(FleetError, match="example"):
        FixtureFleetSource().load(fleet)


def test_unknown_key_is_an_error(tmp_path: Path):
    path = tmp_path / "fleet.toml"
    path.write_text(MINIMAL + "\npassword = \"nope\"\n", encoding="utf-8")
    with pytest.raises(FleetError, match="unknown keys"):
        load_fleet(path)


def test_duplicate_slug_is_an_error(tmp_path: Path):
    path = tmp_path / "fleet.toml"
    path.write_text(
        MINIMAL
        + """
[[sites]]
slug = "example"
domain = "other.example"
name = "Other"
bot = "other-bot"
github_repo = ""
brand_markers = ["Other"]
""",
        encoding="utf-8",
    )
    with pytest.raises(FleetError, match="duplicate slug"):
        load_fleet(path)
