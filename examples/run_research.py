"""Minimal end-to-end example: evolve + run the `research` seed.

Requires ANTHROPIC_API_KEY (put it in a .env at the repo root, or export it).
Non-interactive, design-judge mode (cheap). First run forks the seed to a v1
champion under examples/demo_project/evo/, evolves it, and may promote a winner.

    python examples/run_research.py
"""

import asyncio
import os
import sys

# make the repo root importable when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from evo.loop import run_evo


async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("set ANTHROPIC_API_KEY (see .env.example)")
    await run_evo(
        project_dir="./examples/demo_project",
        task_type="research",
        task_input="What are the tradeoffs of vector databases vs. keyword search for RAG?",
        rounds=2,
        interactive=False,
        mode="b",       # design-judge (cheap); use "c" to compare real outputs
        do_evo=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
