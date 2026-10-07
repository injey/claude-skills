# <STORY-ID>: <story title>

| | |
| --- | --- |
| Phase | <n> · <PHASE>. Depends on <stories>; unblocks <stories> |
| Overview | [← <PHASE> phase overview](../<PHASE>/README.html) |
| Status | **<Analysis done. Agreed: … Open: …>** |
| Baseline | `unifydatacube`, branch `<branch>`, commit `<sha>` (<date>); <read-only scan, or: changed on branch `<feature-branch>`, local commit `<sha>`> |
| Files | `<data>.csv` · [<data>.html](<data>.html) · `tools/` (<what the scripts do>) |

## Summary

<What the story delivers, in two or three sentences.>

**In short:** <the key numbers and the main recommendation in one or two sentences.>

<Optional: what earlier decisions already fix for this story, as a short list linking to them.>

## Current issues and planned changes

| # | Current issue | Planned change | Story |
| --- | --- | --- | --- |
| 1 | <fact from the code, with file paths and counts> | <what changes> | <story IDs> |

## Decisions

| ID | Decision | Recommendation | Status |
| --- | --- | --- | --- |
| <X‑D1> | <short name> | <one-line recommendation>. See details below | Open |

## Decision details

Select a decision to expand it.

<details>
<summary><strong><X-D1> · <short name></strong>: <one-line summary> (Open)</summary>

**Today:** <what the code does now, with paths and counts.>

**Recommendation:**
- <point>

**Impact:** <what changes for code, tests, deployments or customers.>

**To agree:**
1. <question>? (Recommended: yes.)

</details>

<script>
// Expand every decision when printing, so the PDF shows the full details.
addEventListener("beforeprint", () => document.querySelectorAll("details").forEach(d => d.open = true));
</script>

## Next steps

| # | Step | Who |
| --- | --- | --- |
| 1 | <step> | <role> |

<Optional collapsible checklists or findings, same <details> pattern.>

## Decisions log

| ID | Decision | Date | By |
| --- | --- | --- | --- |
| | *(filled in as decisions are agreed)* | | |
