# CLAUDE.md — evo-orchestrator

Guidance for Claude Code (and humans) working in this repo.

## What this is
A standalone, model-agnostic reimplementation of an evolutionary workflow-tuning
loop. The base model is frozen; the evolving "weight" is a **policy script**
(Python text). The loop is: GENERATE (arena) → SELECT (pairwise duel) → PERSIST
(policy.json). See `README.md` for the full picture.

This is a clean-room public version. It does **not** depend on the Claude Code
Workflow harness — `runtime/harness.py` reimplements those primitives on the
Anthropic SDK so the same scripts run anywhere.

## Layout
```
runtime/harness.py   agent() parallel() pipeline() log() phase() on the Anthropic SDK
runtime/models.py    model alias -> id map + cost table (add new models here)
evo/loop.py          the orchestrator + CLI (evo? → arena → select → feedback → persist)
evo/arena.py         GENERATE: mutate + duel, R rounds, early-stop
evo/judge.py         pairwise, order-swapped duel (design + output flavours), split detect
evo/fuse.py          crossover: splice two split candidates, gate the child
evo/policy.py        policy.json / challenger.json / journal.md I/O
seeds/*.py           7 starting champions (one per task type)
graders/             optional execution grader for coding tasks
examples/            runnable end-to-end demo
evo.py               CLI entry point
```

## Conventions
- **Policy-script contract:** every seed / champion defines
  `async def run(agent, parallel, pipeline, log, phase, args)` and an optional
  module-level `META` dict. Keep it runnable — the runtime `exec()`s it.
- **Pairwise, never rated.** Comparisons are two-candidate, order-swapped. Don't
  introduce absolute 1–10 scoring; it's noisy and was deliberately rejected.
- **Reward hierarchy:** user feedback > output comparison (mode c) > design
  judge (mode b). Never let a judge override explicit user feedback.
- **Cost discipline:** default to the cheap path (design judge, no execution).
  Only mode c runs scripts on real input (~2× cost). Every seed should use cheap
  models for bulk work and strong models only for verify/synthesize.
- **Schema for structure.** Prefer `agent(..., schema=…)` (forced tool-use) over
  parsing free text.
- **Guarded fan-out.** `agent()` never raises — it logs and returns `None` on
  timeout/error. Filter with `[x for x in results if x]`.

## Security (important)
`runtime.run_script` and `graders/pytest_grader.py` `exec()` code that may be
LLM-authored. Do not run untrusted champions on a machine with secrets. Prefer a
container/VM. This is inherent to evolving executable scaffolds — keep the
warning prominent if you touch the README.

## Dev
```bash
pip install -r requirements.txt
cp .env.example .env        # ANTHROPIC_API_KEY
python examples/run_research.py
```
No network/tests run in CI yet. When adding a seed, mirror an existing one's
structure and update `seeds/README.md`.

## Not in scope here
- The original Claude Code Workflow `.js` version and the `evo-tune` skill live
  in the author's private workspace, not this repo.
