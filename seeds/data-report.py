"""Seed: data-report — turn tabular data into verified stats + chart specs + narrative.

args: {"data": "<csv/markdown table>", "goal": "what to surface"}
Every statistic is independently recomputed by a stronger model before it is used
in the narrative (numbers verified vs the raw data).
"""

META = {
    "name": "data-report",
    "description": "Summarize a dataset into verified stats, chart specs, and a narrative.",
    "phases": ["Stats", "Verify", "Narrate"],
}

STAT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"stats": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"name": {"type": "string"}, "value": {"type": "string"},
                       "how": {"type": "string"}},
        "required": ["name", "value", "how"]}}},
    "required": ["stats"],
}
OK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"correct": {"type": "boolean"}, "fix": {"type": "string"}},
    "required": ["correct", "fix"],
}


async def run(agent, parallel, pipeline, log, phase, args):
    a = args or {}
    data = a.get("data", "")
    goal = a.get("goal", "summarize the key trends")

    phase("Stats")
    s = await agent(
        f"Goal: {goal}\nCompute the key summary statistics from this data. For each, show "
        "exactly how it was derived.\n\n" + data,
        label="stats", phase="Stats", model="sonnet", schema=STAT_SCHEMA)
    stats = (s or {}).get("stats", [])

    phase("Verify")
    async def check(st):
        v = await agent(
            f"Independently recompute and verify: {st['name']} = {st['value']} "
            f"(claimed method: {st['how']}).\n\nDATA:\n{data}",
            label=f"verify:{st['name'][:16]}", phase="Verify", model="opus", schema=OK_SCHEMA)
        return {**st, "ok": bool(v and v.get("correct")), "fix": (v or {}).get("fix", "")}
    checked = await parallel([(lambda st=st: check(st)) for st in stats])
    good = [c for c in checked if c and c["ok"]]
    log(f"{len(good)}/{len(stats)} stats verified")

    phase("Narrate")
    narrative = await agent(
        f"Write a short report for goal '{goal}' using ONLY these verified statistics:\n"
        + "\n".join(f"- {c['name']}: {c['value']}" for c in good),
        label="narrate", phase="Narrate", model="opus")

    chart_specs = [{"type": "bar", "metric": c["name"], "value": c["value"]} for c in good[:5]]
    return {"narrative": narrative, "stats": good, "chart_specs": chart_specs}
