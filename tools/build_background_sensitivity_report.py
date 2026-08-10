#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TARGETS = [
    {"id": "centerline_length", "label": "Centerline length", "unit": "mm"},
    {"id": "mean_width", "label": "Mean width", "unit": "mm"},
    {"id": "max_width", "label": "Maximum width", "unit": "mm"},
    {"id": "crack_area", "label": "Crack area", "unit": "mm^2"},
]


def main() -> int:
    args = parse_args()
    predictions = read_csv(args.results_dir / "all_predictions.csv")
    for record in predictions:
        record["report_image_path"] = (
            f"renders/full_study/{record['source']}/{record['defect_seed']}/{record['output_seed']}.jpg"
        )
    study_dir = args.results_dir.parents[1]
    missing_images = [
        record["report_image_path"]
        for record in predictions
        if not (study_dir / record["report_image_path"]).is_file()
    ]
    if missing_images:
        raise FileNotFoundError(f"Missing {len(missing_images)} report images; first: {missing_images[0]}")
    pooled = read_csv(args.results_dir / "pooled_summary.csv")
    groups = read_csv(args.results_dir / "per_geometry_summary.csv")
    backgrounds = read_csv(args.results_dir / "per_background_summary.csv")
    summary = json.loads((args.results_dir / "summary.json").read_text(encoding="utf-8"))

    payload = {
        "targets": TARGETS,
        "summary": summary,
        "pooled": pooled,
        "groups": groups,
        "backgrounds": backgrounds,
        "records": predictions,
        "benchmark_mare_range": [2.04, 2.54],
        "image_prefix": "../../",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(payload), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "records": len(predictions)}, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the interactive MetroDef3D background sensitivity report.")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("studies/fixed_geometry_background_sensitivity/results/full_study"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("studies/fixed_geometry_background_sensitivity/results/full_study/report.html"),
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [convert_row(row) for row in csv.DictReader(handle)]


