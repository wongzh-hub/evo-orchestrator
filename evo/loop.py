"""The unified loop:  GENERATE (arena) -> SELECT (duel) -> PERSIST (policy).

  activate(project, task_type, input)
    |- evo? --no--> run champion only, done
    v yes
  GENERATE  arena (default 2 rounds, early-stop on no-dethrone, prompt to extend)
    v            -> 1 evolved candidate (the "challenger")
  SELECT    duel: challenger  vs  incumbent champion
    |  mode a) human pick   b) design-judge (cheap)   c) run-all (2x, real output)
    |- SPLIT? -> FUSE best of both -> gate duel -> maybe carry fused
    v
  FEEDBACK  your verdict is authoritative (beats the judge)
    v
  PERSIST   promote winner -> policy.json (version++), append journal.md

The champion in policy.json is the current text "weight". Reward hierarchy:
user feedback > output comparison (mode c) > design judge (mode b).
"""

import argparse
import asyncio
import time
from pathlib import Path

from runtime.harness import Harness, run_script

from .policy import EvoStore
from .arena import run_arena
from .judge import duel, duel_outputs
from .fuse import fuse_and_gate

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"


def _stamp():
    return time.strftime("%Y-%m-%d %H:%M")


def _ask(prompt, choices=None):
    while True:
        ans = input(prompt).strip().lower()
        if not choices or ans in choices:
            return ans
        print(f"  choose one of: {', '.join(c or '<enter>' for c in choices)}")


def _report(h):
    m = h.meter
    print(f"\n[cost] {m.calls} calls · {m.in_tok}+{m.out_tok} tok · ~${m.usd:.3f}")


async def _select(h, brief, task_input, candidate, incumbent, mode):
    """Compare candidate (arena challenger) vs incumbent champion.
    Returns (winner_id, reasons, split)."""
    if mode == "a":  # human reads both scripts and picks
        print("\n===== CHALLENGER (arena) =====\n")
        print(candidate["script"][:2500] + ("\n...[truncated]" if len(candidate["script"]) > 2500 else ""))
        print("\n===== CHAMPION (incumbent) =====\n")
        print(incumbent["script"][:2500] + ("\n...[truncated]" if len(incumbent["script"]) > 2500 else ""))
        pick = _ask("\nPick better — [1] challenger  [2] champion: ", ["1", "2"])
        return ("challenger" if pick == "1" else "champion"), [], False

    if mode == "c":  # run both on the real input, compare OUTPUTS
        print("running BOTH scripts on the real input (mode c ~= 2x cost)...")
        a_out = await run_script(h, candidate["script"], task_input)
        b_out = await run_script(h, incumbent["script"], task_input)
        res = await duel_outputs(h, brief,
                                 {"id": "challenger", "out": a_out},
                                 {"id": "champion", "out": b_out})
        return res["winner"], res["reasons"], res["split"]

    # mode b (default): cheap design-judge on structure, no execution
    res = await duel(h, brief, candidate, incumbent)
    return res["winner"], res["reasons"], res["split"]


