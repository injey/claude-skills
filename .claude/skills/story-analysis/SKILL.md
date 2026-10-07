---
name: story-analysis
description: Analyse a UDC backlog story (IDs like SETTINGS-02, REPO-01, LEAK-01, PACKAGE-04) and write its notes in ../internal-docs/stories/<STORY-ID>/ (beside the repository) in the agreed format: summary, current issues and planned changes, a decisions table with Status, collapsible decision details, next steps and a decisions log, plus HTML. Also covers recording decisions (marking them Agreed) and keeping the phase overview page in step. Use when asked to start, analyse, plan or design a story, to add or explain decisions for a story, or to mark story decisions as agreed.
---

# Story analysis

Every backlog story gets one notes folder. The notes are internal working material for the UDC
team. They use simple language, show current facts and final decisions only (no history of how a
decision was reached), and put detail into collapsible items so the page stays short.

Story notes live beside the repository, in `../internal-docs/stories/` (paths below are relative to
the repository root):

```
../internal-docs/stories/
  README.md                  index: phase overviews + one status row per story
  <PHASE>/README.md          phase overview (objective, stories, dependencies, outcome, decisions, next steps)
  <STORY-ID>/
    README.md                the story notes (format below) -> README.html (+ README.pdf when useful)
    *.csv                    data the story produces -> *.html via .claude/skills/story-analysis/tools/csv2html.py
    tools/                   scripts that produced the data; rerunnable against a newer commit
```

The story list, dependencies, points and acceptance criteria come from the backlog:
`../internal-docs/proposals/udc-distribution/backlog/udc-distribution-backlog.py` (also the `-stories.csv`).

## Ground rules

- **Changes to `unifydatacube` only on a branch other than `dev` or `main`.**
  - Before any edit or commit there, run `git -C unifydatacube branch --show-current`. If it's `dev`
    or `main`, **warn the user and stop**: no edits and no commit, not even a local one. Check again
    just before committing.
  - Change the repo only when the user asks for that change; analysis alone stays read-only.
  - Commits are local only: never push, never open pull requests, never touch remotes.
  - Record the branch and commit you scanned or changed (`git log -1 --format='%h %cs'`).
- **Facts from the code, not memory.** Every count, file path and line in the notes comes from a scan
  you ran. Put scans worth repeating in `tools/` (standard library Python), and have them fail loudly
  when the code moves away from what the notes assume.
