"""Offline seed test — exec every seed through the real runtime with a stub agent.

Proves each seed is a runnable policy script (correct run() contract, primitive
calls, arg handling) — not just importable. The stub synthesizes a minimal valid
object for any JSON schema, and plain text otherwise. No network / key needed.

    python tests/smoke_seeds.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-offline")

from pathlib import Path              # noqa: E402
from runtime.harness import Harness, run_script   # noqa: E402

SEEDS = Path(__file__).resolve().parent.parent / "seeds"


def synth(schema):
    """Minimal instance satisfying a (simple) JSON schema."""
    t = schema.get("type")
    if t == "object":
        req = schema.get("required", list(schema.get("properties", {})))
        return {k: synth(v) for k, v in schema.get("properties", {}).items() if k in req}
    if t == "array":
        item = schema.get("items")
        return [synth(item)] if item else []
    if t == "string":
        return "x"
    if t == "boolean":
        return True
    if t == "number":
        return 1
    return None


async def stub_agent(self, prompt, *, label=None, phase=None, schema=None, **_):
    return synth(schema) if schema else "stub text"


ARGS = {
    "research": "what is X?",
    "sec-review": "def f(): return 1/0",
    "migrate": {"old_api": "old()", "new_api": "new()",
                "files": [{"path": "a.py", "content": "old()"}]},
    "doc-extract": {"docs": [{"id": "d1", "text": "hello"}],
                    "fields": ["title", "summary"]},
    "data-report": {"data": "a,b\n1,2\n3,4", "goal": "trend"},
    "code-feature": {"spec": "add a flag", "files": [{"path": "m.py", "content": "x=1"}]},
    "bug-fix": {"report": "crashes on empty", "code": "def f(xs): return xs[0]"},
}


async def main():
    Harness.agent = stub_agent
    h = Harness()
    ok = 0
    for seed_file in sorted(SEEDS.glob("*.py")):
        name = seed_file.stem
        src = seed_file.read_text(encoding="utf-8")
        try:
            result = await run_script(h, src, ARGS.get(name, {}))
            assert isinstance(result, dict), f"{name}: run() returned {type(result)}, want dict"
            print(f"  ok  {name:<14} -> keys {list(result)}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {name:<14} -> {type(e).__name__}: {e}")
    total = len(list(SEEDS.glob("*.py")))
    print(f"\n{ok}/{total} seeds executed cleanly")
    if ok != total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
