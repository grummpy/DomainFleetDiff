"""Map a normalized website record into a Hostinger observation.

Hostinger's API does not return page title or a stub flag directly. A bot
that already downloaded the homepage should run ``signals_from_html`` and
merge PHP, SSL, document root, and the deployed SHA from hPanel or the git
deploy into the dict ``hostinger_from_normalized`` accepts.

This module does not read ``HOSTINGER_API_TOKEN`` and does not open a socket.
"""

from __future__ import annotations

from typing import Protocol

from domain_fleet.models import FleetError, HostingerObservation

_FINGERPRINTS = {"custom", "default", "unknown"}


class HostingerTransport(Protocol):
    """Return the normalized website dict for one domain."""

    def fetch_website(self, domain: str) -> dict:
        """Normalized record. Implementations perform their own HTTP."""


def hostinger_from_normalized(payload: dict) -> HostingerObservation:
    fingerprint = str(payload.get("fingerprint") or "unknown")
    if fingerprint not in _FINGERPRINTS:
        raise FleetError("fingerprint must be custom, default, or unknown")
    if "title" not in payload or "is_default_template" not in payload:
        raise FleetError("website payload needs title and is_default_template")
    if not isinstance(payload["is_default_template"], bool):
        raise FleetError("is_default_template must be true or false")
    return HostingerObservation(
        title=str(payload["title"]),
        body_excerpt=str(payload.get("body_excerpt") or ""),
        is_default_template=payload["is_default_template"],
        fingerprint=fingerprint,
        php_version=_optional_str(payload.get("php_version")),
        ssl=_optional_bool(payload.get("ssl")),
        document_root=_optional_str(payload.get("document_root")),
        deployed_sha=_optional_str(payload.get("deployed_sha")),
        last_deploy_at=_optional_str(payload.get("last_deploy_at")),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise FleetError("ssl must be true, false, or omitted")
    return value
