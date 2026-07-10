"""Seed: sec-review — review a diff across dimensions, adversarially verify each finding.

args: a diff/code string, or {"diff": "..."}.
Uses pipeline: each dimension's findings verify as soon as that dimension is done,
instead of waiting for all dimensions (no needless barrier).
"""

META = {
    "name": "sec-review",
    "description": "Find correctness + security issues in a diff; verify each before reporting.",
    "phases": ["Review", "Verify"],
}

FIND_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"findings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"title": {"type": "string"}, "location": {"type": "string"},
                       "detail": {"type": "string"}},
        "required": ["title", "location", "detail"]}}},
    "required": ["findings"],
}
VERDICT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"real": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["real", "why"],
}

DIMENSIONS = [
    ("correctness", "logic bugs, edge cases, off-by-one, error handling, nullability"),
    ("security", "injection, authz, secrets, unsafe deserialization, path traversal, SSRF"),
    ("resource", "leaks, unbounded growth, blocking I/O on hot paths, races, deadlock"),
]


async def run(agent, parallel, pipeline, log, phase, args):
    diff = args if isinstance(args, str) else (args or {}).get("diff", "")

    async def review(dim, _item, _idx):
        key, desc = dim
        r = await agent(
            f"Review this diff for {key} issues ({desc}). Be specific and cite locations.\n\n"
            f"DIFF:\n{diff}",
            label=f"review:{key}", phase="Review", model="sonnet", schema=FIND_SCHEMA)
        return (key, (r or {}).get("findings", []))

    async def verify_stage(prev, _dim, _idx):
        key, findings = prev
        async def ver(f):
            v = await agent(
                f"Adversarially verify this {key} finding. Try to REFUTE it; set real=false "
                "unless it is clearly triggerable/exploitable given the diff.\n"
                f"TITLE: {f['title']}\nLOCATION: {f['location']}\nDETAIL: {f['detail']}\n\n"
                f"DIFF:\n{diff}",
                label=f"verify:{key}", phase="Verify", model="opus", schema=VERDICT_SCHEMA)
            return {**f, "dimension": key, "verdict": v}
        return await parallel([(lambda f=f: ver(f)) for f in findings])

    results = await pipeline(DIMENSIONS, review, verify_stage)
    confirmed = [f for group in results if group for f in group
                 if f and f.get("verdict") and f["verdict"]["real"]]
    log(f"{len(confirmed)} confirmed findings")
    return {"findings": confirmed, "count": len(confirmed)}
