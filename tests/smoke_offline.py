"""Offline smoke test — exercises the full loop with a STUBBED agent.

No network and no real API key required: it monkeypatches Harness.agent to return
canned structured data, so it verifies the orchestration wiring (seed fork ->
arena climb -> pairwise duel -> promote -> journal) end to end.

    python tests/smoke_offline.py
"""

import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-offline")  # client constructs; never called

from runtime.harness import Harness   # noqa: E402
from evo.loop import run_evo          # noqa: E402

RUN_STUB = ("async def run(agent, parallel, pipeline, log, phase, args):\n"
            "    return {'ok': True}\n")


async def stub_agent(self, prompt, *, label=None, phase=None, schema=None,
                     model=None, max_tokens=4096, system=None, **_):
    """Fake model: a script gains one '# evolved' marker per mutation; the judge
    always favors the script/output carrying more markers -> a deterministic climb."""
    props = set((schema or {}).get("properties", {}).keys())
    if props == {"script"}:                              # mutate / splice
        n = prompt.count("# evolved")
        return {"script": ("# evolved\n" * (n + 1)) + RUN_STUB}
    if "winner" in props:                                # duel (design or output)
        if "--- DESIGN A ---" in prompt:
            a = prompt.split("--- DESIGN A ---")[-1].split("--- DESIGN B ---")[0]
            b = prompt.split("--- DESIGN B ---")[-1]
        else:
            a = prompt.split("OUTPUT A")[-1].split("OUTPUT B")[0]
            b = prompt.split("OUTPUT B")[-1]
        w = "A" if a.count("# evolved") >= b.count("# evolved") else "B"
        return {"winner": w,
                "reasons": [{"dimension": "verification", "favored": w, "note": "stub"}]}
    return "stub text"


async def main():
    Harness.agent = stub_agent
    proj = tempfile.mkdtemp(prefix="evo_smoke_")
    print("project:", proj)

    out = await run_evo(proj, "research", "smoke input",
                        rounds=2, interactive=False, mode="b", do_evo=True)

    pol = json.load(open(os.path.join(proj, "evo", "policy.json"), encoding="utf-8"))
    journal = open(os.path.join(proj, "evo", "journal.md"), encoding="utf-8").read()

    assert out and out.get("promoted"), f"expected a promotion, got {out}"
    assert pol["version"] == 2, f"expected champion v2, got v{pol['version']}"
    assert "# evolved" in pol["script"], "champion script was not updated"
    assert "promoted" in journal, "journal missing promotion line"
    assert not os.path.exists(os.path.join(proj, "evo", "challenger.json")), \
        "challenger.json should be cleared after promotion"

    print(f"PASS  version={pol['version']}  history={len(pol['history'])}  "
          f"journal_lines={journal.count(chr(10))}")


if __name__ == "__main__":
    asyncio.run(main())
