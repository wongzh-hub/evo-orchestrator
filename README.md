# evo-orchestrator

[![tests](https://github.com/wongzh-hub/evo-orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/wongzh-hub/evo-orchestrator/actions/workflows/ci.yml)

> **RL for multi-agent workflows — but the weights are readable text.**

**Evolve a multi-agent workflow the way you'd train a policy — except the
"weights" are plain text you can read, edit, and share.**

The base model is frozen. What improves over time is the *orchestration
scaffold*: the workflow script itself (how agents are decomposed, fanned out,
verified, and what each is told). A pool of scaffolds is generated, compared
head-to-head, and the winner is kept — a champion / challenger loop that carries
your feedback as the reward signal.

This is **search / evolution, not gradient RL** — closer in spirit to
PromptBreeder, DSPy-GEPA, and Sakana's scaffold search than to fine-tuning. No
model is trained. The "weight" is a Python script.

> Standalone runtime included: the same scripts run anywhere with an
> `ANTHROPIC_API_KEY` — no proprietary harness required.

**Two editions, same loop:**
- **Standalone** (this repo root) — Python on the Anthropic SDK; needs an API key.
- **[Claude Code edition](claude-code/)** — runs inside Claude Code on your
  subscription, **no API key** (`.js` seeds + the `evo-tune` skill).

---

## The loop

```
activate(project, task_type, input)
   │
   ├─ evolve? ──no──►  run the champion only ──►  result
   │  yes
   ▼
GENERATE   arena: mutate champion → challenger, duel on structure,
   │       keep winner. R rounds (default 2), early-stop on no-dethrone.
   │       → one evolved candidate
   ▼
SELECT     duel:  evolved candidate  vs  incumbent champion
   │       a) you pick   b) design-judge (cheap)   c) run-all (2×, real output)
   │       └─ if SPLIT (optional, default-on): FUSE the two → EXTRA gate duel,
   │          child kept only if it beats the winner (else discarded)
   ▼
FEEDBACK   your thumbs up/down — authoritative, overrides the judge
   ▼
PERSIST    winner → policy.json (version++)   +   journal.md
```

Two candidates only, always compared **pairwise and order-swapped** (A-vs-B then
B-vs-A) to cancel position bias. Never an absolute 1–10 score — ratings are
noisy; relative judgments are not.

**Reward hierarchy:** your feedback  >  output comparison (mode c)  >  design
judge (mode b).

The "other" candidate in SELECT is the **incumbent champion from
`policy.json`** — i.e. *did this run's evolution actually beat the best you
already trust?* Only a proven win is promoted.

The **FUSE** step (crossover) is an **optional extra round**. It fires only when a
duel is *split* — each candidate wins some judged dimensions — and is **on by default
in that case** (skipped when one side sweeps). A splice agent merges the winning parts
of both into a child; that child must then win an **extra gate duel** against the
winner to be kept, else it's discarded (fusion often regresses). See
[`evo/fuse.py`](evo/fuse.py).

---

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY

# evolve + run a research task (design-judge mode, non-interactive)
python evo.py ./myproject --task research \
    --input "tradeoffs of vector DBs vs keyword search for RAG" \
    --mode b --evo --yes

# or the guided example
python examples/run_research.py
```

Interactive run (asks evolve?/rounds/mode/feedback):

```bash
python evo.py ./myproject --task research --input "..."
```

State lands in `./myproject/evo/`:

| file | is |
|------|----|
| `policy.json` | the champion script (the text "weight") + version + history |
| `challenger.json` | the mutation/fusion currently under test |
| `journal.md` | run log the mutator reads back like experience replay |

---

## Task types (seeds)

Ships with 7 starting champions in [`seeds/`](seeds/): `research`, `sec-review`,
`migrate`, `doc-extract`, `data-report`, `code-feature`, `bug-fix`. First use of
a type forks its seed to your project's v1 champion; evolution takes over from
there. Coding solutions can be graded **objectively** in run-all mode: pass `--tests <file>`
and, when a candidate emits a `solution`/`code` field, SELECT scores it with
[`graders/pytest_grader.py`](graders/pytest_grader.py) run in a **subprocess with a
timeout** (process isolation) via [`evo/grade.py`](evo/grade.py) instead of the LLM
judge; it falls back to the judge otherwise.

Add a task type by dropping a `<name>.py` into `seeds/`.

---

## How it works — the runtime

A policy script is Python that defines:

```python
META = {"name": "research", "description": "...", "phases": ["Gather", "Verify", "Synthesize"]}

async def run(agent, parallel, pipeline, log, phase, args):
    phase("Gather")
    claims = await parallel([ (lambda a=a: agent(f"research {a}", schema=CLAIM_SCHEMA)) for a in angles ])
    ...
    return {"answer": ...}
```

`runtime/harness.py` provides the four primitives on the Anthropic SDK:

- **`agent(prompt, schema=…, model=…)`** — one API call; returns text, or a
  validated dict when a JSON `schema` is given (forced tool-use).
- **`parallel(thunks)`** — `asyncio.gather` with a concurrency cap; a failed
  thunk resolves to `None`.
- **`pipeline(items, *stages)`** — each item flows through stages independently
  (no barrier between stages).
- **`log` / `phase`** — progress + a built-in token/cost meter.

Because the scaffold is *just a script*, an LLM can mutate it, and the runtime
can re-execute it — that's the whole evolutionary loop.

---

## ⚠️ Security

The runtime **`exec()`s policy scripts**, and mutation/fusion produce
**LLM-authored code**. Treat every script as untrusted:

- run in a container / VM / sandbox, not on a machine with secrets or creds;
- review a champion before trusting it in an automated pipeline;
- the execution grader also runs candidate code — same rule.

This is inherent to evolving *executable* scaffolds. It is called out loudly on
purpose.

---

## What's the novel bit

Prompt-evolution work (PromptBreeder, DSPy) optimizes *prompts* inside a fixed
program. Here the thing under evolution is the **orchestration structure** —
fan-out, verification topology, pipeline-vs-barrier, model-per-role — carried as
a **shareable, per-project text weight**, with **human feedback** as the sparse,
authoritative reward.

Origin: this began as a Claude Code Workflow experiment. Toy accuracy tasks
(math, LeetCode-style code) *saturated* modern models and gave no gradient; the
signal that kept climbing was **design quality judged pairwise**. That finding is
the reason the loop is built around structure duels rather than benchmark scores.

---

## Roadmap

- [ ] Provider adapters (OpenAI, Gemini) behind the `agent()` interface — v1 is Anthropic-only
- [ ] Distil a promoted per-project champion back into the shared seed (with a confirm gate)
- [ ] Elo/Bradley-Terry aggregation when comparing >2 candidates
- [x] Subprocess-isolated execution grader for run-all (`--tests`) — see `evo/grade.py`
- [ ] Full container/VM sandbox for run-all + graders
- [ ] More seeds (test-authoring, refactor, triage)

## License

MIT — see [LICENSE](LICENSE).
