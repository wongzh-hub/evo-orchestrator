# Seed library

Each `*.py` here is a **starting champion** for one task type — a real, readable
multi-agent workflow. On first use of a task type, the loop forks the matching
seed into `<project>/evo/policy.json` as the v1 champion, then evolves from there.

A seed is a policy script: a module with an optional `META` dict and

```python
async def run(agent, parallel, pipeline, log, phase, args):
    ...
    return <result>
```

| Seed | Task | Shape |
|------|------|-------|
| `research` | answer a question | gather (multi-angle) → adversarial per-claim fact-check → synthesize |
| `sec-review` | audit a diff | dimensions → find → adversarially verify each (pipeline) |
| `migrate` | change an API across files | discover → transform → verify, per-file pipeline |
| `doc-extract` | pull fixed fields from docs | parallel extract, no silent drops |
| `data-report` | data → narrative | stats → independently verify each number → narrate |
| `code-feature` | implement a feature | plan → per-file implement → self-review |
| `bug-fix` | fix a bug | reproduce → locate root cause → patch → verify |

`code-feature` and `bug-fix` can be graded objectively (run tests) instead of by
judge — see `../graders/pytest_grader.py` and run-all mode.

These are **starting points**, not frozen. The whole idea is that evolution
rewrites them per project. To add a task type, drop a new `<name>.py` here.
