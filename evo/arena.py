"""GENERATE stage: evolve the champion via mutation + pairwise duel.

Runs R rounds (default 2). Each round mutates the current best into a challenger
and duels them on structure (cheap design-judge). The winner carries forward.
Early-stops the moment a round fails to dethrone the incumbent (no progress).

Output: a single evolved candidate script (may equal the champion if nothing
beat it) plus a trajectory for the journal.
"""

from collections import Counter

from .judge import duel

# alternating mutation pressure across rounds
MUTATE_FOCI = [
    "correctness & verification coverage",
    "robustness, cost-awareness & partial-failure handling",
]

SCRIPT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"script": {"type": "string"}},
    "required": ["script"],
}


async def mutate(h, script, journal_tail, focus):
    prompt = (
        "You improve a multi-agent WORKFLOW DESIGN written as a Python policy script.\n"
        "It defines `async def run(agent, parallel, pipeline, log, phase, args)` and an\n"
        "optional module-level META dict. KEEP that contract intact and runnable.\n"
        f"Make ONE meaningful improvement focused on: {focus}. Right-size, do not bloat.\n"
        "Improve against this rubric: decomposition, fan-out sizing, verification/\n"
        "adversarial coverage, timeout/partial-failure handling, schema use, prompt\n"
        "quality, cost-awareness. Avoid anti-patterns (needless barriers, silent caps,\n"
        "no self-heal, over/under-engineering).\n"
        f"\nWhat past runs learned (journal tail):\n{journal_tail or '(none)'}\n"
        f"\nCURRENT SCRIPT:\n{script}\n\n"
        "Return ONLY the full improved Python script as the 'script' field."
    )
    r = await h.agent(prompt, label=f"mutate [{focus[:20]}]", phase="Generate",
                      model="opus", schema=SCRIPT_SCHEMA)
    return r["script"] if r and r.get("script") else None


async def run_arena(h, brief, champion_script, journal_tail="", rounds=2):
    """Returns (candidate_script, trajectory)."""
    best = {"id": "champion", "script": champion_script}
    traj = []
    focus = MUTATE_FOCI[0]  # round-0 seed; later rounds are DIRECTED by the judge's losses
    for rnd in range(rounds):
        mutant_src = await mutate(h, best["script"], journal_tail, focus)
        if not mutant_src:
            traj.append({"round": rnd, "result": "mutate_failed"})
            h.log(f"arena round {rnd}: mutation failed; keeping current best")
            break
        challenger = {"id": f"mutant{rnd}", "script": mutant_src}
        res = await duel(h, brief, best, challenger, incumbent_id=best["id"])
        dethroned = res["winner"] == challenger["id"]
        traj.append({"round": rnd, "winner": res["winner"], "focus": focus,
                     "dethroned": dethroned, "split": res["split"]})
        h.log(f"arena round {rnd}: winner={res['winner']} dethroned={dethroned}")
        if dethroned:
            best = challenger
        else:
            h.log("champion held this round; early-stopping arena")
            break
        # DIRECTED mutation: aim the next round at the dimensions the current best
        # still lost, mined from the judge's per-dimension verdicts (not a fixed cycle)
        lost = [r["dimension"] for r in res.get("reasons", []) if r["favored"] != best["id"]]
        if lost:
            top = [d for d, _ in Counter(lost).most_common(3)]
            focus = ("the judge still penalized this design on: " + ", ".join(top)
                     + " — target those specifically")
        else:
            focus = MUTATE_FOCI[(rnd + 1) % len(MUTATE_FOCI)]
    return best["script"], traj