- **Proofs of concept during analysis** go in `../internal-docs/stories/<ID>/poc/`, with a `run_poc.py`
  that uses the repo's own `.venv`, imports repo code without writing to it
  (`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `PYTHONPATH=poc:repo`) and checks that the
  repo's `git status` is unchanged afterwards. Record the results and lessons in a collapsible item.
  The real implementation goes into the repo, on the feature branch, once the user asks for it.
- **Test baselines:** run the repo's suite the same way (leaving no files behind), record pass/fail with causes as CSV
  and HTML, and compare later runs against it (no new failures).
- **Tabular output:** CSV (UTF-8 with BOM), followed by `python3 .claude/skills/story-analysis/tools/csv2html.py file.csv --title "…"`
  for the interactive view. A generator script ends with that call.
- **Decision IDs are phase-wide**, so one phase has one decision register: `S-D<n>` for SETTINGS
  (continue the numbering; SETTINGS-01 used S-D1 … S-D13). For other phases use the phase initial,
  for example `R-D1` (REPO), `L-D1` (LEAK), `P-D1` (PACKAGE), `C-D1` (CONTAIN), `RO-D1` (ROLLOUT).
- **Status is Agreed only when the user asks.** A decision is Open until the user, after discussing it,
  explicitly says it's agreed. Never infer agreement from approval of an edit. When it's marked:
  set Status to **Agreed**, change "To agree" to "Agreed answers (date)", add a decisions-log row,
  and update the story status line, the phase overview and the index.
- **Final values only.** Once something is decided, rewrite the text to state the decision. Don't
  keep "changed from", "moved", "16 kept, 4 changed" and similar history.
- **Link phase and story pages, as HTML.** In the phase overview's Stories table, the story ID links to
  `../<STORY-ID>/README.html` and so does its "notes" link. Each story's header table has an
  `| Overview | [← <PHASE> phase overview](../<PHASE>/README.html) |` row under Phase. Use `.html`
  targets: the built pages don't rewrite `.md` links.
- **Reuse earlier decisions.** Before proposing a decision, read the phase overview's "Agreed
  decisions" and the earlier story notes. Build on them; don't reopen them.

## Workflow

1. **Read the story:** backlog description, acceptance criteria, dependencies; the phase overview;
   the notes of the stories it depends on.
2. **Scan the code** (read-only during analysis) for what the story touches. Quantify: how many files, reads,
   tests, call sites. Find what will break or surprise (hidden defaults, runtime writes, test
   fixtures, import-time reads, leaks).
3. **Draft the decisions.** One per real choice the team must make. Each has a recommendation, a
   short "Today / Recommendation / Impact / To agree" detail, and yes/no questions that are easy to
   agree.
4. **Write `../internal-docs/stories/<STORY-ID>/README.md`** using [template.md](template.md).
5. **Build and check:**
   `python3 .claude/skills/markdown-docs/scripts/md2pdf.py ../internal-docs/stories/<ID>/README.md --format html`.
   - Collapsible items must stay closed in HTML; the PDF prints them open (the `beforeprint` script
     in the template).
   - Put a non-breaking hyphen (U+2011) in ID cells (`S‑D14`, `SETTINGS‑02`) so they don't wrap.
   - Mermaid diagrams: prefer `flowchart TB` or list-style boxes; wide `LR` chains render tiny.
     Render the PDF (`… README.md` without `--format`) and view a page with
     `swift .claude/skills/markdown-docs/scripts/pdf_pages.swift <pdf> <dir> <pages>`.
6. **Update the phase overview** (`../internal-docs/stories/<PHASE>/README.md`): the story's status row, its
   notes link, new agreed decisions, next steps. Rebuild its HTML. Update `../internal-docs/stories/README.md`.
7. **Reply in chat** with a short summary: what was found, the decisions to agree (one table with
   the recommended answers) and the next steps. Ask which decisions to mark Agreed.
8. **Implement, only when the user asks:**
   1. Check the branch (not `dev` or `main`; otherwise warn and stop).
   2. Make the change in `unifydatacube`, following the agreed decisions.
   3. Run the tests and compare with the story's test baseline: no new failures.
   4. Commit locally with a clear message (no push).
   5. Update the story notes: status, next steps, and the branch and commit of the change.

## Notes format (template.md)

| Section | Contents |
| --- | --- |
| Header table | Phase · Depends on / Unblocks · Status (one bold line: agreed vs open) · Baseline (repo, branch, commit, date; read-only scan or changed on branch) · Files (data, tables, tools) |
| **Summary** | What the story is for, the key numbers, and what's already decided upstream. A diagram if it helps. If counts come from a generator, keep them between `<!-- BEGIN GENERATED: name -->` / `<!-- END GENERATED: name -->` markers and let the script write them |
| **Current issues and planned changes** | Table: # · Current issue · Planned change · Story |
| **Decisions** | Table: ID · Decision · Recommendation · Status (**Agreed** / Open) |
| **Decision details** | One collapsible `<details>` per decision (title ends "(Open)" or "(Agreed)"): **Today**, **Recommendation**, **Impact**, **To agree** (numbered questions with "(Recommended: yes.)") |
| **Next steps** | Table: # · Step · Who. Long checklists or findings go in collapsible items below the table |
| **Decisions log** | Table: ID · Decision · Date · By ("Story owner" unless the user names someone) |

Writing style: short sentences, plain words, tables for anything with columns, one idea per
bullet. Describe the code as it is today and the plan as decided. Explain acronyms on first use.
