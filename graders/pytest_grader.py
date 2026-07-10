"""Optional execution grader for coding seeds.

Gives an OBJECTIVE reward (fraction of tests passed) instead of a judge verdict,
for run-all mode on code tasks. The tests file defines a module-level
`TESTS = [((arg1, arg2, ...), expected), ...]` and the solution defines an entry
function (default name `solve`).

    python graders/pytest_grader.py solution.py tests.py [entry_fn]
    -> {"passed": 5, "total": 6}

SECURITY: this exec()s candidate code. Run only in a sandbox/container.
"""

import json
import sys
import traceback


def grade(solution_src, tests_src, entry="solve"):
    sol_ns = {}
    try:
        exec(compile(solution_src, "<solution>", "exec"), sol_ns)  # noqa: S102
    except Exception:  # noqa: BLE001
        return {"passed": 0, "total": 0, "error": traceback.format_exc()}

    test_ns = {}
    try:
        exec(compile(tests_src, "<tests>", "exec"), test_ns)       # noqa: S102
    except Exception:  # noqa: BLE001
        return {"passed": 0, "total": 0, "error": "bad tests: " + traceback.format_exc()}

    cases = test_ns.get("TESTS", [])
    fn = sol_ns.get(entry)
    if fn is None or not cases:
        return {"passed": 0, "total": len(cases), "error": "no entry fn or no TESTS"}

    passed = 0
    for args, expected in cases:
        try:
            if fn(*args) == expected:
                passed += 1
        except Exception:  # noqa: BLE001 - a crash is just a failed case
            pass
    return {"passed": passed, "total": len(cases)}


if __name__ == "__main__":
    sol = open(sys.argv[1], encoding="utf-8").read()
    tst = open(sys.argv[2], encoding="utf-8").read()
    entry = sys.argv[3] if len(sys.argv) > 3 else "solve"
    print(json.dumps(grade(sol, tst, entry)))
