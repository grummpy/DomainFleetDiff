"""Offline observations stored beside each site in the fleet TOML."""

from __future__ import annotations

from domain_fleet.models import Fleet, FleetError, Observation


class FixtureFleetSource:
    """Read observations that were already written into the manifest.

    Tests and ``domain-fleet scan`` use this source. It does not call
    GitHub or Hostinger.
    """

    name = "fixture"

    def load(self, fleet: Fleet) -> dict[str, Observation]:
        missing: list[str] = []
        loaded: dict[str, Observation] = {}
        for site in fleet.sites:
            observation = fleet.observations.get(site.slug)
            if observation is None or observation.hostinger is None:
                missing.append(site.slug)
                continue
            if site.github_repo and observation.github is None:
                missing.append(site.slug)
                continue
            loaded[site.slug] = observation
        if missing:
            joined = ", ".join(missing)
            raise FleetError(
                "fixture source needs offline observations for: "
                f"{joined}. Add [sites.hostinger] and, when github_repo is set, "
                "[sites.github]. The packaged sample fleet already has them."
            )
        return loaded
