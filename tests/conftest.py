from __future__ import annotations

import pytest

from domain_fleet.fleet_load import load_fleet, sample_fleet_path
from domain_fleet.scan import scan_fleet
from domain_fleet.signals import parse_time

DEMO_NOW = "2026-10-01T00:00:00Z"


@pytest.fixture(scope="session")
def sample_fleet():
    return load_fleet(sample_fleet_path())


@pytest.fixture(scope="session")
def sample_report(sample_fleet):
    from domain_fleet.adapters.fixture import FixtureFleetSource

    observations = FixtureFleetSource().load(sample_fleet)
    return scan_fleet(
        sample_fleet,
        observations,
        source="fixture",
        now=parse_time(DEMO_NOW),
    )
