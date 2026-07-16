#!/usr/bin/env python3
"""Build and optionally serve the local AeroSense runtime dashboard."""

from __future__ import annotations

import argparse
import csv
import errno
import json
import re
import statistics
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping, Optional, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = Path(__file__).resolve().parent
DEFAULT_LEDGER = REPOSITORY_ROOT / "runtime_test_runs.txt"
DEFAULT_OUTPUT = DASHBOARD_DIR / "index.html"

REQUIRED_LEDGER_COLUMNS = {
    "timestamp_utc",
    "status",
    "airport",
    "commit_ref",
    "elapsed_seconds",
}

RULESET_NAMES = {
    "mos139_2019": "MOS139 (C.07 2026)",
    "icao_annex14_vol1_modernised_ofs_oes": "Annex 14 Modernised OLS",
    "icao_annex14_vol1_current_ols": "Annex 14 Current OLS",
    "uk_caa_cap168_edition_13": "UK CAP 168 Edition 13",
    "easa_cs_adr_dsn_issue_7": "EASA CS-ADR-DSN Issue 7",
}
RUNWAY_SCENARIOS = {"single", "parallel", "intersecting", "mixed"}


def _field(row: Mapping[str, object], name: str) -> str:
    return str(row.get(name, "") or "").strip()


def _float(value: object) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _integer(value: object) -> Optional[int]:
    number = _float(value)
    return int(number) if number is not None else None


def _runway_scenario(value: object, runway_count: Optional[int]) -> str:
    scenario = str(value or "").strip().lower()
    if scenario not in RUNWAY_SCENARIOS:
        return ""
    if runway_count is None:
        return scenario
    if scenario == "single" and runway_count != 1:
        return ""
    if scenario in {"parallel", "intersecting"} and runway_count < 2:
        return ""
    if scenario == "mixed" and runway_count < 3:
        return ""
    return scenario


def _bool(value: object) -> Optional[bool]:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ruleset_name(identifier: str, label: str) -> str:
    return label or RULESET_NAMES.get(identifier, identifier.replace("_", " ").title()) or "Not recorded"


def _run_source(agent: str) -> str:
    lowered = agent.lower()
    if "headless" in lowered or "codex" in lowered or "ci" == lowered:
        return "Codex"
    return "User"


def _uppercase_icao_reference(value: object, airport: object) -> str:
    text = str(value or "").strip()
    code = str(airport or "").strip().upper()
    if len(code) == 4 and code.isalpha():
        return re.sub(rf"\b{re.escape(code)}\b", code, text, flags=re.IGNORECASE)
    return text


def _humanize_case_identifier(value: object, airport: object) -> str:
    humanized = str(value or "").replace("_", " ").replace("-", " ").title()
    return _uppercase_icao_reference(humanized, airport)


def _plain_case_name(row: Mapping[str, object], airport: str) -> str:
    name = _field(row, "test_case_name")
    if name:
        return _uppercase_icao_reference(name, airport)
    identifier = _field(row, "test_case_id")
    if identifier:
        return _humanize_case_identifier(identifier, airport)
    filename = _field(row, "input_filename")
    if filename:
        return _humanize_case_identifier(Path(filename).stem, airport)
    return "Not recorded"


