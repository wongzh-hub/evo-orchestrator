---
name: evo-tune
description: Self-tuning workflow runner for Claude Code. Runs a project's Workflow via an evolving TEXT "policy" (champion + challenger workflow scripts), compares the two (design-judge OR run-all), collects the USER's feedback, and rewrites policy.json + journal.md so the workflow improves across runs. Verbal/evolutionary — no weights, the policy is text. Use when the user says "evo-tune", "self-tuning workflow", "run <project> with evo", or "tune this workflow".
---

# evo-tune — self-tuning workflow loop (Claude Code edition)

Wraps running a project's Workflow with an evolving text policy. The base model is
frozen; what's "learned" and saved is the **workflow script itself** (champion)
plus a mutated **challenger**. Reward = a design-judge (cheap, frequent) + the
**user's feedback** (sparse, authoritative — it wins on conflict).

State lives per project at `<project>/evo/`:
- `policy.json` — champion script + version + history
- `challenger.json` — the current mutation under test
- `journal.md` — run log (mode, outcome, feedback, rationale)

Seed library: `${CLAUDE_PLUGIN_ROOT}/seeds/*.js` — fork one as the v1 champion for
a matching new project.

## Portability note
This edition is machine-independent. Read/write the policy files via `evo_io.py`
(next to this file). Pass scripts to `evo_io.py` by FILE path, not as argv, to
avoid length limits. Nothing here assumes a specific OS, temp dir, or search tool.

## Procedure

1. **Resolve target.** Identify the project + which Workflow to run. Set
   `EVO=<project>/evo`. Run `python "${CLAUDE_PLUGIN_ROOT}/skills/evo-tune/evo_io.py" status "$EVO"`.
   - If no `policy.json`: ask which seed to fork (a `${CLAUDE_PLUGIN_ROOT}/seeds/*.js`,
     or an existing script). Write it to a file, then `evo_io.py init "$EVO" <file> <name>`.

2. **Ask the user the per-run choice** (2 candidates: champion vs challenger):
   - **A) design-judge (static)** — judge champion vs challenger on structure only;
     run just the winner. Cheapest (~1×), proxy signal.
   - **B) run-all (dynamic)** — run BOTH on the real input; compare OUTPUTS. True
     signal, ~2× cost.
   - **C) champion-only** — run current best, no comparison, no learning this run.

3. **Ensure a challenger exists** (modes A/B). If missing, spawn an improver agent
   (opus) — give it the champion script + the last few `journal.md` entries — to
   produce a meaningfully improved variant. Save via `evo_io.py set-challenger`.

4. **Execute by mode:**
   - **A:** spawn 2 opus judges (order-swapped, champion-vs-challenger) scoring
     orchestration STRUCTURE (pipeline/parallel correctness, justified barriers,
     fan-out sizing, verification/adversarial stages, schema use, timeout/partial-
     failure handling, phase clarity, prompt quality, anti-patterns). Majority →
     winner. Run the WINNER. Deliver result.
   - **B:** run BOTH via the Workflow tool on the same input. Show the user both
     outputs. Judge outputs (opus, order-swapped) AND ask which is better.
   - **C:** run the champion. Deliver result.

5. **Collect the user's feedback** — thumbs (good/bad) + optional note. Authoritative.

6. **Update:**
   - winner = user feedback if given, else judge verdict.
   - challenger won → `evo_io.py promote "$EVO"`, then generate a fresh challenger.
   - champion won → keep it; optionally replace the stale challenger.
   - Always `evo_io.py log "$EVO" "<mode>: ran v<n>; winner=<...>; feedback=<...>; why=<one line>"`.

7. **Report:** what ran, the verdict, the feedback recorded, the new version.

## Notes
- Default cadence: mode A most runs, B when output quality matters, C when in a hurry.
- Compare, never rate — pairwise + order-swapped. A raw 1–10 score is noisy; a
  head-to-head judgment is not.
- A noisy judge can drift; the user's feedback periodically re-anchors it. Never let
  a judge override explicit user feedback.
- Engine universal, weight per-project: each project keeps its own `evo/`.
- The standalone Python edition (repo root) reimplements the arena / duel / fuse
  loop if you'd rather run outside Claude Code with an API key.
