"""Seed: bug-fix — reproduce, locate root cause, patch, verify.

args: {"report": "...", "code": "<source>", "tests": "<optional TESTS spec>"}
When `tests` is provided you can grade objectively instead of by judge — see
graders/pytest_grader.py and run-all (mode c).
"""

META = {
    "name": "bug-fix",
    "description": "Fix a reported bug: reproduce, locate root cause, patch, verify.",
    "phases": ["Reproduce", "Locate", "Fix", "Verify"],
}

LOC_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"root_cause": {"type": "string"}, "location": {"type": "string"}},
    "required": ["root_cause", "location"],
}
FIX_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"content": {"type": "string"}, "explanation": {"type": "string"}},
    "required": ["content", "explanation"],
}
VERIFY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"fixed": {"type": "boolean"}, "regressions": {"type": "string"}},
    "required": ["fixed", "regressions"],
}


async def run(agent, parallel, pipeline, log, phase, args):
    a = args or {}
    report, code, tests = a.get("report", ""), a.get("code", ""), a.get("tests", "")

    phase("Reproduce")
    repro = await agent(
        f"State the exact failing behavior and a minimal reproduction.\n"
        f"REPORT: {report}\n\nCODE:\n{code}",
        label="reproduce", phase="Reproduce", model="sonnet")

    phase("Locate")
    loc = await agent(
        f"Find the ROOT CAUSE (not the symptom).\nREPRO: {repro}\n\nCODE:\n{code}",
        label="locate", phase="Locate", model="opus", schema=LOC_SCHEMA)

    phase("Fix")
    fix = await agent(
        "Patch the root cause with the SMALLEST correct change. Return the full new file.\n"
        f"ROOT CAUSE: {(loc or {}).get('root_cause', '')}\n\nCODE:\n{code}",
        label="fix", phase="Fix", model="sonnet", schema=FIX_SCHEMA)

    phase("Verify")
    tests_clause = (f"\nCheck against these tests:\n{tests}" if tests else "")
    ver = await agent(
        "Does this patch fix the bug without regressions?" + tests_clause + "\n"
        f"REPORT: {report}\nPATCH:\n{(fix or {}).get('content', '')}",
        label="verify", phase="Verify", model="opus", schema=VERIFY_SCHEMA)

    return {"root_cause": (loc or {}).get("root_cause", ""),
            "patch": (fix or {}).get("content", ""),
            "explanation": (fix or {}).get("explanation", ""),
            "fixed": bool(ver and ver.get("fixed")),
            "regressions": (ver or {}).get("regressions", "")}
