"""Command line for ``domain-fleet scan`` and ``domain-fleet report``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from domain_fleet import __version__
from domain_fleet.adapters.fixture import FixtureFleetSource
from domain_fleet.adapters.live import LiveFleetSource
from domain_fleet.fleet_load import load_fleet, sample_fleet_path
from domain_fleet.models import FleetError, Kind, ScanReport
from domain_fleet.render import render_html, render_text
from domain_fleet.scan import scan_fleet
from domain_fleet.signals import parse_time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domain-fleet",
        description=(
            "Classify a multi-site Hostinger and GitHub fleet and print a "
            "merge-ready checklist. The scan does not merge or deploy."
        ),
    )
    parser.add_argument("--version", action="version", version=f"domain-fleet {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="Classify the fleet and print checklists")
    scan.add_argument(
        "--fleet",
        type=Path,
        help="Hub fleet TOML. Defaults to the packaged offline sample.",
    )
    scan.add_argument(
        "--source",
        choices=("fixture", "live"),
        default="fixture",
        help="fixture reads observations in the TOML. live requires injected transports.",
    )
    scan.add_argument("--html", type=Path, help="Write a self-contained HTML report")
    scan.add_argument("--json", help="Write scan JSON to this path, or - for stdout")
    scan.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when any site is stub, unknown, or has a diff",
    )
    scan.add_argument(
        "--now",
        help="ISO-8601 clock override for stale-commit checks. Defaults to the current time.",
    )

    report = commands.add_parser("report", help="Render HTML from scan JSON")
    report.add_argument("--json", required=True, help="Scan JSON path")
    report.add_argument("--html", type=Path, required=True, help="HTML output path")

    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            return _scan(args)
        return _report(args)
    except FleetError as exc:
        print(f"domain-fleet: {exc}", file=sys.stderr)
        return 2


def _scan(args: argparse.Namespace) -> int:
    using_sample = args.fleet is None
    fleet_path = args.fleet if args.fleet is not None else sample_fleet_path()
    fleet = load_fleet(fleet_path)
    if args.source == "live":
        LiveFleetSource(None, None)
        return 2
    observations = FixtureFleetSource().load(fleet)
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    report = scan_fleet(fleet, observations, source="fixture", now=now)
    payload = report.to_dict()

    if using_sample and args.json != "-":
        print(
            "note: packaged sample fleet (offline). Pass --fleet to scan your hub manifest.",
            file=sys.stderr,
        )

    if args.json == "-":
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report))
        if args.json:
            _write(Path(args.json), json.dumps(payload, indent=2) + "\n")

    if args.html:
        _write(args.html, render_html(report))

    if args.strict and _dirty(report):
        return 1
    return 0


def _report(args: argparse.Namespace) -> int:
    try:
        raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
    except OSError as exc:
        raise FleetError(f"cannot read {args.json}: {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise FleetError(f"{args.json}: invalid JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise FleetError(f"{args.json}: scan JSON must be an object")
    report = ScanReport.from_dict(raw)
    _write(args.html, render_html(report))
    print(f"wrote {args.html}")
    return 0


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _dirty(report: ScanReport) -> bool:
    if any(card.kind != Kind.LIVE for card in report.cards):
        return True
    return any(card.diffs for card in report.cards)
