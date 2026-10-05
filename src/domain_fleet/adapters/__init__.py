"""Observation sources. Fixture data is the default. Live clients stay behind transports."""

from domain_fleet.adapters.fixture import FixtureFleetSource
from domain_fleet.adapters.live import AdapterNotConfigured, LiveFleetSource

__all__ = ["AdapterNotConfigured", "FixtureFleetSource", "LiveFleetSource"]