def load_runs(ledger_path: Path) -> list[dict[str, object]]:
    """Read the append-only TSV and retain missing legacy scenario fields as unknown."""
    with Path(ledger_path).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        missing = REQUIRED_LEDGER_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Runtime ledger is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    runs: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=1):
        moment = _timestamp(row.get("timestamp_utc"))
        design_id = _field(row, "design_ruleset")
        primary_id = _field(row, "baseline_ols_ruleset") or design_id
        comparison_id = _field(row, "comparison_ols_ruleset")
        primary = _ruleset_name(primary_id, _field(row, "baseline_ols_ruleset_label"))
        comparison = (
            _ruleset_name(comparison_id, _field(row, "comparison_ols_ruleset_label"))
            if comparison_id
            else "No comparison"
        )
        runway_count = _integer(row.get("runway_count"))
        runway_configuration = _runway_scenario(
            row.get("runway_configuration"),
            runway_count,
        )
        fingerprint = _field(row, "input_fingerprint")
        airport_text = _field(row, "airport")
        airport = (
            airport_text.upper()
            if len(airport_text) == 4 and airport_text.isalpha()
            else airport_text or "Not recorded"
        )
        test_case = _plain_case_name(row, airport)
        legacy_setup = "|".join(
            [
                test_case,
                airport,
                str(runway_count or "unknown"),
                runway_configuration or "unknown",
                design_id,
                primary_id,
                comparison_id,
            ]
        )
        runs.append(
            {
                "id": row_number,
                "timestamp": _iso(moment),
                "airport": airport,
                "testCase": test_case,
                "testCaseRecorded": test_case != "Not recorded",
                "inputFilename": _field(row, "input_filename") or "Not recorded",
                "runwayCount": runway_count,
                "runwayCountLabel": str(runway_count) if runway_count is not None else "Not recorded",
                "scenario": runway_configuration.title() if runway_configuration else "Not recorded",
                "builtTo": _ruleset_name(design_id, _field(row, "design_ruleset_label")),
                "primaryOls": primary,
                "comparedWith": comparison,
                "olsSelection": primary + (f" vs {comparison}" if comparison_id else " only"),
                "elapsed": _float(row.get("elapsed_seconds")),
                "status": (_field(row, "status") or "unknown").title(),
                "runBy": _run_source(_field(row, "agent")),
                "agent": _field(row, "agent") or "Not recorded",
                "commit": (_field(row, "commit_ref") or "unknown")[:7],
                "commitFull": _field(row, "commit_ref") or "unknown",
                "dirty": _bool(row.get("working_tree_dirty")),
                "fingerprint": fingerprint or "Not recorded",
                "exactSetup": f"exact:{fingerprint}" if fingerprint else f"legacy:{legacy_setup}",
                "exactSetupRecorded": bool(fingerprint),
                "layers": _integer(row.get("layers_created")),
                "features": _integer(row.get("features_created")),
            }
        )
    return sorted(runs, key=lambda item: (str(item["timestamp"]), int(item["id"])))


def recent_window_change(runs: Sequence[Mapping[str, object]]) -> dict[str, Optional[float]]:
    """Compare the latest five usable runs with the preceding five."""
    values = [
        float(run["elapsed"])
        for run in runs
        if str(run.get("status", "")).lower() == "completed" and run.get("elapsed") is not None
    ]
    if len(values) < 10:
        return {"recent_median": None, "previous_median": None, "change": None}
    recent = statistics.median(values[-5:])
    previous = statistics.median(values[-10:-5])
    change = None if previous == 0 else (recent - previous) / previous
    return {
        "recent_median": round(recent, 3),
        "previous_median": round(previous, 3),
        "change": change,
    }


