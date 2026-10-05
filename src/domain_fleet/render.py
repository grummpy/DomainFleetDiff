"""Text and self-contained HTML renderings of a scan."""

from __future__ import annotations

import html

from domain_fleet.models import CheckStatus, Kind, ScanReport, SiteCard

_STATUS_ORDER = {
    CheckStatus.READY: 0,
    CheckStatus.BLOCKED: 1,
    CheckStatus.INFO: 2,
    CheckStatus.DONE: 3,
}


def render_text(report: ScanReport) -> str:
    summary = report.summary
    lines = [
        (
            f"Domain Fleet Diff  {report.source}  hub {report.hub_repo}  {report.scanned_at}"
        ),
        (
            f"{summary.sites} sites · {summary.live} live · {summary.stub} stub · "
            f"{summary.unknown} unknown · {summary.content_diffs} content · "
            f"{summary.config_diffs} config · {summary.merge_ready} merge-ready"
        ),
        "",
    ]
    for card in report.cards:
        lines.extend(_text_card(card))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _text_card(card: SiteCard) -> list[str]:
    repo = card.github_repo or "no repo"
    head = _sha(card.head_sha)
    subject = card.head_subject or "no commit recorded"
    when = (card.head_at or "")[:10]
    lines = [
        f"{card.kind.value.upper():7} {card.domain}  {card.name}",
        f"        bot {card.bot}  repo {repo}",
        f"        head {head}  {subject}  {when}".rstrip(),
    ]
    if card.diffs:
        drift = "; ".join(f"{item.kind.value}: {item.summary}" for item in card.diffs)
        lines.append(f"        drift {drift}")
    for reason in card.reasons:
        lines.append(f"        why: {reason}")
    for check in sorted(card.checks, key=lambda item: _STATUS_ORDER[item.status]):
        lines.append(f"        [{check.status.value:7}] {check.text}")
    return lines