async def run_evo(project_dir, task_type, task_input, *, rounds=2,
                  interactive=True, mode=None, do_evo=None):
    evo_dir = Path(project_dir) / "evo"
    store = EvoStore(evo_dir)
    h = Harness()
    brief = f"Task type: {task_type}\nInput: {task_input}"

    # 1. ensure a champion exists (fork the seed on first use)
    if not store.exists():
        seed = SEEDS_DIR / f"{task_type}.py"
        if not seed.exists():
            raise SystemExit(
                f"no seed for task type '{task_type}' in {SEEDS_DIR} "
                f"(available: {[p.stem for p in SEEDS_DIR.glob('*.py')]})"
            )
        store.init(seed, task_type, task_type)
        print(f"initialized champion from seed '{task_type}' (v1)")

    incumbent = {"id": "champion", "script": store.champion_script()}

    # 2. evolve or not
    if do_evo is None:
        do_evo = interactive and _ask("Evolve this run? [y/N]: ", ["y", "n", ""]) == "y"
    if not do_evo:
        print(f"running champion only (v{store.policy()['version']})...")
        result = await run_script(h, incumbent["script"], task_input)
        store.log(f"champion-only: ran v{store.policy()['version']}; "
                  f"cost=${h.meter.usd:.3f}", _stamp())
        _report(h)
        return result

    # 3. GENERATE — arena
    if interactive:
        r = _ask(f"Arena rounds [default {rounds}]: ", None)
        if r.isdigit():
            rounds = int(r)
    print(f"running arena ({rounds} rounds)...")
    cand_src, traj = await run_arena(h, brief, incumbent["script"],
                                     store.journal_tail(), rounds=rounds)
    if interactive and traj and traj[-1].get("dethroned"):
        if _ask("Champion was dethroned — run more rounds? [y/N]: ", ["y", "n", ""]) == "y":
            cand_src, _ = await run_arena(h, brief, cand_src,
                                          store.journal_tail(), rounds=rounds)

    if cand_src.strip() == incumbent["script"].strip():
        print("arena produced no improvement over the incumbent; champion kept.")
        store.log("arena: no candidate beat the champion; kept", _stamp())
        _report(h)
        return None

    candidate = {"id": "challenger", "script": cand_src}
    store.set_challenger(cand_src, origin="arena")

    # 4. SELECT
    if mode is None:
        mode = _ask("Select mode — a) human  b) design-judge  c) run-all  [b]: ",
                    ["a", "b", "c", ""]) or "b" if interactive else "b"
    winner_id, reasons, split = await _select(h, brief, task_input,
                                              candidate, incumbent, mode)
    carried = candidate if winner_id == "challenger" else incumbent

    # 4b. optional FUSE on a split verdict
    if split:
        do_fuse = True
        if interactive:
            do_fuse = _ask("Judge split (each side won some dimensions) — fuse best of "
                           "both? [Y/n]: ", ["y", "n", ""]) != "n"
        if do_fuse:
            fused = await fuse_and_gate(h, brief, candidate, incumbent, reasons, winner_id)
            if fused:
                carried = fused
                candidate = fused  # fused is now the promotable challenger

    # 5. FEEDBACK — authoritative, overrides the judge
    feedback = "none"
    if interactive:
        print(f"\njudge/candidate verdict: winner = {carried['id']}")
        fb = _ask("Your verdict — [g]ood (promote the evolved candidate) / "
                  "[b]ad (reject, keep champion) / [enter] accept judge: ", ["g", "b", ""])
        feedback = fb or "accept-judge"
        if fb == "g":
            carried = candidate          # you override the judge -> promote candidate
        elif fb == "b":
            carried = incumbent          # you reject -> champion holds

    # 6. PERSIST
    promoting = carried["id"] != "champion"
    if promoting:
        v = store.promote(carried["script"], origin=carried["id"], stamp=_stamp())
        print(f"promoted {carried['id']} -> champion (v{v})")
        outcome = f"promoted {carried['id']} to v{v}"
    else:
        store.clear_challenger()
        print("champion held; no promotion.")
        outcome = "champion held"

    store.log(f"mode={mode}; {outcome}; feedback={feedback}; "
              f"split={split}; cost=${h.meter.usd:.3f}", _stamp())
    _report(h)
    return {"promoted": promoting, "outcome": outcome, "version": store.policy()["version"]}


async def run_cli():
    ap = argparse.ArgumentParser(
        prog="evo",
        description="Self-tuning workflow runner (evolve orchestration scripts as text weights).",
    )
    ap.add_argument("project_dir", help="project directory; evo state goes in <dir>/evo/")
    ap.add_argument("--task", required=True, help="task type = seed name (e.g. research)")
    ap.add_argument("--input", default="", help="task input / brief")
    ap.add_argument("--rounds", type=int, default=2, help="arena rounds (default 2)")
    ap.add_argument("--mode", choices=["a", "b", "c"],
                    help="select mode: a=human, b=design-judge, c=run-all")
    ap.add_argument("--evo", dest="do_evo", action="store_true",
                    help="force evolution on (skip the prompt)")
    ap.add_argument("--no-evo", dest="no_evo", action="store_true",
                    help="run champion only")
    ap.add_argument("--yes", action="store_true",
                    help="non-interactive: accept defaults, no prompts")
    a = ap.parse_args()

    do_evo = True if a.do_evo else (False if a.no_evo else None)
    await run_evo(a.project_dir, a.task, a.input, rounds=a.rounds,
                  interactive=not a.yes, mode=a.mode, do_evo=do_evo)


if __name__ == "__main__":
    asyncio.run(run_cli())