def _json_for_html(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>AeroSense runtime explorer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3f5f7;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #687582;
      --line: #d9e0e6;
      --blue: #1769aa;
      --blue-soft: #e9f3fb;
      --green: #177245;
      --green-soft: #e8f6ef;
      --red: #b42318;
      --red-soft: #fdecea;
      --amber: #8a5a00;
      --amber-soft: #fff3d5;
      --shadow: 0 1px 2px rgba(31, 41, 51, .07);
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    button, select { font: inherit; }
    .page { width: min(1500px, 100%); margin: 0 auto; padding: 22px; }
    .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: clamp(24px, 3vw, 34px); line-height: 1.15; }
    .subtitle { margin: 6px 0 0; color: var(--muted); font-size: 15px; }
    .actions { display: flex; gap: 8px; flex: 0 0 auto; }
    .button { min-height: 38px; padding: 8px 13px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel); color: var(--ink); cursor: pointer; box-shadow: var(--shadow); }
    .button:hover { border-color: var(--blue); }
    .panel { margin-bottom: 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); box-shadow: var(--shadow); }
    .panel-pad { padding: 16px; }
    .filters { display: grid; grid-template-columns: repeat(8, minmax(125px, 1fr)); gap: 10px; }
    .filter label { display: block; margin-bottom: 5px; color: var(--muted); font-size: 12px; font-weight: 650; }
    select { width: 100%; min-height: 38px; padding: 7px 28px 7px 9px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--ink); }
    select:focus, button:focus { outline: 3px solid rgba(23, 105, 170, .18); outline-offset: 1px; }
    .filter-status { display: flex; justify-content: space-between; gap: 12px; margin-top: 12px; color: var(--muted); }
    .notice { margin-top: 12px; padding: 9px 11px; border-radius: 7px; background: var(--amber-soft); color: #674400; font-size: 13px; }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
    .kpi { min-height: 118px; padding: 15px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); box-shadow: var(--shadow); }
    .kpi-label { color: var(--muted); font-size: 12px; font-weight: 650; }
    .kpi-value { margin-top: 5px; font-size: clamp(23px, 3vw, 32px); font-weight: 700; font-variant-numeric: tabular-nums; }
    .kpi-note { margin-top: 4px; color: var(--muted); font-size: 12px; }
    .positive { color: var(--green) !important; }
    .negative { color: var(--red) !important; }
    .section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; padding: 15px 16px 0; }
    h2 { margin: 0; font-size: 18px; }
    .section-note { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
    .ticker { display: grid; grid-template-columns: repeat(5, minmax(180px, 1fr)); gap: 10px; padding: 14px 16px 16px; overflow-x: auto; }
    .run-card { min-width: 180px; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfd; }
    .run-card-top { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 11px; }
    .run-time-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .run-time { margin: 6px 0 2px; font-size: 25px; font-weight: 700; font-variant-numeric: tabular-nums; }
    .run-owner { display: inline-flex; align-items: center; padding: 3px 7px; border-radius: 999px; background: var(--blue-soft); color: var(--blue); font-size: 11px; font-weight: 700; }
    .run-owner.user { background: var(--green-soft); color: var(--green); }
    .run-case { min-height: 40px; font-weight: 650; }
    .run-meta { color: var(--muted); font-size: 12px; }
    .delta { display: inline-block; margin-top: 8px; padding: 3px 7px; border-radius: 999px; background: var(--blue-soft); color: var(--blue); font-size: 11px; font-weight: 650; }
    .delta.positive { background: var(--green-soft); }
    .delta.negative { background: var(--red-soft); }
    .chart-wrap { padding: 10px 16px 16px; }
    #trendChart { display: block; width: 100%; height: 310px; }
    .chart-empty { display: grid; height: 250px; place-items: center; color: var(--muted); }
    .pivot-controls { display: flex; align-items: end; gap: 10px; }
    .pivot-controls .filter { min-width: 175px; }
    .table-wrap { overflow: auto; padding: 12px 16px 16px; }
    table { width: 100%; border-collapse: collapse; white-space: nowrap; }
    th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; }
    th { position: sticky; top: 0; background: var(--panel); color: var(--muted); font-size: 12px; }
    th button { padding: 0; border: 0; background: transparent; color: inherit; font-weight: 650; cursor: pointer; }
    td.number, th.number { text-align: right; font-variant-numeric: tabular-nums; }
    .quality { display: inline-flex; padding: 3px 7px; border-radius: 999px; font-size: 11px; font-weight: 650; }
    .quality.exact { background: var(--green-soft); color: var(--green); }
    .quality.rough { background: var(--amber-soft); color: var(--amber); }
    .empty-row { padding: 28px 10px; color: var(--muted); text-align: center; }
    details { margin-bottom: 20px; padding: 0 3px; color: var(--muted); }
    details summary { cursor: pointer; color: var(--ink); font-weight: 650; }
    details p { max-width: 900px; }
    code { padding: 1px 4px; border-radius: 4px; background: #e9edf1; }
    @media (max-width: 1150px) { .filters { grid-template-columns: repeat(4, 1fr); } .ticker { grid-template-columns: repeat(5, 220px); } }
    @media (max-width: 760px) {
      .page { padding: 14px; }
      .topbar { display: block; }
      .actions { margin-top: 12px; }
      .filters { grid-template-columns: repeat(2, 1fr); }
      .kpis { grid-template-columns: repeat(2, 1fr); }
      .section-head { align-items: flex-start; flex-direction: column; }
      .pivot-controls { width: 100%; }
      .pivot-controls .filter { min-width: 0; flex: 1; }
    }
    @media (max-width: 440px) { .filters, .kpis { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main class="page">
    <div class="topbar">
      <div>
        <h1>AeroSense runtime explorer</h1>
        <p class="subtitle">Filter the test conditions, then see whether matching runs are getting faster or slower.</p>
      </div>
      <div class="actions">
        <button class="button" id="clearFilters" type="button">Clear filters</button>
        <button class="button" id="refreshPage" type="button">Refresh data</button>
      </div>
    </div>

    <section class="panel panel-pad" aria-label="Dashboard filters">
      <div class="filters">
        <div class="filter"><label for="filterTestCase">Test case</label><select id="filterTestCase" data-field="testCase"></select></div>
        <div class="filter"><label for="filterAirport">Airport</label><select id="filterAirport" data-field="airport"></select></div>
        <div class="filter"><label for="filterRunways">Runways</label><select id="filterRunways" data-field="runwayCountLabel"></select></div>
        <div class="filter"><label for="filterScenario">Scenario</label><select id="filterScenario" data-field="scenario"></select></div>
        <div class="filter"><label for="filterBuiltTo">Built to</label><select id="filterBuiltTo" data-field="builtTo"></select></div>
        <div class="filter"><label for="filterPrimary">Primary OLS</label><select id="filterPrimary" data-field="primaryOls"></select></div>
        <div class="filter"><label for="filterComparison">Compared with</label><select id="filterComparison" data-field="comparedWith"></select></div>
        <div class="filter"><label for="filterRunBy">Run by</label><select id="filterRunBy" data-field="runBy"></select></div>
      </div>
      <div class="filter-status"><span id="filterCount"></span><span id="generatedAt">Built __GENERATED_AT__</span></div>
      <div class="notice" id="comparisonNotice"></div>
    </section>

    <section class="kpis" aria-label="Runtime summary">
      <article class="kpi"><div class="kpi-label">Matching runs</div><div class="kpi-value" id="kpiRuns">—</div><div class="kpi-note" id="kpiRunsNote"></div></article>
      <article class="kpi"><div class="kpi-label">Typical run time</div><div class="kpi-value" id="kpiMedian">—</div><div class="kpi-note">Median of completed matching runs</div></article>
      <article class="kpi"><div class="kpi-label">Last 5 vs previous 5</div><div class="kpi-value" id="kpiChange">—</div><div class="kpi-note" id="kpiChangeNote"></div></article>
      <article class="kpi"><div class="kpi-label">Latest matching run</div><div class="kpi-value" id="kpiLatest">—</div><div class="kpi-note" id="kpiLatestNote"></div></article>
    </section>

    <section class="panel">
      <div class="section-head"><div><h2>Last 5 matching runs</h2><p class="section-note">Newest first. The change badge compares with the previous run using the same recorded setup.</p></div></div>
      <div class="ticker" id="lastFive"></div>
    </section>

    <section class="panel">
      <div class="section-head"><div><h2>Run time over time</h2><p class="section-note">Lower is faster. Each dot is one completed run after your filters are applied.</p></div></div>
      <div class="chart-wrap" id="trendWrap"><svg id="trendChart" role="img" aria-label="Runtime trend"></svg></div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div><h2>Pivot summary</h2><p class="section-note">Choose how to group the filtered runs; click a column heading to sort.</p></div>
        <div class="pivot-controls">
          <div class="filter"><label for="groupPrimary">Group rows by</label><select id="groupPrimary"></select></div>
          <div class="filter"><label for="groupSecondary">Then by</label><select id="groupSecondary"></select></div>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th><button type="button" data-sort="group">Group</button></th>
            <th class="number"><button type="button" data-sort="runs">Runs</button></th>
            <th class="number"><button type="button" data-sort="median">Typical</button></th>
            <th class="number"><button type="button" data-sort="latest">Latest</button></th>
            <th class="number"><button type="button" data-sort="recent">Last 5</button></th>
            <th class="number"><button type="button" data-sort="change">Change</button></th>
            <th><button type="button" data-sort="quality">Comparison quality</button></th>
          </tr></thead>
          <tbody id="pivotBody"></tbody>
        </table>
      </div>
    </section>

    <details>
      <summary>How to read this</summary>
      <p>For a fair speed comparison, filter to one test case and one OLS selection. “Typical” means the median, so one unusually slow run does not dominate. “Last 5 vs previous 5” compares two five-run windows.</p>
      <p>Older runtime rows did not record the test-case file, runway count, layout, or exact parameters. They remain visible for airport and OLS exploration, but are marked <strong>rough</strong>. New rows store an exact setup code and are marked <strong>exact</strong>.</p>
    </details>
  </main>

  <script id="runData" type="application/json">__RUN_DATA__</script>
  <script>
  (() => {
    const allRuns = JSON.parse(document.getElementById('runData').textContent);
    const filterElements = [...document.querySelectorAll('select[data-field]')];
    const groupOptions = [
      ['testCase', 'Test case'], ['airport', 'Airport'], ['runwayCountLabel', 'Runways'],
      ['scenario', 'Scenario'], ['builtTo', 'Built to'], ['primaryOls', 'Primary OLS'],
      ['comparedWith', 'Compared with'], ['runBy', 'Run by'], ['commit', 'Commit']
    ];
    const groupPrimary = document.getElementById('groupPrimary');
    const groupSecondary = document.getElementById('groupSecondary');
    let sortState = { key: 'runs', direction: -1 };

    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    const median = values => {
      const sorted = values.filter(Number.isFinite).slice().sort((a, b) => a - b);
      if (!sorted.length) return null;
      const middle = Math.floor(sorted.length / 2);
      return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    };
    const seconds = value => Number.isFinite(value) ? `${value.toFixed(value >= 100 ? 0 : 1)}s` : '—';
    const percentChange = (recent, previous) => Number.isFinite(recent) && Number.isFinite(previous) && previous !== 0 ? (recent - previous) / previous : null;
    const directionText = change => {
      if (!Number.isFinite(change)) return 'Not enough runs';
      if (Math.abs(change) < .02) return 'About the same';
      return `${Math.abs(change * 100).toFixed(0)}% ${change < 0 ? 'faster' : 'slower'}`;
    };
    const dateLabel = iso => new Intl.DateTimeFormat(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}).format(new Date(iso));
    const shortDate = iso => new Intl.DateTimeFormat(undefined, {month:'short', day:'numeric'}).format(new Date(iso));
    const completed = runs => runs.filter(run => run.status === 'Completed' && Number.isFinite(run.elapsed));

    function uniqueValues(field) {
      return [...new Set(allRuns.map(run => String(run[field] ?? 'Not recorded')))].sort((a, b) => {
        if (a === 'Not recorded') return 1;
        if (b === 'Not recorded') return -1;
        return a.localeCompare(b, undefined, {numeric: true});
      });
    }

    function populateFilters() {
      filterElements.forEach(select => {
        const values = uniqueValues(select.dataset.field);
        select.innerHTML = '<option value="">All</option>' + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
        select.addEventListener('change', render);
      });
      groupPrimary.innerHTML = groupOptions.map(([field, label]) => `<option value="${field}">${label}</option>`).join('');
      groupPrimary.value = 'airport';
      refreshSecondaryOptions();
      groupSecondary.value = 'primaryOls';
      groupPrimary.addEventListener('change', () => { refreshSecondaryOptions(); renderPivot(filteredRuns()); });
      groupSecondary.addEventListener('change', () => renderPivot(filteredRuns()));
    }

    function refreshSecondaryOptions() {
      const current = groupSecondary.value;
      groupSecondary.innerHTML = '<option value="">None</option>' + groupOptions
        .filter(([field]) => field !== groupPrimary.value)
        .map(([field, label]) => `<option value="${field}">${label}</option>`).join('');
      if ([...groupSecondary.options].some(option => option.value === current)) groupSecondary.value = current;
    }

    function filteredRuns() {
      return allRuns.filter(run => filterElements.every(select => !select.value || String(run[select.dataset.field]) === select.value));
    }

    function comparisonQuality(runs) {
      const setups = new Set(runs.map(run => run.exactSetup));
      const allExact = runs.length > 0 && runs.every(run => run.exactSetupRecorded);
      if (allExact && setups.size === 1) {
        const owners = new Set(allRuns.filter(run => run.exactSetup === runs[0].exactSetup).map(run => run.runBy));
        const shared = owners.has('User') && owners.has('Codex');
        return {
          label: shared ? 'Exact · User + Codex' : `Exact · ${[...owners][0] || 'one runner'} only`,
          kind: 'exact', shared
        };
      }
      if (setups.size === 1) return {label: 'Rough: old inputs missing', kind: 'rough'};
      return {label: 'Mixed setups: filter further', kind: 'rough'};
    }

    function renderKpis(runs) {
      const usable = completed(runs);
      const typical = median(usable.map(run => run.elapsed));
      const recent = usable.slice(-5);
      const previous = usable.slice(-10, -5);
      const recentMedian = recent.length === 5 ? median(recent.map(run => run.elapsed)) : null;
      const previousMedian = previous.length === 5 ? median(previous.map(run => run.elapsed)) : null;
      const change = percentChange(recentMedian, previousMedian);
      const latest = usable.at(-1);
      const quality = comparisonQuality(usable);

      document.getElementById('kpiRuns').textContent = runs.length;
      document.getElementById('kpiRunsNote').textContent = `${usable.length} completed`;
      document.getElementById('kpiMedian').textContent = seconds(typical);
      const changeElement = document.getElementById('kpiChange');
      const mixedSetups = quality.label.startsWith('Mixed');
      changeElement.textContent = mixedSetups ? 'Filter further' : `${quality.kind === 'rough' && Number.isFinite(change) ? '~' : ''}${directionText(change)}`;
      changeElement.className = `kpi-value ${!mixedSetups && Number.isFinite(change) ? (change < -.02 ? 'positive' : change > .02 ? 'negative' : '') : ''}`;
      document.getElementById('kpiChangeNote').textContent = mixedSetups
        ? 'Select one test setup before comparing speed'
        : Number.isFinite(change)
          ? `${seconds(recentMedian)} recently vs ${seconds(previousMedian)} before · ${quality.label}`
          : `Needs 10 completed matching runs · ${quality.label}`;
      document.getElementById('kpiLatest').textContent = latest ? seconds(latest.elapsed) : '—';
      document.getElementById('kpiLatestNote').textContent = latest ? `${latest.airport} · ${dateLabel(latest.timestamp)} · ${latest.commit}` : 'No completed matching run';

      document.getElementById('comparisonNotice').textContent = quality.kind === 'exact'
        ? quality.shared
          ? 'This is an exact shared setup: User and Codex ran identical input parameters.'
          : `This is an exact input setup, but only ${quality.label.includes('Codex') ? 'Codex' : 'User'} has run it so far.`
        : quality.label.startsWith('Mixed')
          ? 'This view mixes input setups. Use the slicers to narrow it before treating faster/slower as a development result.'
          : 'This is a rough historical comparison: older rows did not record the exact input file and parameters.';
    }

    function priorComparable(run, runs) {
      const earlier = completed(runs).filter(candidate => candidate.timestamp < run.timestamp && candidate.exactSetup === run.exactSetup);
      return earlier.at(-1) || null;
    }

    function renderLastFive(runs) {
      const latest = runs.slice().sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 5);
      const host = document.getElementById('lastFive');
      if (!latest.length) {
        host.innerHTML = '<div class="empty-row">No runs match these filters.</div>';
        return;
      }
      host.innerHTML = latest.map(run => {
        const prior = priorComparable(run, runs);
        const change = prior && Number.isFinite(run.elapsed) ? percentChange(run.elapsed, prior.elapsed) : null;
        const approximate = !run.exactSetupRecorded && Number.isFinite(change) ? '~' : '';
        const deltaClass = Number.isFinite(change) ? (change < -.02 ? 'positive' : change > .02 ? 'negative' : '') : '';
        const delta = Number.isFinite(change) ? `${approximate}${directionText(change)} vs prior` : 'No comparable prior run';
        const runway = run.runwayCount ? `${run.runwayCount} · ${run.scenario}` : run.scenario;
        return `<article class="run-card">
          <div class="run-card-top"><span>${escapeHtml(dateLabel(run.timestamp))}</span><span>${escapeHtml(run.status)}</span></div>
          <div class="run-time-row"><div class="run-time">${escapeHtml(seconds(run.elapsed))}</div><span class="run-owner ${run.runBy === 'User' ? 'user' : 'codex'}">${escapeHtml(run.runBy)}</span></div>
          <div class="run-case">${escapeHtml(run.testCase)}</div>
          <div class="run-meta">${escapeHtml(run.airport)} · ${escapeHtml(runway)}</div>
          <div class="run-meta">${escapeHtml(run.olsSelection)}</div>
          <span class="delta ${deltaClass}">${escapeHtml(delta)}</span>
        </article>`;
      }).join('');
    }

    function renderTrend(runs) {
      const usable = completed(runs);
      const svg = document.getElementById('trendChart');
      if (!usable.length) {
        svg.outerHTML = '<div class="chart-empty" id="trendChart">No completed runtimes match these filters.</div>';
        return;
      }
      if (svg.tagName !== 'svg') {
        svg.outerHTML = '<svg id="trendChart" role="img" aria-label="Runtime trend"></svg>';
      }
      const chart = document.getElementById('trendChart');
      const width = 1000, height = 310, left = 58, right = 18, top = 18, bottom = 45;
      const innerWidth = width - left - right, innerHeight = height - top - bottom;
      const times = usable.map(run => new Date(run.timestamp).getTime());
      const minTime = Math.min(...times), maxTime = Math.max(...times);
      const rawMin = Math.min(...usable.map(run => run.elapsed));
      const rawMax = Math.max(...usable.map(run => run.elapsed));
      const padding = Math.max((rawMax - rawMin) * .12, 1);
      const minY = Math.max(0, rawMin - padding), maxY = rawMax + padding;
      const x = run => left + ((new Date(run.timestamp).getTime() - minTime) / (maxTime - minTime || 1)) * innerWidth;
      const y = run => top + (1 - (run.elapsed - minY) / (maxY - minY || 1)) * innerHeight;
      const palette = ['#1769aa','#177245','#9b51a0','#c45d12','#5b6573','#b42318','#00838f','#6b5b95'];
      const seriesKeys = [...new Set(usable.map(run => run.exactSetup))];
      const color = key => palette[Math.max(0, seriesKeys.indexOf(key)) % palette.length];
      let parts = [`<rect x="0" y="0" width="${width}" height="${height}" fill="white"/>`];
      for (let tick = 0; tick <= 4; tick++) {
        const value = minY + (maxY - minY) * tick / 4;
        const tickY = top + innerHeight - innerHeight * tick / 4;
        parts.push(`<line x1="${left}" y1="${tickY}" x2="${width-right}" y2="${tickY}" stroke="#e2e7eb"/>`);
        parts.push(`<text x="${left-9}" y="${tickY+4}" text-anchor="end" fill="#687582" font-size="11">${value.toFixed(value >= 100 ? 0 : 1)}s</text>`);
      }
      seriesKeys.forEach(key => {
        const series = usable.filter(run => run.exactSetup === key);
        if (series.length > 1) {
          parts.push(`<polyline fill="none" stroke="${color(key)}" stroke-width="2" opacity=".75" points="${series.map(run => `${x(run)},${y(run)}`).join(' ')}"/>`);
        }
      });
      usable.forEach(run => parts.push(`<circle cx="${x(run)}" cy="${y(run)}" r="4" fill="${color(run.exactSetup)}" stroke="white" stroke-width="1.5"><title>${escapeHtml(`${run.testCase} · ${run.airport} · ${seconds(run.elapsed)} · ${dateLabel(run.timestamp)}`)}</title></circle>`));
      const labels = [usable[0], usable[Math.floor((usable.length - 1) / 2)], usable.at(-1)];
      labels.forEach((run, index) => parts.push(`<text x="${x(run)}" y="${height-16}" text-anchor="${index === 0 ? 'start' : index === 2 ? 'end' : 'middle'}" fill="#687582" font-size="11">${escapeHtml(shortDate(run.timestamp))}</text>`));
      chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
      chart.innerHTML = parts.join('');
    }

    function pivotRows(runs) {
      const primary = groupPrimary.value;
      const secondary = groupSecondary.value;
      const groups = new Map();
      runs.forEach(run => {
        const values = [String(run[primary] ?? 'Not recorded')];
        if (secondary) values.push(String(run[secondary] ?? 'Not recorded'));
        const key = values.join('\u0000');
        if (!groups.has(key)) groups.set(key, {values, runs: []});
        groups.get(key).runs.push(run);
      });
      return [...groups.values()].map(group => {
        const usable = completed(group.runs);
        const values = usable.map(run => run.elapsed);
        const recentValues = values.slice(-5);
        const previousValues = values.slice(-10, -5);
        const recent = recentValues.length ? median(recentValues) : null;
        const previous = previousValues.length === 5 ? median(previousValues) : null;
        const quality = comparisonQuality(usable);
        const mixedSetups = quality.label.startsWith('Mixed');
        return {
          group: group.values.join(' · '), runs: group.runs.length,
          median: median(values), latest: usable.at(-1)?.elapsed ?? null,
          recent, change: mixedSetups ? null : percentChange(recent, previous), quality: quality.label,
          qualityKind: quality.kind
        };
      });
    }

    function renderPivot(runs) {
      const rows = pivotRows(runs);
      const multiplier = sortState.direction;
      rows.sort((a, b) => {
        const left = a[sortState.key], right = b[sortState.key];
        if (left == null) return 1;
        if (right == null) return -1;
        return (typeof left === 'number' ? left - right : String(left).localeCompare(String(right), undefined, {numeric:true})) * multiplier;
      });
      const body = document.getElementById('pivotBody');
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7" class="empty-row">No runs match these filters.</td></tr>';
        return;
      }
      body.innerHTML = rows.map(row => `<tr>
        <td>${escapeHtml(row.group)}</td><td class="number">${row.runs}</td>
        <td class="number">${escapeHtml(seconds(row.median))}</td><td class="number">${escapeHtml(seconds(row.latest))}</td>
        <td class="number">${escapeHtml(seconds(row.recent))}</td>
        <td class="number ${Number.isFinite(row.change) ? (row.change < -.02 ? 'positive' : row.change > .02 ? 'negative' : '') : ''}">${escapeHtml(Number.isFinite(row.change) ? directionText(row.change) : '—')}</td>
        <td><span class="quality ${row.qualityKind}">${escapeHtml(row.quality)}</span></td>
      </tr>`).join('');
    }

    function render() {
      const runs = filteredRuns();
      document.getElementById('filterCount').textContent = `${runs.length} of ${allRuns.length} runs shown`;
      renderKpis(runs);
      renderLastFive(runs);
      renderTrend(runs);
      renderPivot(runs);
    }

    document.getElementById('clearFilters').addEventListener('click', () => { filterElements.forEach(select => select.value = ''); render(); });
    document.getElementById('refreshPage').addEventListener('click', () => location.reload());
    document.querySelectorAll('[data-sort]').forEach(button => button.addEventListener('click', () => {
      const key = button.dataset.sort;
      sortState = sortState.key === key ? {key, direction: sortState.direction * -1} : {key, direction: key === 'group' || key === 'quality' ? 1 : -1};
      renderPivot(filteredRuns());
    }));
    populateFilters();
    render();
  })();
  </script>
