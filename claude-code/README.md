# Claude Code edition — the `evo-tune` plugin

For **Claude Code users with no Anthropic API key** — this edition runs inside
Claude Code on your existing subscription. (The [standalone Python edition](../)
at the repo root needs an API key; this one does not.)

This folder **is** a Claude Code plugin.

## Structure
```
claude-code/
  .claude-plugin/plugin.json   plugin manifest
  skills/evo-tune/             the self-tuning skill (SKILL.md + evo_io.py)
  commands/evo.md              the /evo slash command
  seeds/*.js                   7 workflow seeds (research, sec-review, migrate,
                               doc-extract, data-report, code-feature, bug-fix)
  README.md                    this file
```

## Install (via the repo's marketplace)
```
/plugin marketplace add wongzh-hub/evo-orchestrator
/plugin install evo-tune
```
Then run:
```
/evo <project-dir> [task-type]
```
or just say **"evo-tune"** / **"run <project> with evo"** / **"tune this workflow"**.

Installing wires up the skill, the `/evo` command, and the seeds automatically —
no manual copying. Skill/command paths resolve via `${CLAUDE_PLUGIN_ROOT}`.

## How it works
Each seed is a Workflow script: `export const meta = {...}` then a body that calls
the Workflow primitives (`agent`, `parallel`, `pipeline`, `log`, `phase`) and
`return`s a result. On first use of a task type, `evo-tune` forks the matching seed
into `<project>/evo/policy.json` as the v1 champion and evolves from there —
champion vs challenger, your feedback as the reward, improving across runs.

## Relationship to the standalone edition
Same loop, two runtimes:

| | Claude Code plugin (here) | Standalone edition (repo root) |
|---|---|---|
| runs in | Claude Code (your subscription) | any machine with `ANTHROPIC_API_KEY` |
| seeds | `.js` Workflow scripts | `.py` policy scripts |
| the loop | the `evo-tune` skill | `evo/loop.py` (arena / duel / fuse) |
| API key | not needed | needed |

The seeds are intentionally minimal — they call the Workflow primitives and nothing
more. The full engine (breeding arena, tournament) lives as portable Python in the
standalone edition; it is not required to use these seeds.

## Note on portability
These seeds carry no machine-specific paths or environment assumptions. If you adapt
one to read files or search the web, wire in your own tools — keep local paths out of
anything you publish.
