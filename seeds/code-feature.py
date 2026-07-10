"""Seed: code-feature — implement a feature across files: plan, write per-file, self-review.

args: {"spec": "...", "files": [{"path","content"}, ...]}
Coding seeds pair well with the optional execution grader (graders/pytest_grader.py)
in run-all mode: swap the review agent for real test runs to get an objective reward.
"""

META = {
    "name": "code-feature",
    "description": "Implement a feature: plan, generate per-file changes, self-review.",
    "phases": ["Plan", "Implement", "Review"],
}

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"steps": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"path": {"type": "string"}, "change": {"type": "string"}},
        "required": ["path", "change"]}}},
    "required": ["steps"],
}
NEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"content": {"type": "string"}, "note": {"type": "string"}},
    "required": ["content", "note"],
}
REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"approved": {"type": "boolean"}, "issues": {"type": "string"}},
    "required": ["approved", "issues"],
}


async def run(agent, parallel, pipeline, log, phase, args):
    a = args or {}
    spec = a.get("spec", "")
    files = a.get("files", [])                      # [{"path","content"}]
    by_path = {f["path"]: f["content"] for f in files}

    phase("Plan")
    plan = await agent(
        f"Plan the MINIMAL edits to implement this feature:\n{spec}\n\nExisting files:\n"
        + "\n".join(f"- {f['path']}" for f in files),
        label="plan", phase="Plan", model="opus", schema=PLAN_SCHEMA)
    steps = (plan or {}).get("steps", [])

    phase("Implement")
    async def implement(step):
        cur = by_path.get(step["path"], "")
        r = await agent(
            f"Apply this change and return the FULL new file content.\n"
            f"CHANGE: {step['change']}\nFEATURE SPEC: {spec}\n\n"
            f"CURRENT ({step['path']}):\n{cur}",
            label=f"impl:{step['path']}", phase="Implement", model="sonnet", schema=NEW_SCHEMA)
        return {"path": step["path"], "content": (r or {}).get("content", ""),
                "note": (r or {}).get("note", "")}
    edits = [e for e in await parallel([(lambda s=s: implement(s)) for s in steps]) if e]

    phase("Review")
    async def review(e):
        v = await agent(
            "Review this edit against the spec. Flag bugs/omissions; approve only if correct.\n"
            f"SPEC: {spec}\nFILE {e['path']}:\n{e['content']}",
            label=f"review:{e['path']}", phase="Review", model="opus", schema=REVIEW_SCHEMA)
        return {**e, "approved": bool(v and v.get("approved")), "issues": (v or {}).get("issues", "")}
    reviewed = [r for r in await parallel([(lambda e=e: review(e)) for e in edits]) if r]

    approved = sum(1 for r in reviewed if r["approved"])
    log(f"{approved}/{len(reviewed)} edits approved")
    return {"edits": reviewed, "approved": approved, "total": len(reviewed)}
