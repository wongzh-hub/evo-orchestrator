"""Seed: research — multi-angle gather, adversarial per-claim fact-check, synthesize.

args: a question string, or {"question": "..."}.
"""

META = {
    "name": "research",
    "description": "Answer a research question with sourced, fact-checked claims.",
    "phases": ["Gather", "Verify", "Synthesize"],
}

CLAIM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"claims": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"claim": {"type": "string"}, "support": {"type": "string"}},
        "required": ["claim", "support"]}}},
    "required": ["claims"],
}
VERDICT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"supported": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["supported", "why"],
}


async def run(agent, parallel, pipeline, log, phase, args):
    question = args if isinstance(args, str) else (args or {}).get("question", "")

    phase("Gather")
    angles = ["core definitions & established facts",
              "recent developments & data",
              "counter-evidence, caveats & failure modes"]
    gathered = await parallel([
        (lambda a=a: agent(
            f"Research this angle — '{a}' — for the question:\n{question}\n\n"
            "Return 3-6 concrete factual claims, each with its supporting evidence.",
            label=f"gather:{a[:18]}", phase="Gather", model="sonnet", schema=CLAIM_SCHEMA))
        for a in angles])
    claims = [c for g in gathered if g for c in g.get("claims", [])]
    log(f"gathered {len(claims)} claims")

    phase("Verify")
    async def verify(c):
        v = await agent(
            "Adversarially fact-check this claim. Try to REFUTE it; set supported=false "
            "if the evidence is weak, dated, or over-generalized.\n"
            f"CLAIM: {c['claim']}\nSTATED SUPPORT: {c['support']}",
            label="verify", phase="Verify", model="opus", schema=VERDICT_SCHEMA)
        return {**c, "verdict": v}
    checked = await parallel([(lambda c=c: verify(c)) for c in claims])
    kept = [c for c in checked if c and c.get("verdict") and c["verdict"]["supported"]]
    log(f"{len(kept)}/{len(claims)} claims survived fact-check")

    phase("Synthesize")
    answer = await agent(
        f"Write a concise, well-structured answer to:\n{question}\n\n"
        "Use ONLY these verified claims; do not add unsupported statements:\n"
        + "\n".join(f"- {c['claim']}" for c in kept),
        label="synthesize", phase="Synthesize", model="opus")

    return {"question": question, "answer": answer,
            "claims_verified": len(kept), "claims_total": len(claims)}
