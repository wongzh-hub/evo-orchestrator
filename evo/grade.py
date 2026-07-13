"""Objective grading bridge for coding tasks.

Runs the standalone execution grader (`graders/pytest_grader.py`) in a SUBPROCESS
with a timeout, so untrusted candidate code gets process isolation and cannot hang
or corrupt the parent evo loop. Used by SELECT mode c when a `--tests` spec is
given and the candidate's output carries a solution; otherwise the loop falls back
to the LLM output-judge.

This is a lightweight sandbox (separate process + wall-clock timeout), not a full
container. Treat candidate code as untrusted regardless — see the README SECURITY
section for the container/VM recommendation.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

GRADER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "graders", "pytest_grader.py",
)


def extract_solution(out):
    """Pull solution source from a candidate's run() output.
    Accepts a str (the source itself) or a dict with a 'solution' / 'code' field.
    Returns None when no solution can be found (caller falls back to the judge)."""
    if isinstance(out, str) and out.strip():
        return out
    if isinstance(out, dict):
        for key in ("solution", "code"):
            val = out.get(key)
            if isinstance(val, str) and val.strip():
                return val
    return None


def objective_grade(solution_src, tests_src, entry="solve", timeout=15):
    """Grade solution_src against tests_src via the grader subprocess.
    Returns {"passed": int, "total": int[, "error": str]}. A timeout or crash
    yields passed=0 (a non-terminating or broken candidate simply loses)."""
    if not solution_src or not tests_src:
        return {"passed": 0, "total": 0, "error": "missing solution or tests"}
    d = tempfile.mkdtemp(prefix="evograde_")
    try:
        sol = os.path.join(d, "solution.py")
        tst = os.path.join(d, "tests.py")
        with open(sol, "w", encoding="utf-8") as f:
            f.write(solution_src)
        with open(tst, "w", encoding="utf-8") as f:
            f.write(tests_src)
        try:
            r = subprocess.run(
                [sys.executable, GRADER, sol, tst, entry],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"passed": 0, "total": 0, "error": f"timeout after {timeout}s"}
        out = (r.stdout or "").strip()
        try:
            return json.loads(out.splitlines()[-1])
        except Exception:  # noqa: BLE001
            return {"passed": 0, "total": 0,
                    "error": (r.stderr or out or "no grader output")[:400]}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def frac(g):
    """Pass fraction (0..1) from a grade dict; 0 when no tests ran."""
    total = g.get("total") or 0
    return (g.get("passed", 0) / total) if total else 0.0
