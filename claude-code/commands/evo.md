---
description: Run a project's workflow through the evo-tune self-improving loop (champion vs challenger, your feedback is the reward)
argument-hint: <project-dir> [task-type]
---

Run the **evo-tune** loop for: $ARGUMENTS

Follow the `evo-tune` skill procedure exactly:

1. Resolve the target project + its `evo/` dir. If no `policy.json` exists yet, ask
   which seed to fork from `${CLAUDE_PLUGIN_ROOT}/seeds/` (match the task type), then
   init it as the v1 champion.
2. Ask me the per-run compare mode: **A** design-judge (cheap) / **B** run-all
   (compare real outputs, ~2×) / **C** champion-only (no learning).
3. Ensure a challenger exists via the internal **arena** (Workflow tool,
   `${CLAUDE_PLUGIN_ROOT}/skills/evo-tune/arena.workflow.js`): multi-round mutate → order-
   swapped design-duel → carry winner, early-stop, directed by the judge's per-dimension
   losses. Save the returned `challenger_script` via `evo_io.py set-challenger`.

4. Run + compare champion vs challenger **pairwise, order-swapped** — never a raw score.
5. Collect my feedback (good/bad + note) — it is authoritative and overrides the judge.
6. Promote the winner (`evo_io.py promote`), refresh the challenger, and append the
   journal line.
7. Report what ran, the verdict, my recorded feedback, and the new champion version.

Use `python "${CLAUDE_PLUGIN_ROOT}/skills/evo-tune/evo_io.py"` for all policy I/O.
