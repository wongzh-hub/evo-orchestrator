"""Seed: doc-extract — extract a fixed schema from documents, no silent drops.

args: {"docs": [{"id","text"}, ...], "fields": ["title","date","summary", ...]}
"""

META = {
    "name": "doc-extract",
    "description": "Extract structured fields from documents against a fixed schema.",
    "phases": ["Extract"],
}


async def run(agent, parallel, pipeline, log, phase, args):
    a = args or {}
    docs = a.get("docs", [])                       # [{"id","text"}]
    fields = a.get("fields", ["title", "date", "summary"])
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {f: {"type": "string"} for f in fields},
        "required": fields,
    }

    async def extract(d):
        r = await agent(
            "Extract exactly these fields. Use \"\" if a field is genuinely absent — never "
            f"guess or fabricate:\n{fields}\n\nDOCUMENT:\n{d['text']}",
            label=f"extract:{d['id']}", phase="Extract", model="sonnet", schema=schema)
        return {"id": d["id"], "fields": r}

    got = await parallel([(lambda d=d: extract(d)) for d in docs])
    records = [g for g in got if g and g.get("fields")]
    missing = [d["id"] for d, g in zip(docs, got) if not (g and g.get("fields"))]
    if missing:
        log(f"WARNING: no extraction for {missing} (reported, not silently dropped)")
    return {"records": records, "missing": missing,
            "extracted": len(records), "total": len(docs)}