def convert_row(row: dict[str, str]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, value in row.items():
        if value == "":
            converted[key] = ""
            continue
        try:
            converted[key] = int(value)
            continue
        except ValueError:
            pass
        try:
            converted[key] = float(value)
            continue
        except ValueError:
            converted[key] = value
    return converted


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MetroDef3D Background Sensitivity Study</title>
<style>
:root {{
  color-scheme: light;
  --bg: #eef1f3;
  --surface: #ffffff;
  --text: #172027;
  --muted: #5d6972;
  --line: #cbd2d7;
  --line-dark: #8e999f;
  --procedural: #227f78;
  --procedural-soft: #d8eeeb;
  --photographic: #b86a16;
  --photographic-soft: #f7e7d3;
  --danger: #a23b3b;
  --danger-soft: #f7dddd;
  --focus: #1769aa;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
button, select {{ font: inherit; }}
button:focus-visible, select:focus-visible, [tabindex]:focus-visible {{ outline: 3px solid color-mix(in srgb, var(--focus) 45%, transparent); outline-offset: 2px; }}
.shell {{ min-height: 100vh; }}
.topbar {{ background: #202a31; color: white; border-bottom: 4px solid var(--procedural); }}
.topbar-inner {{ max-width: 1480px; margin: 0 auto; padding: 20px 28px 16px; }}
h1 {{ margin: 0; font-size: 24px; line-height: 1.2; letter-spacing: 0; }}
.subtitle {{ margin: 5px 0 0; color: #d7dde1; max-width: 980px; }}
.tabs {{ display: flex; gap: 2px; margin-top: 16px; }}
.tab {{ border: 0; border-bottom: 3px solid transparent; background: transparent; color: #d7dde1; padding: 8px 13px 7px; cursor: pointer; }}
.tab[aria-selected="true"] {{ color: white; border-bottom-color: #f0a34c; }}
main {{ max-width: 1480px; margin: 0 auto; padding: 22px 28px 48px; }}
.view[hidden] {{ display: none; }}
.metric-strip {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }}
.metric {{ min-height: 84px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 13px 15px; }}
.metric strong {{ display: block; font-size: 24px; line-height: 1.1; font-variant-numeric: tabular-nums; }}
.metric span {{ color: var(--muted); }}
.section {{ background: var(--surface); border: 1px solid var(--line); border-radius: 6px; margin-top: 14px; overflow: hidden; }}
.section-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding: 14px 16px 10px; border-bottom: 1px solid var(--line); }}
h2, h3 {{ margin: 0; letter-spacing: 0; }}
h2 {{ font-size: 17px; }}
h3 {{ font-size: 15px; }}
.section-head p {{ margin: 0; color: var(--muted); }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 9px 11px; border-bottom: 1px solid #e2e6e9; text-align: right; white-space: nowrap; }}
th {{ color: #46525a; background: #f6f7f8; font-size: 12px; font-weight: 700; }}
th:first-child, td:first-child {{ text-align: left; }}
tbody tr:last-child td {{ border-bottom: 0; }}
.source {{ display: inline-flex; align-items: center; gap: 7px; font-weight: 700; }}
.source::before {{ content: ""; width: 9px; height: 9px; border-radius: 50%; background: var(--procedural); }}
.source.photographic::before {{ background: var(--photographic); }}
.bar-cell {{ min-width: 150px; }}
.bar-track {{ position: relative; height: 7px; margin-top: 4px; background: #e4e8ea; overflow: hidden; }}
.bar-fill {{ height: 100%; background: var(--procedural); }}
.bar-fill.photographic {{ background: var(--photographic); }}
.finding-band {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px solid var(--line); }}
.finding {{ padding: 14px 16px; border-right: 1px solid var(--line); }}
.finding:last-child {{ border-right: 0; }}
.finding b {{ display: block; margin-bottom: 3px; }}
.finding p {{ margin: 0; color: var(--muted); }}
.detail-toolbar {{ display: grid; grid-template-columns: minmax(190px, 260px) 1fr auto; align-items: end; gap: 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; }}
.field label {{ display: block; color: var(--muted); font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
select {{ width: 100%; height: 38px; border: 1px solid var(--line-dark); border-radius: 4px; background: white; color: var(--text); padding: 0 34px 0 9px; }}
.record-title {{ min-width: 0; }}
.record-title strong {{ display: block; font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.record-title span {{ color: var(--muted); }}
.nav-buttons {{ display: flex; gap: 6px; }}
.icon-button {{ width: 38px; height: 38px; border: 1px solid var(--line-dark); border-radius: 4px; background: white; color: var(--text); font-size: 20px; line-height: 1; cursor: pointer; }}
.icon-button:hover {{ background: #f0f3f4; }}
.seed-summary {{ margin-top: 14px; }}
.record-layout {{ display: grid; grid-template-columns: minmax(420px, 0.95fr) minmax(560px, 1.25fr); gap: 14px; margin-top: 14px; }}
.image-panel, .measure-panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }}
.image-stage {{ display: grid; place-items: center; background: #151b1f; aspect-ratio: 1 / 1; }}
.image-stage img {{ width: 100%; height: 100%; display: block; object-fit: contain; }}
.image-meta {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border-top: 1px solid var(--line); }}
.badge {{ display: inline-flex; align-items: center; min-height: 25px; border-radius: 4px; padding: 3px 8px; background: var(--procedural-soft); color: #155c57; font-weight: 700; }}
.badge.photographic {{ background: var(--photographic-soft); color: #8b4d0c; }}
.observation-id {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
.measure-head {{ padding: 13px 14px 10px; border-bottom: 1px solid var(--line); }}
.measure-head p {{ margin: 3px 0 0; color: var(--muted); }}
.covered {{ color: #176a4c; font-weight: 700; }}
.miss {{ color: var(--danger); font-weight: 700; background: var(--danger-soft); }}
.thumb-section {{ margin-top: 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 10px; }}
.thumb-rail {{ display: grid; grid-template-columns: repeat(12, minmax(56px, 1fr)); gap: 7px; }}
.thumb {{ position: relative; padding: 0; border: 2px solid transparent; background: #dce1e4; aspect-ratio: 1 / 1; cursor: pointer; overflow: hidden; }}
.thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.thumb.active {{ border-color: var(--focus); }}
.thumb.missed::after {{ content: ""; position: absolute; inset: 3px 3px auto auto; width: 8px; height: 8px; border-radius: 50%; background: var(--danger); box-shadow: 0 0 0 2px white; }}
.thumb-source {{ margin: 10px 2px 6px; color: var(--muted); font-size: 12px; font-weight: 700; }}
@media (max-width: 1050px) {{
  .record-layout {{ grid-template-columns: 1fr; }}
  .image-panel {{ max-width: 760px; width: 100%; justify-self: center; }}
  .thumb-rail {{ grid-template-columns: repeat(8, minmax(48px, 1fr)); }}
}}
@media (max-width: 720px) {{
  .topbar-inner, main {{ padding-left: 14px; padding-right: 14px; }}
  .metric-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .finding-band {{ grid-template-columns: 1fr; }}
  .finding {{ border-right: 0; border-bottom: 1px solid var(--line); }}
  .finding:last-child {{ border-bottom: 0; }}
  .detail-toolbar {{ grid-template-columns: 1fr auto; }}
  .field {{ grid-column: 1 / -1; }}
  .thumb-rail {{ grid-template-columns: repeat(6, minmax(42px, 1fr)); }}
}}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="topbar-inner">
      <h1>MetroDef3D Background Sensitivity Study</h1>
      <p class="subtitle">Eight fixed geometries evaluated under procedural and photographed surface variation with construction-grounded reference measurands.</p>
      <nav class="tabs" aria-label="Report views">
        <button class="tab" data-view-button="overview" aria-selected="true">Overview</button>
        <button class="tab" data-view-button="detail" aria-selected="false">Per seed</button>
      </nav>
    </div>
  </header>
  <main>
    <section class="view" id="overview-view"></section>
    <section class="view" id="detail-view" hidden>
      <div class="detail-toolbar">
        <div class="field"><label for="seed-select">Defect seed</label><select id="seed-select"></select></div>
        <div class="record-title"><strong id="record-title"></strong><span id="record-subtitle"></span></div>
        <div class="nav-buttons">
          <button class="icon-button" id="previous-record" title="Previous observation" aria-label="Previous observation">&#8592;</button>
          <button class="icon-button" id="next-record" title="Next observation" aria-label="Next observation">&#8594;</button>
        </div>
      </div>
      <div class="section seed-summary">
        <div class="section-head"><h2 id="seed-summary-title"></h2><p>Within-geometry appearance sensitivity</p></div>
        <div class="table-wrap"><table id="seed-summary-table"></table></div>
      </div>
      <div class="record-layout">
        <section class="image-panel">
          <div class="image-stage"><img id="record-image" alt="Rendered crack observation"></div>
          <div class="image-meta"><span class="badge" id="source-badge"></span><span class="observation-id" id="observation-id"></span></div>
        </section>
        <section class="measure-panel">
          <div class="measure-head"><h2>Measurement results</h2><p id="measurement-context"></p></div>
          <div class="table-wrap"><table id="measurement-table"></table></div>
        </section>
      </div>
      <section class="thumb-section" id="thumbnail-section"></section>
    </section>
  </main>
</div>
<script>
const DATA = {data};
const state = {{ view: "overview", seed: null, recordIndex: 0 }};
const targetById = Object.fromEntries(DATA.targets.map(target => [target.id, target]));
const targetOrder = Object.fromEntries(DATA.targets.map((target, index) => [target.id, index]));
const sourceOrder = {{procedural: 0, photographic: 1}};
const seeds = [...new Set(DATA.records.map(record => Number(record.defect_seed)))].sort((a, b) => a - b);
state.seed = seeds[0];

const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[character]));
const number = (value, digits = 2) => Number(value).toLocaleString(undefined, {{minimumFractionDigits: digits, maximumFractionDigits: digits}});
const percent = value => `${{number(100 * Number(value), 1)}}%`;
const sourceLabel = source => source === "procedural" ? "Procedural" : "Photographed";
const sourceClass = source => source === "photographic" ? "photographic" : "procedural";
const recordsForSeed = seed => DATA.records.filter(record => Number(record.defect_seed) === Number(seed)).sort((a, b) => {{
  return sourceOrder[a.source] - sourceOrder[b.source] || Number(a.background_index) - Number(b.background_index);
}});

function setView(view) {{
  state.view = view;
  document.querySelectorAll("[data-view-button]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.viewButton === view)));
  document.getElementById("overview-view").hidden = view !== "overview";
  document.getElementById("detail-view").hidden = view !== "detail";
  if (view === "detail") renderDetail();
}}

function renderOverview() {{
  const root = document.getElementById("overview-view");
  const pooledRows = DATA.pooled.map(row => {{
    const target = targetById[row.target];
    const range = Number(row.mean_geometry_prediction_range_percent_truth);
    const mare = Number(row.mare_percent);
    const coverage = Number(row.coverage);
    return `<tr>
      <td><span class="source ${{sourceClass(row.source)}}">${{sourceLabel(row.source)}}</span></td>
      <td>${{escapeHtml(target.label)}}</td>
      <td class="bar-cell">${{number(mare)}}%<div class="bar-track"><div class="bar-fill ${{sourceClass(row.source)}}" style="width:${{Math.min(100, mare / 5 * 100)}}%"></div></div></td>
      <td class="bar-cell">${{number(range)}}%<div class="bar-track"><div class="bar-fill ${{sourceClass(row.source)}}" style="width:${{Math.min(100, range / 16 * 100)}}%"></div></div></td>
      <td>${{percent(coverage)}} [${{percent(row.coverage_ci_low)}}, ${{percent(row.coverage_ci_high)}}]</td>
      <td>${{number(row.relative_interval_width_mean_percent)}}%</td>
    </tr>`;
  }}).join("");
  const backgroundRows = DATA.backgrounds.map(row => `<tr>
    <td>${{String(row.background_index).padStart(3, "0")}}</td>
    <td>${{number(row.across_target_mare_percent)}}%</td>
    <td class="${{Number(row.interval_miss_count) ? "miss" : "covered"}}">${{row.interval_miss_count}} / ${{row.prediction_count}}</td>
    <td>${{percent(row.interval_coverage)}}</td>
    <td>${{row.centerline_length_miss_count}}</td>
    <td>${{row.mean_width_miss_count}}</td>
    <td>${{row.max_width_miss_count}}</td>
    <td>${{row.crack_area_miss_count}}</td>
  </tr>`).join("");
  root.innerHTML = `
    <div class="metric-strip">
      <div class="metric"><strong>${{DATA.summary.total_observations}}</strong><span>Total observations</span></div>
      <div class="metric"><strong>${{DATA.summary.defect_count}}</strong><span>Fixed geometries</span></div>
      <div class="metric"><strong>${{DATA.summary.procedural_observations}}</strong><span>Procedural observations</span></div>
      <div class="metric"><strong>${{DATA.summary.photographic_observations}}</strong><span>Photographed observations</span></div>
    </div>
    <section class="section">
      <div class="section-head"><h2>Pooled comparison</h2><p>Calibrated intervals; 95% Wilson intervals for coverage</p></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Surface source</th><th>Measurand</th><th>MARE</th><th>Mean prediction range / truth</th><th>Coverage</th><th>Mean interval width / truth</th></tr></thead>
        <tbody>${{pooledRows}}</tbody>
      </table></div>
      <div class="finding-band">
        <div class="finding"><b>Independent generated-domain check</b><p>Procedural MARE was 1.13-2.63%, of the same order as the primary held-out test range of 2.04-2.54%.</p></div>
        <div class="finding"><b>Appearance transfer response</b><p>Photographed surfaces increased within-geometry prediction ranges to 6.96-14.50% of the references.</p></div>
        <div class="finding"><b>Interval response</b><p>Mean relative interval widths changed by less than 0.2 percentage points despite the larger photographed-surface variation.</p></div>
      </div>
    </section>
    <section class="section">
      <div class="section-head"><h2>Photographed background comparison</h2><p>Eight geometries and four measurands per background</p></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Background</th><th>Across-target MARE</th><th>Interval misses</th><th>Coverage</th><th>Centerline misses</th><th>Mean-width misses</th><th>Maximum-width misses</th><th>Area misses</th></tr></thead>
        <tbody>${{backgroundRows}}</tbody>
      </table></div>
    </section>`;
}}

function renderSeedOptions() {{
  document.getElementById("seed-select").innerHTML = seeds.map(seed => `<option value="${{seed}}">Seed ${{seed}}</option>`).join("");
  document.getElementById("seed-select").value = String(state.seed);
}}

function renderDetail() {{
  renderSeedOptions();
  const records = recordsForSeed(state.seed);
  if (state.recordIndex >= records.length) state.recordIndex = 0;
  const record = records[state.recordIndex];
  renderSeedSummary();
  renderRecord(record, records);
  renderThumbnails(records);
}}

function renderSeedSummary() {{
  const rows = DATA.groups.filter(row => Number(row.defect_seed) === Number(state.seed)).sort((a, b) => sourceOrder[a.source] - sourceOrder[b.source] || targetOrder[a.target] - targetOrder[b.target]);
  document.getElementById("seed-summary-title").textContent = `Seed ${{state.seed}} summary`;
  document.getElementById("seed-summary-table").innerHTML = `<thead><tr><th>Surface source</th><th>Measurand</th><th>N</th><th>MARE</th><th>Prediction range / truth</th><th>Coverage</th><th>Mean interval width</th></tr></thead><tbody>${{rows.map(row => {{
    const target = targetById[row.target];
    return `<tr><td><span class="source ${{sourceClass(row.source)}}">${{sourceLabel(row.source)}}</span></td><td>${{escapeHtml(target.label)}}</td><td>${{row.sample_count}}</td><td>${{number(row.mare_percent)}}%</td><td>${{number(row.prediction_range_percent_truth)}}%</td><td>${{row.coverage_count}}/${{row.sample_count}}</td><td>${{formatValue(row.interval_width_mean, target)}}</td></tr>`;
  }}).join("")}}</tbody>`;
}}

function renderRecord(record, records) {{
  const background = record.source === "procedural" ? `background seed ${{record.background_seed}}` : String(record.background_photo).split("/").pop();
  document.getElementById("record-title").textContent = `${{sourceLabel(record.source)}} observation ${{record.background_index}}`;
  document.getElementById("record-subtitle").textContent = `${{state.recordIndex + 1}} of ${{records.length}} | ${{background}}`;
  const image = document.getElementById("record-image");
  image.src = DATA.image_prefix + record.report_image_path;
  image.alt = `Seed ${{state.seed}}, ${{sourceLabel(record.source).toLowerCase()}} observation ${{record.background_index}}`;
  const badge = document.getElementById("source-badge");
  badge.textContent = sourceLabel(record.source);
  badge.className = `badge ${{sourceClass(record.source)}}`;
  document.getElementById("observation-id").textContent = `Output ${{record.output_seed}}`;
  document.getElementById("measurement-context").textContent = `Fixed reference geometry, ${{background}}`;
  const rows = DATA.targets.map(target => measurementRow(record, target)).join("");
  document.getElementById("measurement-table").innerHTML = `<thead><tr><th>Measurand</th><th>Reference</th><th>Prediction</th><th>Signed error</th><th>Relative error</th><th>Calibrated interval</th><th>Coverage</th></tr></thead><tbody>${{rows}}</tbody>`;
}}

function measurementRow(record, target) {{
  const id = target.id;
  const truth = Number(record[`${{id}}_actual`]);
  const prediction = Number(record[`${{id}}_mu`]);
  const lower = Number(record[`${{id}}_lower`]);
  const upper = Number(record[`${{id}}_upper`]);
  const error = prediction - truth;
  const relative = 100 * error / truth;
  const covered = Number(record[`${{id}}_covered`]) === 1;
  return `<tr>
    <td>${{escapeHtml(target.label)}}</td>
    <td>${{formatValue(truth, target)}}</td>
    <td>${{formatValue(prediction, target)}}</td>
    <td>${{signedValue(error, target)}}</td>
    <td>${{relative >= 0 ? "+" : ""}}${{number(relative)}}%</td>
    <td>[${{formatValue(lower, target)}}, ${{formatValue(upper, target)}}]</td>
    <td class="${{covered ? "covered" : "miss"}}">${{covered ? "Covered" : "Miss"}}</td>
  </tr>`;
}}

function formatValue(value, target) {{
  const digits = target.id.includes("width") ? 3 : 2;
  return `${{number(value, digits)}} ${{target.unit}}`;
}}

function signedValue(value, target) {{
  const digits = target.id.includes("width") ? 3 : 2;
  return `${{value >= 0 ? "+" : ""}}${{number(value, digits)}} ${{target.unit}}`;
}}

function renderThumbnails(records) {{
  const sources = ["procedural", "photographic"];
  document.getElementById("thumbnail-section").innerHTML = sources.map(source => {{
    const sourceRecords = records.map((record, index) => ({{record, index}})).filter(item => item.record.source === source);
    return `<div class="thumb-source">${{sourceLabel(source)}} observations</div><div class="thumb-rail">${{sourceRecords.map(item => {{
      const missed = DATA.targets.some(target => Number(item.record[`${{target.id}}_covered`]) === 0);
      return `<button class="thumb ${{item.index === state.recordIndex ? "active" : ""}} ${{missed ? "missed" : ""}}" data-record-index="${{item.index}}" title="${{sourceLabel(source)}} observation ${{item.record.background_index}}" aria-label="${{sourceLabel(source)}} observation ${{item.record.background_index}}"><img src="${{DATA.image_prefix + item.record.report_image_path}}" alt=""></button>`;
    }}).join("")}}</div>`;
  }}).join("");
  document.querySelectorAll("[data-record-index]").forEach(button => button.addEventListener("click", () => {{ state.recordIndex = Number(button.dataset.recordIndex); renderDetail(); }}));
}}

function stepRecord(delta) {{
  const count = recordsForSeed(state.seed).length;
  state.recordIndex = (state.recordIndex + delta + count) % count;
  renderDetail();
}}

function stepSeed(delta) {{
  const seedIndex = seeds.indexOf(state.seed);
  state.seed = seeds[(seedIndex + delta + seeds.length) % seeds.length];
  const count = recordsForSeed(state.seed).length;
  state.recordIndex = Math.min(state.recordIndex, count - 1);
  renderDetail();
}}

document.querySelectorAll("[data-view-button]").forEach(button => button.addEventListener("click", () => setView(button.dataset.viewButton)));
document.getElementById("seed-select").addEventListener("change", event => {{ state.seed = Number(event.target.value); state.recordIndex = 0; renderDetail(); }});
document.getElementById("previous-record").addEventListener("click", () => stepRecord(-1));
document.getElementById("next-record").addEventListener("click", () => stepRecord(1));
document.addEventListener("keydown", event => {{
  if (state.view !== "detail" || ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  if (event.key === "ArrowLeft") {{ event.preventDefault(); stepRecord(-1); }}
  if (event.key === "ArrowRight") {{ event.preventDefault(); stepRecord(1); }}
  if (event.key === "ArrowUp") {{ event.preventDefault(); stepSeed(-1); }}
  if (event.key === "ArrowDown") {{ event.preventDefault(); stepSeed(1); }}
}});

renderOverview();
renderSeedOptions();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
