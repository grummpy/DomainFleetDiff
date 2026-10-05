"""Source interface shared by the fixture fleet and a future live fleet."""

from __future__ import annotations

from typing import Protocol

from domain_fleet.models import Fleet, Observation


class FleetSource(Protocol):
    name: str

    def load(self, fleet: Fleet) -> dict[str, Observation]:
        """Return one observation per site slug."""
