# Changelog

## 0.1.0 — 2026-07-13

First tagged release: hardening, a real Claude Code internal arena, objective grading, and packaging.

### Fixed
- **CLI silently did nothing without a key.** `run_cli()` now loads `.env` and fails fast if
  `ANTHROPIC_API_KEY` is missing; a run where every model call failed prints a warning
  instead of a green success (was: exit 0, empty output, success-looking journal).
- **Mode-c crash.** A throwing LLM-authored candidate no longer aborts the whole run — it is
  treated as a loss and the champion is held.
- **Promotion safety.** A genuine judge tie holds the incumbent (never promotes a challenger
  on a coin-flip); a no-signal comparison (both judge calls failed) holds the champion
  instead of promoting a phantom winner under `--yes`.
- **policy.json durability.** Writes are atomic (temp + `os.replace`); `promote()` keeps a
  `.bak`; an unreadable `policy.json` falls back to that backup.

### Added
- **Objective grading.** `--tests <file>` routes SELECT mode c through `evo/grade.py`, which
  runs `graders/pytest_grader.py` in a **subprocess with a timeout** (process isolation) when
  a candidate emits a `solution`/`code` field; falls back to the LLM judge otherwise. Closes
  the "grader shipped but never wired in" gap.
- **Claude Code internal arena.** The `evo-tune` skill now generates its challenger via a real
  multi-round arena (`claude-code/skills/evo-tune/arena.workflow.js`) — mutate → order-swapped
  duel → carry, early-stop — matching the Python `evo/arena.py`. Previously a one-shot mutation.
- **Packaging.** `pyproject.toml` + an `evo` console entry point (`pip install -e .`); pinned
  dependency upper bounds (`anthropic>=0.40,<1.0`, etc.).
- **Tests/CI.** Offline harness-contract and grader-wiring tests, wired into CI.

### Changed
- **Directed mutation.** Each arena round targets the dimensions the judge just penalized
  (mined from per-dimension verdicts) instead of a fixed 2-item cycle.
- **Seed timeout guards.** All 7 `claude-code/seeds/*.js` wrap every `agent()` in a
  `Promise.race` timeout so a hung agent can't stall a `parallel()` barrier.
- **Cleanup / hardening.** Removed dead code (`extract_meta`, unused `judge.DIMENSIONS`);
  hardened both `evo_io.py` copies (usage guard, `promote` null-guard, `get` validation); the
  judge prompts now mark candidate content as untrusted (prompt-injection).

### Docs
- Documented the **judge self-preference** caveat (judge = mutator = fuser share a model;
  user feedback re-anchors it).
- Fixed stale `CLAUDE.md` claims (CI does run tests; the Claude Code edition ships in-repo
  under `claude-code/`).

### Upgrade note
- `python evo.py` now **requires `ANTHROPIC_API_KEY`** and errors out if it is missing —
  previously it ran to a no-op "success". Set the key (or create `.env`) before running.
