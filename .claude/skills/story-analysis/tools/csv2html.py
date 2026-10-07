#!/usr/bin/env python3
"""Turn any CSV into a self-contained, interactive HTML table (sort, filter, search, columns, export).

Usage:
    python3 csv2html.py data.csv [more.csv ...] [--title "Title"] [--cdn] [-o out.html]

- Columns come from the header row; nothing is specific to one file.
- Column filters are chosen from the data: a pick list for columns with few distinct values,
  a text "contains" filter otherwise, and a numeric filter (=, >, <, >=, <=) for number columns.
- By default the Tabulator library is inlined (from vendor/), so the page works offline and can be
  attached to an email. --cdn loads it from cdnjs instead (much smaller file, needs internet).
- Writes <name>.html next to each CSV unless -o is given (only with a single CSV).
Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = "tabulator-6.3.1"
VENDOR = HERE / "vendor" / LIB
CDN = "https://cdnjs.cloudflare.com/ajax/libs/tabulator/6.3.1"
NUM = re.compile(r"^-?\d+(\.\d+)?$")


def column_specs(header: list[str], rows: list[list[str]]) -> list[dict]:
    specs = []
    for i, name in enumerate(header):
        values = [r[i] for r in rows if i < len(r) and r[i] != ""]
        distinct = set(values)
        avg = sum(map(len, values)) / len(values) if values else 0
        if values and all(NUM.match(v) for v in values):
            kind = "number"
        elif distinct and len(distinct) <= 20 and (len(distinct) <= max(3, len(rows) // 3) or len(values) < len(rows)):
            kind = "list"
        else:
            kind = "text"
        specs.append({"title": name, "kind": kind, "long": avg > 40})
    return specs


def render(src: Path, title: str, cdn: bool) -> str:
    with src.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [r for r in reader if any(c.strip() for c in r)]
    # Tabulator field names: positional keys avoid problems with dots/spaces in headers.
    specs = column_specs(header, rows)
    data = [{f"c{i}": (r[i] if i < len(r) else "") for i in range(len(header))} for r in rows]
    for d in data:
        for i, s in enumerate(specs):
            if s["kind"] == "number" and d[f"c{i}"] != "":
                d[f"c{i}"] = float(d[f"c{i}"]) if "." in d[f"c{i}"] else int(d[f"c{i}"])
    payload = json.dumps({"columns": specs, "data": data}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    if cdn:
        lib = (f'<link rel="stylesheet" href="{CDN}/css/tabulator.min.css">\n'
               f'<script src="{CDN}/js/tabulator.min.js"></script>')
    else:
        css = (VENDOR / "tabulator.min.css").read_text(encoding="utf-8")
        js = (VENDOR / "tabulator.min.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        lib = f"<style>{css}</style>\n<script>{js}</script>"
    return (TEMPLATE.replace("%%TITLE%%", html.escape(title))
            .replace("%%SOURCE%%", html.escape(src.name))
            .replace("%%META%%", f"{len(rows)} rows · {len(header)} columns · generated {date.today().isoformat()}")
            .replace("%%STEM%%", json.dumps(src.stem))
            .replace("%%LIB%%", lib)
            .replace("%%DATA%%", payload))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
%%LIB%%
<style>
  :root { --brand:#4E106F; --accent:#EF2A79; --ink:#1d1d1f; --muted:#666; --line:#e2dce8; --bg:#fff; --zebra:#f8f6fa; }
  body { margin:0; font:14px/1.4 Roboto, "Helvetica Neue", Arial, sans-serif; color:var(--ink); background:var(--bg); }
  header { background:var(--brand); color:#fff; padding:14px 20px; }
  header h1 { margin:0; font-size:20px; font-weight:600; }
  header p { margin:4px 0 0; opacity:.8; font-size:12px; }
  .bar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:10px 20px; border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); z-index:10; }
  .bar input[type=search] { flex:1 1 260px; max-width:420px; padding:6px 10px; border:1px solid var(--line); border-radius:6px; font:inherit; }
  .bar button, .bar summary { padding:6px 12px; border:1px solid var(--brand); border-radius:6px; background:#fff; color:var(--brand); font:inherit; cursor:pointer; list-style:none; }
  .bar button:hover, .bar summary:hover { background:var(--brand); color:#fff; }
  .bar details { position:relative; }
  .bar details[open] .cols { display:block; }
  .cols { display:none; position:absolute; top:110%; left:0; background:#fff; border:1px solid var(--line); border-radius:6px; padding:8px 12px; max-height:60vh; overflow:auto; box-shadow:0 6px 18px rgba(0,0,0,.12); white-space:nowrap; z-index:20; }
  .cols label { display:block; padding:2px 0; cursor:pointer; }
  .count { margin-left:auto; color:var(--muted); font-size:12px; }
  .hint { color:var(--muted); font-size:12px; padding:6px 20px 0; }
  #table { margin:8px 20px 20px; }
  .tabulator { font-size:13px; border:1px solid var(--line); }
  .tabulator .tabulator-header .tabulator-col { background:var(--brand); color:#fff; }
  .tabulator .tabulator-header .tabulator-col .tabulator-col-content .tabulator-col-title { white-space:normal; }
  .tabulator .tabulator-header .tabulator-col input, .tabulator .tabulator-header .tabulator-col select { color:var(--ink); font-size:12px; }
  .tabulator-row.tabulator-row-even { background:var(--zebra); }
  .tabulator-row .tabulator-cell { white-space:pre-wrap; vertical-align:top; }
  .tabulator-row .tabulator-cell.tabulator-frozen { background:inherit; font-weight:600; }
  .tabulator-row.tabulator-selectable:hover { background:#efe7f5; }
  .tabulator-row { cursor:pointer; }
  .clamp { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; white-space:pre-wrap; }
  .tabulator-row.expanded .clamp { display:block; -webkit-line-clamp:unset; }
</style>
</head>
<body>
<header><h1>%%TITLE%%</h1><p>Source: %%SOURCE%% · %%META%%</p></header>
<div class="bar">
  <input type="search" id="search" placeholder="Search all columns…" aria-label="Search all columns">
  <details><summary>Columns</summary><div class="cols" id="cols"></div></details>
  <button id="reset" type="button">Reset</button>
  <button id="download" type="button">Download filtered CSV</button>
  <span class="count" id="count"></span>
</div>
<div class="hint">Click a header to sort (shift-click for multi-column sort). Click a row to expand long text. Filter under each header; number columns accept =, &gt;, &lt;, &gt;=, &lt;= (for example &gt;=2).</div>
<div id="table"></div>
<script>
const SRC = %%DATA%%;
const STEM = %%STEM%%;

function numberFilter(term, value) {
  const m = String(term).trim().match(/^(>=|<=|>|<|=)?\s*(-?\d+(\.\d+)?)$/);
  if (!m) return true;
  const op = m[1] || "=", n = parseFloat(m[2]);
  if (value === "" || value === null) return false;
  return {"=": value == n, ">": value > n, "<": value < n, ">=": value >= n, "<=": value <= n}[op];
}

// Long text: show 3 lines; click the row to expand or collapse it.
function clamp(cell) {
  const div = document.createElement("div");
  div.className = "clamp";
  div.textContent = cell.getValue() ?? "";
  return div;
}

const columns = SRC.columns.map((c, i) => {
  const col = { title: c.title, field: "c" + i, headerTooltip: c.title, minWidth: 90 };
  if (i === 0) col.frozen = true;
  if (c.long) { col.width = 300; col.formatter = clamp; col.tooltip = true; }
  if (c.kind === "number") {
    col.sorter = "number"; col.hozAlign = "right"; col.width = 95;
    col.headerFilter = "input"; col.headerFilterPlaceholder = ">=, <=, =";
    col.headerFilterFunc = numberFilter;
  } else if (c.kind === "list") {
    col.headerFilter = "list";
    col.headerFilterParams = { valuesLookup: "all", clearable: true, multiselect: true, sort: "asc" };
    col.headerFilterFunc = "in";
    col.headerFilterPlaceholder = "any";
  } else {
    col.headerFilter = "input"; col.headerFilterPlaceholder = "contains…";
  }
  return col;
});

const table = new Tabulator("#table", {
  data: SRC.data, columns, layout: "fitData", height: "calc(100vh - 170px)",
  columnDefaults: { maxInitialWidth: 360 },
  movableColumns: true, placeholder: "No rows match the filters",
});

const count = document.getElementById("count");
const total = SRC.data.length;
table.on("rowClick", (e, row) => { row.getElement().classList.toggle("expanded"); row.normalizeHeight(); });
table.on("dataFiltered", (filters, rows) => { count.textContent = rows.length + " of " + total + " rows"; });
table.on("tableBuilt", () => {
  count.textContent = total + " of " + total + " rows";
  const box = document.getElementById("cols");
  table.getColumns().forEach(col => {
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.checked = true;
    cb.addEventListener("change", () => cb.checked ? col.show() : col.hide());
    label.append(cb, " " + col.getDefinition().title);
    box.append(label);
  });
});

const search = document.getElementById("search");
search.addEventListener("input", () => {
  const q = search.value.trim().toLowerCase();
  if (!q) { table.clearFilter(); return; }
  table.setFilter(row => Object.values(row).some(v => String(v).toLowerCase().includes(q)));
});
document.getElementById("reset").addEventListener("click", () => {
  search.value = ""; table.clearFilter(true); table.clearSort();
});
document.getElementById("download").addEventListener("click", () => {
  table.download("csv", STEM + "-filtered.csv", { bom: true }, "active");
});
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--title", help="page title (default: file name)")
    ap.add_argument("--cdn", action="store_true", help="load Tabulator from cdnjs instead of inlining it")
    ap.add_argument("-o", "--out", type=Path, help="output file (single CSV only)")
    a = ap.parse_args()
    if a.out and len(a.csv) > 1:
        ap.error("-o works with one CSV only")
    for src in a.csv:
        title = a.title or src.stem.replace("-", " ").replace("_", " ").capitalize()
        out = a.out or src.with_suffix(".html")
        out.write_text(render(src, title, a.cdn), encoding="utf-8")
        print(f"built  {out}")


if __name__ == "__main__":
    main()
