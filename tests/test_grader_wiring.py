"""Offline test for the objective grader bridge (evo/grade.py): correct/wrong solutions,
solution extraction, and subprocess timeout isolation. No network, no key. Runs in CI."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evo.grade import extract_solution, objective_grade, frac

TESTS = "TESTS = [((1, 2), 3), ((2, 2), 4), ((5, 5), 10), ((0, 0), 0)]"


def main():
    good = "def solve(a, b):\n    return a + b\n"
    bad = "def solve(a, b):\n    return a - b\n"

    g_good = objective_grade(good, TESTS)
    assert g_good == {"passed": 4, "total": 4}, g_good
    assert frac(g_good) == 1.0

    g_bad = objective_grade(bad, TESTS)
    assert g_bad["total"] == 4 and g_bad["passed"] <= 1, g_bad  # only (0,0)->0 could pass
    assert frac(g_bad) < 1.0

    # solution extraction: str, dict('solution'/'code'), and miss
    assert extract_solution(good) == good
    assert extract_solution({"solution": good}) == good
    assert extract_solution({"code": good}) == good
    assert extract_solution({"answer": 1}) is None
    assert extract_solution(None) is None

    # subprocess timeout isolation: a non-terminating candidate loses, doesn't hang parent
    loop = "def solve(a, b):\n    while True:\n        pass\n"
    g_to = objective_grade(loop, TESTS, timeout=4)
    assert g_to["passed"] == 0 and "timeout" in (g_to.get("error") or ""), g_to

    # a syntactically broken candidate -> 0, no crash
    g_syntax = objective_grade("def solve(a, b) return a+b", TESTS)
    assert g_syntax["passed"] == 0, g_syntax

    print("PASS grader wiring: correct/wrong grade, extract_solution, timeout isolation, bad-syntax")


if __name__ == "__main__":
    main()
