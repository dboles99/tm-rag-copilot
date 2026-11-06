"""Static results page: docs/index.html and docs/recall.svg.

Everything is generated from results/*.json, data/ and EXPERIMENTS.md. The
page is one self-contained HTML file: inline CSS, inline SVG only, no external
scripts, fonts or images, so it also works offline and from a file:// URL.
Light and dark themes follow prefers-color-scheme; all dynamic text is HTML
escaped.
"""

import html
import json
import re
from pathlib import Path

from .index import DATA_DIR, RESULTS_DIR, ROOT
from .qa import PLACEHOLDER_RE
from .tbx import parse_tbx
from .tmx import parse_tmx

ACCENT = "#2f6f8f"
SERIES_COLORS = ["#7d8aa0", "#5b8a72", "#b08954", "#7a6f9e"]

PAGE_CSS = """
:root {
  --bg: #fbfbf9; --ink: #23272e; --muted: #6a7280; --card: #ffffff;
  --line: #e4e6ea; --accent: #2f6f8f; --grid: #e8eaee; --fail: #b3564d;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16181c; --ink: #e8eaee; --muted: #9aa2ad; --card: #1e2126;
    --line: #2e333a; --accent: #6fb3d8; --grid: #2a2f36; --fail: #d98a80;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink); line-height: 1.6;
  font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial,
    "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
}
header, main, footer { max-width: 60rem; margin: 0 auto; padding: 0 1.25rem; }
header { padding-top: 3rem; }
h1 { font-size: 2rem; margin: 0 0 .4rem; }
h2 {
  font-size: 1.25rem; margin: 2.75rem 0 .9rem; padding-top: 1.25rem;
  border-top: 1px solid var(--line);
}
.tagline { font-size: 1.05rem; max-width: 46rem; margin: .2rem 0 .6rem; }
.zh { color: var(--muted); margin: .3rem 0 0; max-width: 46rem; }
.lede {
  background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem 1.25rem; margin-top: 1.5rem;
}
.lede-title { margin: 0 0 .35rem; font-weight: 650; }
.lede ul { margin: 0; padding-left: 1.2rem; }
.lede li { margin: .25rem 0; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: 1rem; margin-top: 1.5rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.25rem; }
.card .value { font-size: 2rem; font-weight: 650; color: var(--accent); font-variant-numeric: tabular-nums; }
.card .label { color: var(--muted); font-size: .9rem; margin-top: .15rem; }
.card .sub { display: block; color: var(--muted); font-size: .8rem; margin-top: .2rem; }
figure { margin: 1rem 0 0; }
svg { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); border-radius: 10px; }
figcaption, .note { font-size: .87rem; color: var(--muted); margin: .55rem 0 0; }
.tablewrap { overflow-x: auto; max-width: 100%; -webkit-overflow-scrolling: touch; }
.tablewrap table { min-width: 36rem; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--line); vertical-align: top; overflow-wrap: anywhere; }
th { color: var(--muted); font-weight: 600; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td .sub { color: var(--muted); font-size: .82rem; display: block; }
tr.kept-row td { background: rgba(47, 111, 143, .10); }
.pill {
  display: inline-block; padding: .1rem .55rem; border-radius: 999px;
  font-size: .78rem; font-weight: 600; white-space: nowrap;
}
.pill.pass { color: var(--accent); background: rgba(47, 111, 143, .14); }
.pill.fail { color: var(--fail); background: rgba(179, 86, 77, .14); }
.bar-row { display: grid; grid-template-columns: 13rem 1fr; gap: .75rem; align-items: center; margin: .55rem 0; }
.bar-stack { display: grid; gap: .3rem; }
.bar-line { display: grid; grid-template-columns: 1fr 4.5rem; gap: .5rem; align-items: center; }
.bar-label { font-size: .88rem; overflow-wrap: anywhere; }
.bar-track { background: var(--grid); border-radius: 4px; height: 8px; overflow: hidden; }
.bar-fill { background: var(--accent); border-radius: 4px; height: 100%; }
.bar-fill.alt { background: var(--muted); }
.bar-val { font-variant-numeric: tabular-nums; font-size: .8rem; color: var(--muted); text-align: right; }
.legend { font-size: .85rem; color: var(--muted); margin: .6rem 0 0; }
ul { padding-left: 1.25rem; margin: .5rem 0 0; }
li { margin: .3rem 0; }
.exp-notes li { margin: .45rem 0; }
footer { color: var(--muted); font-size: .85rem; padding-top: 2.5rem; padding-bottom: 3rem; }
@media (max-width: 40rem) {
  .bar-row { grid-template-columns: 8.5rem 1fr; }
  .bar-line { grid-template-columns: 1fr 4rem; }
  h1 { font-size: 1.6rem; }
}
"""

