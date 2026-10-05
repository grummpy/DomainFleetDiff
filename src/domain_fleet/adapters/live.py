"""Live source. Constructing it without both transports is a hard error.

Wiring a real client is a bot's job: pass objects that satisfy
``GitHubTransport`` and ``HostingerTransport``. Nothing in this package
reads tokens from the environment.
"""

from __future__ import annotations

from domain_fleet.adapters.github import GitHubTransport, github_from_normalized
from domain_fleet.adapters.hostinger import HostingerTransport, hostinger_from_normalized
from domain_fleet.models import Fleet, FleetError, Observation


class AdapterNotConfigured(FleetError):
    """Raised when a live scan is requested without injected transports."""


_NOT_CONFIGURED = (
    "Live GitHub and Hostinger adapters are interfaces only in this starter. "
    "They do not read tokens and they do not call the network. "
    "Use --source fixture for the offline demo, or inject a GitHubTransport and "
    "a HostingerTransport from your own bot. "
    "When you wire those yourself, the usual env names are GITHUB_TOKEN and "
    "HOSTINGER_API_TOKEN. Do not commit either value."
)


class LiveFleetSource:
    name = "live"

    def __init__(
        self,
        github: GitHubTransport | None,
        hostinger: HostingerTransport | None,
    ) -> None:
        if github is None or hostinger is None:
            raise AdapterNotConfigured(_NOT_CONFIGURED)
        self._github = github
        self._hostinger = hostinger

    def load(self, fleet: Fleet) -> dict[str, Observation]:
        loaded: dict[str, Observation] = {}
        for site in fleet.sites:
            page = hostinger_from_normalized(self._hostinger.fetch_website(site.domain))
            github = None
            if site.github_repo:
                github = github_from_normalized(self._github.fetch_repo(site.github_repo))
            loaded[site.slug] = Observation(hostinger=page, github=github)
        return loaded
