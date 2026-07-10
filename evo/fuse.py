"""Optional recombination (crossover).

Fires when a SELECT duel is SPLIT — neither candidate sweeps the judged
dimensions, so each owns something worth keeping. A splice agent merges the
winning parts of both into a child, using the judge's per-dimension verdicts as
the guide. The child is NOT trusted: it must win one more gate duel against the
current winner before it can be promoted (fusion often regresses).
"""

from .judge import duel

SCRIPT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"script": {"type": "string"}},
    "required": ["script"],
}


async def splice(h, brief, A, B, reasons):
    verdicts = "\n".join(
        f"- [{r['dimension']}] favored {r['favored']}: {r['note']}" for r in reasons
    ) or "(no per-dimension detail)"
    prompt = (
        "Two multi-agent WORKFLOW DESIGNS (Python policy scripts) each win on different\n"
        "dimensions. Produce a CHILD that takes the best part of each. KEEP the contract:\n"
        "`async def run(agent, parallel, pipeline, log, phase, args)` + optional META,\n"
        "fully runnable. Integrate cleanly — no frankenstein, no dead code, right-sized.\n"
        f"\nTASK BRIEF:\n{brief}\n"
        f"\nPER-DIMENSION VERDICTS (who won what):\n{verdicts}\n"
        f"\n--- DESIGN {A['id']} ---\n{A['script']}\n"
        f"\n--- DESIGN {B['id']} ---\n{B['script']}\n\n"
        "Return ONLY the merged Python script as the 'script' field."
    )
    r = await h.agent(prompt, label="fuse/splice", phase="Fuse",
                      model="opus", schema=SCRIPT_SCHEMA)
    return r["script"] if r and r.get("script") else None


async def fuse_and_gate(h, brief, A, B, reasons, winner_id):
    """Splice A+B, then duel the child vs the current winner. Returns the child
    {'id':'fused','script':...} only if it beats the winner; else None."""
    child_src = await splice(h, brief, A, B, reasons)
    if not child_src:
        h.log("fusion produced no script; skipping")
        return None
    child = {"id": "fused", "script": child_src}
    winner = A if winner_id == A["id"] else B
    res = await duel(h, brief, child, winner)
    if res["winner"] == "fused":
        h.log("fused child beat the current winner; carrying fused")
        return child
    h.log("fused child did not beat the winner; discarding")
    return None
