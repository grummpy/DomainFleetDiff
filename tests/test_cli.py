import json
import subprocess
import sys
from pathlib import Path

from domain_fleet.fleet_load import sample_fleet_path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "domain_fleet", *args],
        cwd=ROOT,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )


def test_scan_writes_json_and_html(tmp_path: Path):
    json_path = tmp_path / "scan.json"
    html_path = tmp_path / "nested" / "fleet.html"
    result = _run(
        "scan",
        "--now",
        "2026-10-01T00:00:00Z",
        "--json",
        str(json_path),
        "--html",
        str(html_path),
    )
    assert result.returncode == 0, result.stderr
    assert "packaged sample fleet" in result.stderr
    assert "8 merge-ready" in result.stdout
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["stub"] == 4
    assert "saltydogcustoms.com" in html_path.read_text(encoding="utf-8")


def test_scan_json_stdout_skips_the_text_report():
    result = _run("scan", "--now", "2026-10-01T00:00:00Z", "--json", "-")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["hub"]["repo"] == "grummpy/my_domains"
    assert "note:" not in result.stderr


def test_strict_exits_one_on_the_sample_fleet():
    result = _run("scan", "--now", "2026-10-01T00:00:00Z", "--strict")
    assert result.returncode == 1
    assert "STUB" in result.stdout


def test_live_source_exits_two_without_calling_the_network():
    result = _run("scan", "--source", "live")
    assert result.returncode == 2
    assert "do not call the network" in result.stderr
    assert "HOSTINGER_API_TOKEN" in result.stderr


def test_report_renders_html_from_scan_json(tmp_path: Path):
    json_path = tmp_path / "scan.json"
    html_path = tmp_path / "report.html"
    scanned = _run("scan", "--now", "2026-10-01T00:00:00Z", "--json", str(json_path))
    assert scanned.returncode == 0, scanned.stderr
    rendered = _run("report", "--json", str(json_path), "--html", str(html_path))
    assert rendered.returncode == 0, rendered.stderr
    text = html_path.read_text(encoding="utf-8")
    assert "Domain Fleet" in text
    assert "corruptofficertracker.com" in text


def test_missing_fleet_exits_two(tmp_path: Path):
    result = _run("scan", "--fleet", str(tmp_path / "missing.toml"))
    assert result.returncode == 2
    assert "cannot read fleet file" in result.stderr


def test_custom_fleet_path_is_accepted():
    result = _run("scan", "--fleet", str(sample_fleet_path()), "--now", "2026-10-01T00:00:00Z", "--json", "-")
    assert result.returncode == 0, result.stderr
    assert "packaged sample fleet" not in result.stderr
    assert json.loads(result.stdout)["summary"]["sites"] == 10
