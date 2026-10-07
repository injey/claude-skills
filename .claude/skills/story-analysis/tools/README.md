# Docs tools

## csv2html.py: interactive table from any CSV

Turns a CSV into a single self-contained HTML page you can open in any browser, with:

- sorting on any column (shift-click to sort by several columns);
- a filter under each header:
  - a pick list for columns with few distinct values;
  - "contains" text filters for other text columns;
  - `=`, `>`, `<`, `>=`, `<=` for number columns;
- a search across all columns, a column show/hide menu, and Reset;
- **Download filtered CSV**, which exports the rows you're currently seeing;
- long text capped at 3 lines; click a row to expand it.

```bash
python3 .claude/skills/story-analysis/tools/csv2html.py path/to/data.csv --title "My table"   # writes path/to/data.html
python3 .claude/skills/story-analysis/tools/csv2html.py a.csv b.csv                           # several at once
python3 .claude/skills/story-analysis/tools/csv2html.py data.csv --cdn                        # small file, needs internet
```

It needs only the Python 3.9+ standard library, and nothing in it is specific to one CSV: columns
and filter types come from the data. The table is drawn by
[Tabulator](https://tabulator.info) 6.3.1 (MIT licence). The library is inlined from `vendor/`
by default, so the page works offline and can be emailed (about 500 KB). `--cdn` loads it from
cdnjs instead.

The data is embedded at build time because browsers don't let a local page read a separate CSV
file. **Rebuild the HTML whenever the CSV changes.** The generators that produce CSVs already do
this:

- `stories/SETTINGS-01/tools/build_inventory.py`;
- `proposals/udc-distribution/backlog/udc-distribution-backlog.py csv …`.

When you add a new CSV generator, call `csv2html.py` at its end in the same way.
