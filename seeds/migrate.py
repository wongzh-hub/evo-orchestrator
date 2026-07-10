"""Seed: migrate — migrate a deprecated API across many files.

args: {"old_api": "...", "new_api": "...", "files": [{"path","content"}, ...]}
Pipeline per file (discover -> transform -> verify) so one bad file never sinks
the batch; unaffected files are skipped cheaply on a haiku scan.
"""

META = {
    "name": "migrate",
    "description": "Migrate a deprecated API across files; transform + verify each; tolerate partial failure.",
    "phases": ["Discover", "Transform", "Verify"],
}

SITES_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"uses": {"type": "boolean"},
                   "spans": {"type": "array", "items": {"type": "string"}}},
    "required": ["uses", "spans"],
}
NEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"changed": {"type": "boolean"}, "content": {"type": "string"},
                   "note": {"type": "string"}},
    "required": ["changed", "content", "note"],
}
OK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"ok": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["ok", "why"],
}


async def run(agent, parallel, pipeline, log, phase, args):
    a = args or {}
    old_api, new_api = a.get("old_api", ""), a.get("new_api", "")
    files = a.get("files", [])  # [{"path","content"}]

    async def discover(f, _f, _i):
        r = await agent(
            f"Does this file use `{old_api}`? If so, list the call-site snippets.\n\n"
            f"FILE {f['path']}:\n{f['content']}",
            label=f"scan:{f['path']}", phase="Discover", model="haiku", schema=SITES_SCHEMA)
        return {"file": f, "sites": r}

    async def transform(prev, _f, _i):
        f, sites = prev["file"], prev["sites"]
        if not sites or not sites.get("uses"):
            return {"path": f["path"], "skipped": True}
        r = await agent(
            f"Migrate `{old_api}` -> `{new_api}` in this file. Preserve behavior exactly. "
            "Return the FULL new file content.\n\n"
            f"FILE {f['path']}:\n{f['content']}",
            label=f"xform:{f['path']}", phase="Transform", model="sonnet", schema=NEW_SCHEMA)
        return {"path": f["path"], "result": r}

    async def verify(prev, _f, _i):
        if prev.get("skipped"):
            return prev
        r = prev.get("result")
        if not r or not r.get("changed"):
            return {"path": prev["path"], "verified": False, "reason": "no change produced"}
        v = await agent(
            f"Does this migrated file use `{new_api}` correctly and preserve the original "
            "behavior? Flag any regression.\n\n"
            f"FILE {prev['path']}:\n{r['content']}",
            label=f"verify:{prev['path']}", phase="Verify", model="opus", schema=OK_SCHEMA)
        return {"path": prev["path"], "verified": bool(v and v.get("ok")),
                "content": r["content"], "reason": (v or {}).get("why", "")}

    out = await pipeline(files, discover, transform, verify)
    migrated = [o for o in out if o and o.get("verified")]
    skipped = [o for o in out if o and o.get("skipped")]
    failed = [o for o in out if o and not o.get("verified") and not o.get("skipped")]
    log(f"{len(migrated)} migrated, {len(skipped)} skipped, {len(failed)} failed")
    return {"migrated": migrated, "skipped": len(skipped), "failed": failed}
