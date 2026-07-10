"""Standalone runtime for policy scripts.

Reimplements the four Claude Code Workflow primitives on the Anthropic SDK so
the *same* evolved scripts run anywhere with an ANTHROPIC_API_KEY:

    agent(prompt, ...)          -> one API call; returns text, or a validated
                                   dict when a JSON `schema` is given (forced tool-use)
    parallel(thunks)            -> asyncio.gather with a concurrency cap; a failed
                                   thunk resolves to None (filter with [x for x in r if x])
    pipeline(items, *stages)    -> each item flows through the stages independently
    log(msg) / phase(title)     -> progress output

A "policy script" is Python source that defines:

    META = {"name": ..., "description": ..., "phases": [...]}   # optional metadata

    async def run(agent, parallel, pipeline, log, phase, args):
        ...
        return <result>

`run_script()` execs that source, injects the primitives, and awaits run().

SECURITY: run_script() exec()s code that may be LLM-authored. Only run trusted
scripts, or inside a container/sandbox. See the SECURITY section of the README.
"""

import asyncio
import json
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from .models import resolve, cost_of, DEFAULT_MODEL

try:
    import jsonschema
except ImportError:  # validation is best-effort; SDK already enforces the tool schema
    jsonschema = None


@dataclass
class Meter:
    in_tok: int = 0
    out_tok: int = 0
    usd: float = 0.0
    calls: int = 0

    def add(self, model_id, usage):
        i = getattr(usage, "input_tokens", 0) or 0
        o = getattr(usage, "output_tokens", 0) or 0
        self.in_tok += i
        self.out_tok += o
        self.usd += cost_of(model_id, i, o)
        self.calls += 1


class Harness:
    """Owns the client, concurrency limit, timeout policy, and the cost meter."""

    def __init__(self, client=None, concurrency=8, default_timeout=180,
                 default_model=DEFAULT_MODEL, verbose=True):
        self.client = client or AsyncAnthropic()
        self.sem = asyncio.Semaphore(concurrency)
        self.timeout = default_timeout
        self.default_model = default_model
        self.verbose = verbose
        self.meter = Meter()

    # ---- primitives -------------------------------------------------------
    async def agent(self, prompt, *, label=None, phase=None, schema=None,
                    model=None, max_tokens=4096, system=None, **_ignored):
        """One model call. Returns str, or a validated dict when schema is given.
        Never raises: on timeout/error it logs and returns None (like the
        Workflow timeout guard) so a fan-out stage is not sunk by one bad call.
        """
        model_id = resolve(model or self.default_model)
        async with self.sem:
            try:
                return await asyncio.wait_for(
                    self._call(prompt, model_id, schema, max_tokens, system),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                self.log(f"timeout: {label or 'agent'}")
                return None
            except Exception as e:  # noqa: BLE001 - deliberate catch-all guard
                self.log(f"error: {label or 'agent'}: {e}")
                return None

    async def _call(self, prompt, model_id, schema, max_tokens, system):
        kwargs = dict(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        if schema:
            kwargs["tools"] = [{
                "name": "respond",
                "description": "Return the answer in the required structure.",
                "input_schema": schema,
            }]
            kwargs["tool_choice"] = {"type": "tool", "name": "respond"}

        resp = await self.client.messages.create(**kwargs)
        self.meter.add(model_id, resp.usage)

        if schema:
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    data = block.input
                    if jsonschema is not None:
                        jsonschema.validate(data, schema)
                    return data
            return None
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "".join(parts).strip()

    async def parallel(self, thunks):
        async def guarded(t):
            try:
                return await t()
            except Exception as e:  # noqa: BLE001
                self.log(f"parallel task failed: {e}")
                return None
        return await asyncio.gather(*[guarded(t) for t in thunks])

    async def pipeline(self, items, *stages):
        async def flow(item, idx):
            cur = item
            for stage in stages:
                try:
                    cur = await stage(cur, item, idx)
                except Exception as e:  # noqa: BLE001
                    self.log(f"pipeline item {idx} dropped: {e}")
                    return None
            return cur
        return await asyncio.gather(*[flow(it, i) for i, it in enumerate(items)])

    def log(self, msg):
        if self.verbose:
            print(f"  · {msg}", flush=True)

    def phase(self, title):
        if self.verbose:
            print(f"\n[{title}]", flush=True)

    # ---- script execution -------------------------------------------------
    def namespace(self, args):
        return {
            "agent": self.agent,
            "parallel": self.parallel,
            "pipeline": self.pipeline,
            "log": self.log,
            "phase": self.phase,
            "args": args,
            "asyncio": asyncio,
            "json": json,
        }


async def run_script(harness, script_src, args=None):
    """Exec a policy script string and await its run(...). Returns run()'s value.

    WARNING: exec()s the given source. Only pass trusted scripts or sandbox it.
    """
    ns = harness.namespace(args)
    exec(compile(script_src, "<policy>", "exec"), ns)  # noqa: S102 - see SECURITY
    run = ns.get("run")
    if run is None:
        raise ValueError("policy script defines no run(...) coroutine")
    return await run(
        ns["agent"], ns["parallel"], ns["pipeline"], ns["log"], ns["phase"], args
    )


def extract_meta(script_src):
    """Best-effort read of a script's module-level META dict (for labels/classify)."""
    ns = {}
    try:
        exec(compile(script_src, "<meta>", "exec"), ns)  # noqa: S102
    except Exception:  # noqa: BLE001
        return {}
    meta = ns.get("META")
    return meta if isinstance(meta, dict) else {}