def render_html(report: ScanReport) -> str:
    summary = report.summary
    cards = "\n".join(_html_card(card) for card in report.cards)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Domain Fleet Diff — {html.escape(report.hub_repo)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<header class="top">
  <div>
    <p class="eyebrow">Compare · Deploy · Govern</p>
    <h1>Domain Fleet <span>Diff</span></h1>
    <p class="lede">Hub <a href="https://github.com/{html.escape(report.hub_repo)}">{html.escape(report.hub_repo)}</a>
      · {html.escape(report.scanned_at)} · source {html.escape(report.source)}</p>
  </div>
</header>
<section class="stats" aria-label="Fleet summary">
  <div><strong>{summary.sites}</strong><span>Sites</span></div>
  <div><strong class="live">{summary.live}</strong><span>Live</span></div>
  <div><strong class="stub">{summary.stub}</strong><span>Stub</span></div>
  <div><strong>{summary.unknown}</strong><span>Unknown</span></div>
  <div><strong class="diff">{summary.content_diffs}</strong><span>Content diffs</span></div>
  <div><strong class="diff">{summary.config_diffs}</strong><span>Config diffs</span></div>
  <div><strong class="ready">{summary.merge_ready}</strong><span>Merge-ready</span></div>
</section>
<nav class="filters" aria-label="Filter sites">
  <button type="button" data-filter="all" aria-pressed="true">All</button>
  <button type="button" data-filter="stub">Stub</button>
  <button type="button" data-filter="live">Live</button>
  <button type="button" data-filter="diff">Has diff</button>
  <button type="button" data-filter="ready">Merge-ready</button>
</nav>
<main>
{cards}
</main>
<footer>
  <p>Advisory only. domain-fleet does not merge pull requests or deploy to Hostinger. Checklist rows are the next step for that site's bot or for you.</p>
</footer>
<script>
{_JS}
</script>
</body>
</html>
"""


def _html_card(card: SiteCard) -> str:
    ready = any(check.status == CheckStatus.READY for check in card.checks)
    diffs = "yes" if card.diffs else "no"
    repo = card.github_repo or ""
    repo_html = (
        f'<a href="https://github.com/{html.escape(repo)}">{html.escape(repo)}</a>'
        if repo
        else "no repo linked"
    )
    chips = "".join(
        f'<li class="chip {html.escape(diff.kind.value)}">{html.escape(diff.kind.value)} · {html.escape(diff.summary)}</li>'
        for diff in card.diffs
    )
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in card.reasons)
    checks = "".join(
        f'<li class="{html.escape(check.status.value)}">'
        f"<span>{html.escape(check.status.value)}</span>"
        f"{_check_html(card, check_text=check.text, check_id=check.id)}</li>"
        for check in card.checks
    )
    pr_links = "".join(
        '<a href="https://github.com/{repo}/pull/{number}">#{number}</a>'.format(
            repo=html.escape(repo),
            number=pull.number,
        )
        for pull in card.open_prs
        if repo
    )
    head = html.escape(_sha(card.head_sha))
    subject = html.escape(card.head_subject or "no commit recorded")
    when = html.escape((card.head_at or "—")[:10])
    deployed = html.escape(_sha(card.deployed_sha)) if card.deployed_sha else "—"
    return f"""
<article class="site" data-kind="{html.escape(card.kind.value)}" data-diffs="{diffs}" data-ready="{"yes" if ready else "no"}">
  <header>
    <p class="badge {html.escape(card.kind.value)}">{html.escape(card.kind.value)}</p>
    <h2>{html.escape(card.name)}</h2>
    <p class="domain">{html.escape(card.domain)}</p>
  </header>
  <dl>
    <div><dt>Bot</dt><dd>{html.escape(card.bot)}</dd></div>
    <div><dt>Repo</dt><dd>{repo_html}</dd></div>
    <div><dt>HEAD</dt><dd><code>{head}</code> {subject}</dd></div>
    <div><dt>Commit</dt><dd>{when} · {html.escape(card.author or "—")}</dd></div>
    <div><dt>Deployed</dt><dd><code>{deployed}</code></dd></div>
    <div><dt>PRs</dt><dd>{pr_links or "none"}</dd></div>
  </dl>
  <ul class="chips">{chips}</ul>
  <h3>Why</h3>
  <ul class="reasons">{reasons}</ul>
  <h3>Checklist</h3>
  <ul class="checks">{checks}</ul>
</article>
"""


def _check_html(card: SiteCard, *, check_text: str, check_id: str) -> str:
    text = html.escape(check_text)
    if not check_id.startswith("pr-") or not card.github_repo:
        return text
    number = check_id.removeprefix("pr-")
    href = f"https://github.com/{html.escape(card.github_repo)}/pull/{html.escape(number)}"
    label = f"#{html.escape(number)}"
    # The checklist sentence already contains #N. Link that token once.
    token = f"#{html.escape(number)}"
    linked = f'<a href="{href}">{label}</a>'
    if token in text:
        return text.replace(token, linked, 1)
    return f'{linked} {text}'


def _sha(value: str | None) -> str:
    if not value:
        return "unknown"
    return value[:7]


_CSS = """
:root {
  color-scheme: dark;
  --bg: #070b14;
  --card: #10192b;
  --line: #24344d;
  --text: #e8eef8;
  --muted: #93a4bb;
  --cyan: #3ee0ff;
  --green: #3ee0a2;
  --amber: #f0b429;
  --magenta: #e24bff;
  --red: #ff7b88;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Inter, "Segoe UI", sans-serif;
  background: radial-gradient(900px 420px at 70% -10%, rgba(62, 224, 255, 0.12), transparent 60%), var(--bg);
  color: var(--text);
}
a { color: var(--cyan); text-decoration: none; }
a:hover { text-decoration: underline; }
.top, .stats, .filters, main, footer { width: min(1080px, calc(100% - 32px)); margin: 0 auto; }
.top { padding: 32px 0 8px; }
.eyebrow { letter-spacing: 0.22em; text-transform: uppercase; color: var(--muted); font-size: 12px; margin: 0 0 8px; }
h1 { font-size: 40px; line-height: 1; margin: 0; }
h1 span { color: var(--cyan); }
.lede { color: var(--muted); }
.stats { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; padding: 8px 0 16px; }
.stats div { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
.stats strong { display: block; font-size: 28px; }
.stats span { color: var(--muted); font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; }
.live { color: var(--green); }
.stub { color: var(--amber); }
.diff { color: var(--magenta); }
.ready { color: var(--cyan); }
.filters { display: flex; flex-wrap: wrap; gap: 8px; padding-bottom: 16px; }
.filters button {
  background: transparent; color: var(--text); border: 1px solid var(--line);
  border-radius: 999px; padding: 6px 12px; cursor: pointer;
}
.filters button[aria-pressed="true"] { border-color: var(--cyan); color: var(--cyan); }
main { display: grid; gap: 14px; }
.site { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px 18px 8px; }
.site header { display: grid; grid-template-columns: auto 1fr; grid-template-areas: "badge name" "badge domain"; column-gap: 12px; align-items: center; }
.badge { grid-area: badge; margin: 0; padding: 6px 10px; border-radius: 999px; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; }
.badge.live { color: var(--green); background: rgba(62, 224, 162, 0.12); }
.badge.stub { color: var(--amber); background: rgba(240, 180, 41, 0.12); }
.badge.unknown { color: var(--muted); background: rgba(147, 164, 187, 0.12); }
.site h2 { grid-area: name; margin: 0; font-size: 20px; }
.domain { grid-area: domain; margin: 0; color: var(--muted); }
dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin: 14px 0; }
dl div { min-width: 0; }
dt { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
dd { margin: 2px 0 0; overflow-wrap: anywhere; }
code { font-family: "Cascadia Mono", ui-monospace, monospace; color: var(--cyan); }
.chips, .reasons, .checks { list-style: none; padding: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { border-radius: 999px; padding: 4px 10px; font-size: 13px; }
.chip.content { color: var(--cyan); background: rgba(62, 224, 255, 0.1); }
.chip.config { color: var(--magenta); background: rgba(226, 75, 255, 0.12); }
h3 { font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 12px 0 6px; }
.reasons li { margin: 0 0 4px; }
.checks li { display: grid; grid-template-columns: 88px 1fr; gap: 8px; padding: 7px 0; border-top: 1px solid var(--line); overflow-wrap: anywhere; }
.checks li span { font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; }
.checks .ready span { color: var(--cyan); }
.checks .blocked span { color: var(--red); }
.checks .info span { color: var(--amber); }
.checks .done span { color: var(--green); }
footer { color: var(--muted); font-size: 13px; padding: 22px 0 40px; }
@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  dl { grid-template-columns: 1fr; }
  h1 { font-size: 32px; }
}
"""

_JS = """
const buttons = document.querySelectorAll("[data-filter]");
buttons.forEach((button) => {
  button.addEventListener("click", () => {
    const filter = button.getAttribute("data-filter");
    buttons.forEach((item) => item.setAttribute("aria-pressed", item === button ? "true" : "false"));
    document.querySelectorAll("article.site").forEach((card) => {
      const kind = card.getAttribute("data-kind");
      const diffs = card.getAttribute("data-diffs");
      const ready = card.getAttribute("data-ready");
      const show = filter === "all"
        || (filter === "stub" && kind === "stub")
        || (filter === "live" && kind === "live")
        || (filter === "diff" && diffs === "yes")
        || (filter === "ready" && ready === "yes");
      card.hidden = !show;
    });
  });
});
"""