</body>
</html>
"""


def build_html(
    runs: Sequence[Mapping[str, object]],
    *,
    generated_at: Optional[datetime] = None,
) -> str:
    if not runs:
        raise ValueError("Runtime ledger contains no runs")
    generated = generated_at or datetime.now(timezone.utc)
    return (
        HTML_TEMPLATE.replace("__RUN_DATA__", _json_for_html(list(runs)))
        .replace("__GENERATED_AT__", _iso(generated))
    )


def rebuild(ledger_path: Path, output_path: Path) -> list[dict[str, object]]:
    runs = load_runs(ledger_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(runs), encoding="utf-8")
    return runs


class _RefreshingDashboardHandler(SimpleHTTPRequestHandler):
    ledger_path: Path
    output_path: Path
    build_lock = threading.Lock()

    def _refresh_if_needed(self) -> None:
        if self.output_path.exists() and self.output_path.stat().st_mtime >= self.ledger_path.stat().st_mtime:
            return
        with self.build_lock:
            if self.output_path.exists() and self.output_path.stat().st_mtime >= self.ledger_path.stat().st_mtime:
                return
            rebuild(self.ledger_path, self.output_path)

    def do_GET(self) -> None:  # noqa: N802 - inherited HTTP method name
        if self.path in {"/", "/index.html"}:
            try:
                self._refresh_if_needed()
            except Exception as exc:  # pragma: no cover - interactive fallback
                self.log_error("Dashboard refresh failed: %s", exc)
        super().do_GET()


def serve(ledger_path: Path, output_path: Path, *, port: int) -> None:
    runs = rebuild(ledger_path, output_path)
    handler = type(
        "RefreshingDashboardHandler",
        (_RefreshingDashboardHandler,),
        {"ledger_path": ledger_path, "output_path": output_path},
    )
    server = None
    selected_port = port
    for candidate_port in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(
                ("127.0.0.1", candidate_port),
                partial(handler, directory=str(DASHBOARD_DIR)),
            )
            selected_port = candidate_port
            break
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    if server is None:
        raise OSError(f"No free dashboard port found from {port} to {port + 9}")
    print(f"AeroSense runtime explorer: http://127.0.0.1:{selected_port}")
    print(f"Loaded {len(runs)} runtime rows. Refresh the page after new tests finish.")
    print("Stop the server with Ctrl+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="Runtime TSV path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Generated HTML path")
    parser.add_argument("--serve", action="store_true", help="Build and serve on localhost")
    parser.add_argument("--port", type=int, default=8765, help="Local server port (default: 8765)")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.serve:
        serve(args.ledger, args.output, port=args.port)
        return 0
    runs = rebuild(args.ledger, args.output)
    print(f"Built {args.output} from {len(runs)} runtime rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
