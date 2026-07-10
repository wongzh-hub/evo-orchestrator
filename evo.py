#!/usr/bin/env python
"""CLI entry point.  Usage:

    python evo.py <project_dir> --task research --input "your question" --mode b

See `python evo.py --help`.
"""
import asyncio

from evo.loop import run_cli

if __name__ == "__main__":
    asyncio.run(run_cli())