CHART_CSS = """
.rchart-root { --cbg: #ffffff; --cink: #3c4148; --cgrid: #e8eaee; --cline: #c6ccd4; }
@media (prefers-color-scheme: dark) {
  .rchart-root { --cbg: #1e2126; --cink: #d7dbe0; --cgrid: #2a2f36; --cline: #4a5058; }
}
.rchart text { font-family: -apple-system, "Segoe UI", Roboto, Arial, "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 12px; fill: var(--cink); }
.rchart .bg { fill: var(--cbg); }
.rchart .grid { stroke: var(--cgrid); stroke-width: 1; }
.rchart .axis { stroke: var(--cline); stroke-width: 1; }
.rchart .series-label { font-size: 12px; font-weight: 600; }
"""

PIPE_CSS = """
.pipe-root { --pbg: #ffffff; --pink: #3c4148; --pbox: #f2f4f7; --pedge: #b9c0ca; --parrow: #8a93a0; }
@media (prefers-color-scheme: dark) {
  .pipe-root { --pbg: #1e2126; --pink: #d7dbe0; --pbox: #262a31; --pedge: #4a5058; --parrow: #8a93a0; }
}
.pipe text { font-family: -apple-system, "Segoe UI", Roboto, Arial, "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 12.5px; fill: var(--pink); }
.pipe .bg { fill: var(--pbg); }
.pipe .box { fill: var(--pbox); stroke: var(--pedge); stroke-width: 1.2; }
.pipe .stage { font-weight: 650; }
.pipe .arrow { stroke: var(--parrow); stroke-width: 1.4; fill: none; }
.pipe .head { fill: var(--parrow); }
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def pct(value) -> str:
    """Percentage to one decimal place, e.g. 0.9756 -> '97.6%'."""
    return f"{float(value) * 100:.1f}%"


def load_results(results_dir: str | Path) -> list[dict]:
    results_dir = Path(results_dir)
    results = []
    for path in sorted(results_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_file"] = path.name
        results.append(data)
    return results


def _short_label(config: str) -> str:
    has_lang = "target-lang" in config
    has_hybrid = "hybrid" in config
    if has_lang and has_hybrid:
        return "zh-CN + hybrid"
    if has_lang:
        return "zh-CN filter"
    if has_hybrid:
        return "hybrid"
    return "baseline"


def retrieval_series(results: list[dict]) -> list[dict]:
    series = []
    for result in results:
        if result.get("kind") != "retrieval" or result.get("cross_language"):
            continue
        series.append(
            {
                "label": _short_label(result.get("config", "baseline")),
                "config": result.get("config", "baseline"),
                "file": result.get("_file", ""),
                "values": result["recall_at_k"],
                "color": SERIES_COLORS[len(series) % len(SERIES_COLORS)],
            }
        )
    return series


def best_retrieval(results: list[dict]) -> dict | None:
    candidates = [r for r in results if r.get("kind") == "retrieval" and not r.get("cross_language")]
    if not candidates:
        return None
    def key(r):
        ks = [int(k) for k in r["k_values"]]
        return (r["recall_at_k"][str(max(ks))], r["mrr"])
    return max(candidates, key=key)


def model_result(results: list[dict]) -> dict | None:
    models = [r for r in results if r.get("kind") == "model"]
    return models[0] if models else None


def _retrieval(result: dict) -> bool:
    return result.get("kind") == "retrieval" and not result.get("cross_language")


def baseline_result(results: list[dict]) -> dict | None:
    """Plain vector search, no filter, no hybrid: the retrieval-only baseline."""
    matches = [
        r for r in results
        if _retrieval(r)
        and not r.get("options", {}).get("target_lang")
        and not r.get("options", {}).get("hybrid")
    ]
    return matches[0] if matches else None


def lang_filter_result(results: list[dict]) -> dict | None:
    """The kept retrieval configuration: target-language filter, no hybrid."""
    matches = [
        r for r in results
        if _retrieval(r)
        and r.get("options", {}).get("target_lang")
        and not r.get("options", {}).get("hybrid")
    ]
    return matches[0] if matches else None


def hybrid_result(results: list[dict]) -> dict | None:
    matches = [
        r for r in results
        if _retrieval(r)
        and r.get("options", {}).get("hybrid")
        and not r.get("options", {}).get("target_lang")
    ]
    return matches[0] if matches else None


def lang_hybrid_result(results: list[dict]) -> dict | None:
    matches = [
        r for r in results
        if _retrieval(r)
        and r.get("options", {}).get("hybrid")
        and r.get("options", {}).get("target_lang")
    ]
    return matches[0] if matches else None


def cross_lang_result(results: list[dict]) -> dict | None:
    matches = [r for r in results if r.get("cross_language")]
    return matches[0] if matches else None


def short_model_name(result: dict) -> str:
    name = result.get("llm_model") or result.get("provider") or "model"
    if "qwen" in name.lower():
        return "Qwen"
    return name


def parse_markdown_tables(text: str) -> list[list[list[str]]]:
    tables = []
    current = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def build_recall_svg(series: list[dict], ks: list[int], width: int = 780, height: int = 400, standalone: bool = False) -> str:
    """Line chart of recall@k per configuration, with direct labels on the lines."""
    left, right, top, bottom = 48, 168, 24, 40
    plot_w = width - left - right
    plot_h = height - top - bottom
    k_min, k_max = min(ks), max(ks)
    y_max = 1.0

    def x(k):
        if k_max == k_min:
            return left + plot_w / 2
        return left + plot_w * (k - k_min) / (k_max - k_min)

    def y(v):
        return top + plot_h * (1.0 - v / y_max)

    parts = []
    if standalone:
        parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        parts.append(
            f'<svg class="rchart rchart-root" xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="recall@k by configuration">'
        )
    else:
        parts.append(
            f'<svg class="rchart rchart-root" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="recall@k by configuration">'
        )
    parts.append(f"<style>{CHART_CSS}</style>")
    parts.append(f'<rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="10"/>')
    for i in range(6):
        gy = y(i * 0.2)
        parts.append(f'<line class="grid" x1="{left}" y1="{gy:.1f}" x2="{left + plot_w}" y2="{gy:.1f}"/>')
        parts.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" text-anchor="end">{i * 0.2:.1f}</text>')
    for k in ks:
        gx = x(k)
        parts.append(f'<line class="grid" x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top + plot_h}"/>')
        parts.append(f'<text x="{gx:.1f}" y="{top + plot_h + 18}" text-anchor="middle">k={k}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}"/>')
    parts.append(f'<text x="{left}" y="{top - 8}">recall@k</text>')

    label_positions = []
    for s in series:
        points = [(k, float(s["values"][str(k)])) for k in ks if str(k) in s["values"]]
        if not points:
            continue
        coords = " ".join(f"{x(k):.1f},{y(v):.1f}" for k, v in points)
        parts.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="2.2" points="{coords}"/>')
        for k, v in points:
            parts.append(f'<circle cx="{x(k):.1f}" cy="{y(v):.1f}" r="3" fill="{s["color"]}"/>')
        last_k, last_v = points[-1]
        label_positions.append((y(last_v), s["label"], s["color"]))
    label_positions.sort(key=lambda t: t[0])
    placed = []
    for ly, label, color in label_positions:
        adjusted = ly
        for prev in placed:
            if abs(adjusted - prev) < 14:
                adjusted = prev + 14
        placed.append(adjusted)
        parts.append(
            f'<text class="series-label" x="{left + plot_w + 10}" y="{adjusted + 4:.1f}" fill="{color}">{esc(label)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def build_pipeline_svg(width: int = 920, height: int = 210) -> str:
    """Inline SVG diagram of the pipeline: TMX/TBX in, embed+index, retrieve, prompt, model, QA, evaluate."""
    stages = [
        ("TMX + TBX", "data files"),
        ("parse", "tmx.py, tbx.py"),
        ("embed + index", "MiniLM, Qdrant"),
        ("retrieve", "vector, +BM25 RRF"),
        ("prompt", "v1.0 text, v2.0 JSON"),
        ("model", "mock or Qwen via Ollama"),
        ("QA", "deterministic rules"),
        ("evaluate", "recall@k, MRR, QA"),
    ]
    box_w, box_h, gap = 200, 56, 24
    row1 = stages[:4]
    row2 = stages[4:]
    y1, y2 = 24, 24 + box_h + 64

    def box(x, y, title, sub):
        return (
            f'<rect class="box" x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="9"/>'
            f'<text class="stage" x="{x + box_w / 2}" y="{y + 23}" text-anchor="middle">{esc(title)}</text>'
            f'<text x="{x + box_w / 2}" y="{y + 41}" text-anchor="middle">{esc(sub)}</text>'
        )

    parts = [
        f'<svg class="pipe pipe-root" viewBox="0 0 {width} {height}" role="img" aria-label="pipeline diagram">',
        f"<style>{PIPE_CSS}</style>",
        f'<rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="10"/>',
        "<defs>"
        '<marker id="arrowhead" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
        '<path class="head" d="M0,0 L8,4.5 L0,9 z"/>'
        "</marker>"
        "</defs>",
    ]
    xs = [24 + i * (box_w + gap) for i in range(4)]
    for i, (title, sub) in enumerate(row1):
        parts.append(box(xs[i], y1, title, sub))
    for i, (title, sub) in enumerate(row2):
        parts.append(box(xs[i], y2, title, sub))
    for i in range(3):
        x_end = xs[i] + box_w
        parts.append(
            f'<line class="arrow" x1="{x_end + 3}" y1="{y1 + box_h / 2}" x2="{xs[i + 1] - 5}" y2="{y1 + box_h / 2}" marker-end="url(#arrowhead)"/>'
        )
    for i in range(3):
        x_end = xs[i] + box_w
        parts.append(
            f'<line class="arrow" x1="{x_end + 3}" y1="{y2 + box_h / 2}" x2="{xs[i + 1] - 5}" y2="{y2 + box_h / 2}" marker-end="url(#arrowhead)"/>'
        )
    down_x = xs[3] + box_w / 2
    parts.append(
        f'<path class="arrow" d="M {down_x} {y1 + box_h + 3} L {down_x} {y2 - 14} L {xs[0] + box_w / 2} {y2 - 14} L {xs[0] + box_w / 2} {y2 - 5}" marker-end="url(#arrowhead)"/>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def render_headline_cards(model: dict | None, baseline: dict | None, zhcn: dict | None, results: list[dict]) -> str:
    cards = []
    if model is not None:
        card = {
            "value": pct(model["qa_pass_rate"]),
            "label": f"QA pass with a real model ({short_model_name(model)})",
            "sub": "",
        }
        if baseline is not None:
            card["sub"] = f"{pct(baseline['qa_pass_rate'])} with the retrieval-only baseline"
        cards.append(card)
    if zhcn is not None:
        ks = [int(k) for k in zhcn["k_values"]]
        max_k = max(ks)
        recall = zhcn["recall_at_k"]
        cards.append({"value": pct(recall[str(max_k)]), "label": f"Right match in the top {max_k} (zh-CN filter)"})
        cards.append({"value": pct(recall["1"]), "label": "Right match first (zh-CN filter)"})
    if model is not None:
        cards.append({"value": str(model["bad_json_count"]), "label": f"Bad JSON replies in {model['n_gold']} runs"})
    if not cards:
        cards.append({"value": str(len(results)), "label": "results files"})
    cells = "".join(
        '<div class="card">'
        f'<div class="value">{esc(c["value"])}</div>'
        f'<div class="label">{esc(c["label"])}'
        + (f'<span class="sub">{esc(c["sub"])}</span>' if c.get("sub") else "")
        + "</div></div>"
        for c in cards
    )
    return f'<div class="cards">{cells}</div>'


def render_headline_note(model: dict | None, baseline: dict | None, zhcn: dict | None) -> str:
    parts = []
    if model is not None:
        parts.append(
            f"{model['_file']}: {model.get('llm_model') or model['provider']} served locally, "
            f"prompt v{model['prompt_version']}, {model['n_gold']} gold items, "
            f"{model['wall_time_seconds']:.0f} s wall time"
        )
    if baseline is not None:
        parts.append(f"{baseline['_file']}: retrieval-only baseline, mock provider")
    if zhcn is not None:
        parts.append(f"{zhcn['_file']}: zh-CN target-language filter")
    if not parts:
        return ""
    return f'<p class="note">Sources: {esc("; ".join(parts))}.</p>'


def render_qa_bars(mock_res: dict | None, model_res: dict | None) -> str:
    """One row per QA check, each with two thin bars (mock and real model)."""
    sources = []
    if mock_res is not None:
        sources.append(("mock", mock_res.get("qa_by_check", {}), "alt"))
    if model_res is not None:
        sources.append((short_model_name(model_res), model_res.get("qa_by_check", {}), ""))
    if not sources:
        return '<p class="note">No QA results found.</p>'

    def value_of(qa, check):
        return qa.get(check)

    def differs(check):
        vals = [value_of(qa, check) for _, qa, _ in sources]
        present = [v for v in vals if v is not None]
        if len(present) != len(vals):
            return True
        return len(present) > 1 and abs(float(present[0]) - float(present[1])) > 1e-9

    checks = sorted({c for _, qa, _ in sources for c in qa})
    checks.sort(key=lambda c: (0 if differs(c) else 1, c))
    rows = []
    for check in checks:
        lines = []
        for label, qa, cls in sources:
            value = value_of(qa, check)
            if value is None:
                continue
            width = max(0.0, min(1.0, float(value))) * 100.0
            lines.append(
                f'<div class="bar-line"><div class="bar-track">'
                f'<div class="bar-fill {cls}" style="width:{width:.1f}%"></div></div>'
                f'<div class="bar-val">{pct(value)}</div></div>'
            )
        rows.append(
            f'<div class="bar-row"><div class="bar-label">{esc(check)}</div>'
            f'<div class="bar-stack">{"".join(lines)}</div></div>'
        )
    n = (model_res or mock_res)["n_gold"]
    legend = "Each check has two thin bars: " + " and ".join(
        f"{esc(label)} ({'grey bar, mock that copies the closest TM match' if cls == 'alt' else 'accent bar, real model'})"
        for label, _, cls in sources
    ) + (
        f". Percentages are the share of the {n} gold items passing that check; "
        "checks where the two runs differ are listed first"
    )
    files = ", ".join(
        res["_file"] for res in (mock_res, model_res) if res is not None
    )
    return (
        "".join(rows)
        + f'<p class="legend">{esc(legend)}.</p>'
        + (f'<p class="note">From {esc(files)}.</p>' if files else "")
    )


THAI_RE = re.compile(r"[\u0e00-\u0e7f]")


def render_examples(items_source: dict | None, units: list, terms: list | None = None, limit: int = 6) -> str:
    """Pick `limit` informative per-item rows: a QA failure, a placeholder, a required term, a Thai variant."""
    if items_source is None or not items_source.get("items"):
        return '<p class="note">No per-item results found.</p>'
    terms = terms or []
    by_source: dict[str, dict[str, str]] = {}
    for u in units:
        by_source.setdefault(u.source, {})[u.tgt_lang] = u.target
    by_id = {u.id: u for u in units}
    term_sources = [t.source.lower() for t in terms if t.source]

    candidates = []
    for index, item in enumerate(items_source["items"]):
        unit = by_id.get(item.get("expected_id"))
        if unit is None or "zh-CN" not in by_source.get(unit.source, {}):
            continue
        candidates.append((index, item, unit))

    def has_placeholder(item, unit):
        return bool(
            PLACEHOLDER_RE.search(unit.source)
            or PLACEHOLDER_RE.search(item.get("translation", ""))
        )

    def has_brace_placeholder(item, unit):
        return bool(
            re.search(r"\{[^}]+\}", unit.source)
            or re.search(r"\{[^}]+\}", item.get("translation", ""))
        )

    def has_required_term(item, unit):
        lowered = unit.source.lower()
        return any(ts in lowered for ts in term_sources)

    def has_thai(item, unit):
        return bool(THAI_RE.search(by_source.get(unit.source, {}).get("th", "")))

    chosen = []

    def take(predicate):
        for cand in candidates:
            if cand not in chosen and predicate(cand[1], cand[2]):
                chosen.append(cand)
                return

    take(lambda item, unit: not item.get("qa_passed"))
    take(has_brace_placeholder)
    take(has_placeholder)
    take(has_required_term)
    take(has_thai)
    for cand in candidates:
        if len(chosen) >= limit:
            break
        if cand not in chosen:
            chosen.append(cand)
    chosen = sorted(chosen, key=lambda c: c[0])[:limit]

    rows = []
    for _index, item, unit in chosen:
        langs = by_source[unit.source]
        top_id = item.get("top_match_id")
        top_unit = by_id.get(top_id) if top_id else None
        if top_unit is None and top_id:
            top_unit = by_id.get(str(top_id).split("@")[0])
        top_target = top_unit.target if top_unit is not None else ""
        translation = item.get("translation", "")
        if len(translation) > 120:
            translation = translation[:119] + "…"
        if item.get("qa_passed"):
            qa = '<span class="pill pass">pass</span>'
        else:
            failed = ", ".join(item.get("failed_checks", [])) or "failed"
            qa = f'<span class="pill fail">fail: {esc(failed)}</span>'
        rows.append(
            "<tr>"
            f'<td>{esc(unit.source)}<span class="sub">query: {esc(item.get("query", ""))}</span></td>'
            f'<td>{esc(top_id or "-")}<span class="sub">{esc(top_target)}</span></td>'
            f'<td>{esc(langs.get("zh-CN", "-"))}</td>'
            f'<td>{esc(langs.get("zh-TW", "-"))}</td>'
            f'<td>{esc(langs.get("th", "-"))}</td>'
            f"<td>{esc(translation)}</td>"
            f"<td>{qa}</td>"
            "</tr>"
        )
    if not rows:
        return '<p class="note">No examples with a zh-CN variant found.</p>'
    name = short_model_name(items_source) if items_source.get("kind") == "model" else items_source.get("provider", "mock")
    head = (
        "<tr><th>Source</th><th>Closest match</th><th>zh-CN</th><th>zh-TW</th><th>th</th>"
        f"<th>Output ({esc(name)})</th><th>QA</th></tr>"
    )
    note = (
        f'<p class="note">The zh-CN, zh-TW and th columns are the stored translations of that unit in the '
        f'translation memory (a dash means the TM holds no variant in that language). The output column is what '
        f'{esc(name)} produced for the query; QA ran on the source segment.</p>'
    )
    return f'<div class="tablewrap"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>' + note


def _summary_cell(cell: str) -> str:
    """'0.8049 (mock)' -> '80.5% (mock)'; drop '(results/...)' file references from body text."""
    text = re.sub(r"\s*\(results/[^)]*\)", "", cell).strip()
    m = re.match(r"^(\d+(?:\.\d+)?)(.*)$", text)
    if m:
        rest = m.group(2).strip()
        suffix = f" {rest}" if rest else ""
        return pct(float(m.group(1))) + suffix
    return text


def render_experiment_summary(experiments_text: str) -> str:
    """Render only the single summary table (the one with a 'kept' column), as percentages."""
    tables = parse_markdown_tables(experiments_text)
    summary = next((t for t in tables if "kept" in " ".join(t[0]).lower()), None)
    if summary is None:
        return '<p class="note">No experiment summary table found.</p>'
    head = "".join(f"<th>{esc(_summary_cell(c))}</th>" for c in summary[0])
    body = []
    for row in summary[1:]:
        kept_row = "best" in " ".join(row).lower()
        cls = ' class="kept-row"' if kept_row else ""
        body.append(
            f"<tr{cls}>" + "".join(f"<td>{esc(_summary_cell(c))}</td>" for c in row) + "</tr>"
        )
    return (
        f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


def render_experiment_sentences(results: list[dict]) -> list[str]:
    """One plain sentence per experiment: what was tried, what happened, what was decided."""
    baseline = baseline_result(results)
    zhcn = lang_filter_result(results)
    hybrid = hybrid_result(results)
    zhcn_hybrid = lang_hybrid_result(results)
    cross = cross_lang_result(results)
    model = model_result(results)

    def top(res):
        ks = [int(k) for k in res["k_values"]]
        max_k = max(ks)
        recall = res["recall_at_k"]
        return max_k, pct(recall[str(max_k)]), pct(recall["1"])

    sentences = []
    if baseline is not None:
        max_k, top_pct, first_pct = top(baseline)
        sentences.append(
            f"Plain vector search, nothing changed: the right match was in the top {max_k} for {top_pct} of "
            f"queries and ranked first for {first_pct}; kept as the reference run, not the default."
        )
    if zhcn is not None:
        max_k, top_pct, first_pct = top(zhcn)
        sentences.append(
            f"Keeping only zh-CN units in the ranking lifted the top-{max_k} share to {top_pct} and first place "
            f"to {first_pct}; this is the configuration we kept."
        )
    if hybrid is not None:
        max_k, top_pct, _ = top(hybrid)
        sentences.append(
            f"Adding BM25 keyword fusion to the vector search made recall worse at every k, with the top-{max_k} "
            f"share falling to {top_pct}; it stays an option, not the default."
        )
    if zhcn_hybrid is not None and zhcn is not None:
        max_k, top_pct, _ = top(zhcn_hybrid)
        _, zhcn_top, _ = top(zhcn)
        sentences.append(
            f"Filter plus hybrid together was strictly worse than the filter alone (top-{max_k} {top_pct} against "
            f"{zhcn_top} for the filter only); not adopted."
        )
    if cross is not None:
        max_k, top_pct, _ = top(cross)
        sentences.append(
            f"{cross['n_gold']} queries written in Chinese, searched against the English sources, still found the "
            f"right match in the top {max_k} for {top_pct} of them; kept as a standing cross-language check."
        )
    if model is not None:
        baseline_note = (
            f", against {pct(baseline['qa_pass_rate'])} for the retrieval-only mock"
            if baseline is not None else ""
        )
        sentences.append(
            f"A real local model ({short_model_name(model)}) passed QA on {pct(model['qa_pass_rate'])} of the "
            f"{model['n_gold']} items with {model['bad_json_count']} bad JSON replies{baseline_note}; kept as the "
            "translation path."
        )
    return sentences


def render_lede(n_runs: int) -> str:
    return (
        '<div class="lede"><p class="lede-title">What this shows</p><ul>'
        "<li>Retrieval over a translation memory: each new string reuses the closest stored segment, so output "
        "starts from approved translations instead of being generated from scratch.</li>"
        "<li>Deterministic QA that catches model mistakes: every output is checked against its source, and on the "
        "real model run it caught the one output that broke a rule (shown in the examples below).</li>"
        f"<li>Measured experiments only: {n_runs} runs on the same gold set, including one, hybrid keyword search, "
        "that made recall worse and was not adopted.</li>"
        "</ul></div>"
    )


def build_html(
    results: list[dict],
    units: list,
    experiments_text: str,
    terms: list | None = None,
) -> tuple[str, str]:
    series = retrieval_series(results)
    best = best_retrieval(results)
    model = model_result(results)
    baseline = baseline_result(results)
    zhcn = lang_filter_result(results)
    cross = cross_lang_result(results)
    mock_res = baseline
    ks = sorted({int(k) for s in series for k in s["values"]}) or [1]
    chart_svg = build_recall_svg(series, ks) if series else ""
    recall_svg_standalone = build_recall_svg(series, ks, standalone=True) if series else ""

    cross_note = ""
    if cross is not None:
        max_k = max(int(k) for k in cross["k_values"])
        cross_note = (
            f'Cross-language check: {cross["n_gold"]} Chinese queries from {esc(cross["gold_file"])} '
            f'searched against the English sources: recall@{max_k} {pct(cross["recall_at_k"][str(max_k)])}, '
            f'MRR {pct(cross["mrr"])} ({esc(cross["_file"])}).'
        )

    items_source = model if model is not None else best
    sentences = render_experiment_sentences(results)
    files_note = ", ".join(sorted(r["_file"] for r in results))

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>tm-rag-copilot: measured results</title>",
        f"<style>{PAGE_CSS}</style>",
        "</head>",
        "<body>",
        "<header>",
        "<h1>tm-rag-copilot</h1>",
        '<p class="tagline">A small, honest demo that embeds a synthetic translation memory and term base, '
        "retrieves by meaning, translates with a local model and checks every output with deterministic QA.</p>",
        '<p class="zh">简体中文:把虚构的翻译记忆(TMX)和术语库(TBX)向量化存入本地索引,按语义检索最相似的句段,用本地模型生成译文,并用确定性规则逐条做质量检查。</p>',
        '<p class="zh">繁體中文:把虛構的翻譯記憶(TMX)和術語庫(TBX)向量化存入本地索引,依語義檢索最相似的句段,用本地模型產生譯文,並以確定性規則逐條進行品質檢查。</p>',
        "</header>",
        "<main>",
        render_lede(len(results)),
        "<section>",
        "<h2>Headline numbers</h2>",
        render_headline_cards(model, baseline, zhcn, results),
        render_headline_note(model, baseline, zhcn),
        "</section>",
        "<section>",
        "<h2>Pipeline</h2>",
        f"<figure>{build_pipeline_svg()}<figcaption>TMX and TBX go in; segments are embedded and indexed, retrieved, "
        "prompted, generated, QA-checked and evaluated. Retrieval options: target-language filter and hybrid "
        "BM25 + RRF.</figcaption></figure>",
        "</section>",
        "<section>",
        "<h2>Recall@k by configuration</h2>",
        f"<figure>{chart_svg}<figcaption>Same gold set (data/gold.jsonl, {esc(str(best['n_gold']) if best else '')} queries), "
        "same embedding model; only the retrieval options differ. "
        + (f"Best measured configuration: {esc(best['config'])}." if best else "")
        + "</figcaption></figure>",
        (f'<p class="note">{cross_note}</p>' if cross_note else ""),
        "</section>",
        "<section>",
        "<h2>QA by check: mock vs real model</h2>",
        render_qa_bars(mock_res, model),
        "</section>",
        "<section>",
        "<h2>Real examples</h2>",
        render_examples(items_source, units, terms),
        "</section>",
        "<section>",
        "<h2>What we tried</h2>",
        render_experiment_summary(experiments_text),
        '<ul class="exp-notes">' + "".join(f"<li>{esc(s)}</li>" for s in sentences) + "</ul>",
        f'<p class="note">One row per run in results/: {esc(files_note)}.</p>',
        "</section>",
        "<section>",
        "<h2>What a production system adds</h2>",
        "<ul>"
        "<li>A real LLM provider with retries, fallbacks and cost limits (this repo runs one locally: Qwen via Ollama).</li>"
        "<li>A versioned TM with metadata (domain, quality scores, last used), per-language collections, and auth on the vector store.</li>"
        "<li>Batch and async ingestion, a human review workflow, and terminology enforced during decoding (constrained decoding).</li>"
        "<li>Continuous evaluation against a held-out set with alerts when recall or QA pass rate drops.</li>"
        "</ul>",
        "</section>",
        "<section>",
        "<h2>Limits</h2>",
        "<ul>"
        "<li>133 synthetic segments and a 384-dimensional MiniLM bound retrieval quality; recall@1 stays well below 1.</li>"
        "<li>The mock provider copies the nearest TM match; it does not translate. Its QA failures are reported, not hidden.</li>"
        "<li>Hybrid BM25 + RRF made recall worse on this paraphrased gold set (measured, kept as an option, not the default).</li>"
        "<li>The term base covers zh-CN only; zh-TW and th units exist in the TM but terms are not enforced for them.</li>"
        "<li>Qdrant runs in local mode, single process, no concurrency guarantees.</li>"
        "<li>Every number on this page is from one run of the committed code on the committed data; deterministic here, not a general claim.</li>"
        "</ul>",
        "</section>",
        "</main>",
        "<footer>",
        "Generated by <code>python -m tm_rag report</code> from results/*.json, data/ and EXPERIMENTS.md. "
        "Self-contained file: inline CSS and SVG only, no external resources.",
        "</footer>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n", recall_svg_standalone


def build_report(
    results_dir: str | Path = RESULTS_DIR,
    data_dir: str | Path = DATA_DIR,
    out_dir: str | Path | None = None,
    experiments_path: str | Path | None = None,
) -> list[Path]:
    """Write docs/index.html and docs/recall.svg; returns the written paths."""
    results_dir = Path(results_dir)
    data_dir = Path(data_dir)
    out_dir = Path(out_dir) if out_dir is not None else ROOT / "docs"
    experiments_path = Path(experiments_path) if experiments_path is not None else ROOT / "EXPERIMENTS.md"

    results = load_results(results_dir)
    if not results:
        raise ValueError(f"no results/*.json found in {results_dir}")
    units = parse_tmx(data_dir / "tm.tmx")
    tbx_path = data_dir / "terms.tbx"
    terms = parse_tbx(tbx_path) if tbx_path.exists() else []
    experiments_text = experiments_path.read_text(encoding="utf-8") if experiments_path.exists() else ""

    page, recall_svg = build_html(results, units, experiments_text, terms)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.html"
    svg_path = out_dir / "recall.svg"
    index_path.write_text(page, encoding="utf-8")
    svg_path.write_text(recall_svg, encoding="utf-8")
    return [index_path, svg_path]
