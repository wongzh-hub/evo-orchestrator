"""Offline contract test: asserts Harness builds the exact Anthropic messages.create
kwargs (forced tool_use for schema calls), returns the right shapes, and meters calls.
Uses a fake client — no network, no key needed. Runs in CI."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.harness import Harness


class _Usage:
    input_tokens = 10
    output_tokens = 5


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, blocks):
        self.content = blocks
        self.usage = _Usage()


class _Messages:
    def __init__(self):
        self.last = None

    async def create(self, **kwargs):
        self.last = kwargs
        if kwargs.get("tools"):
            return _Resp([_Block(type="tool_use", input={"ok": True})])
        return _Resp([_Block(type="text", text="hello")])


class _FakeClient:
    def __init__(self):
        self.messages = _Messages()


def main():
    fc = _FakeClient()
    h = Harness(client=fc, verbose=False)

    # 1. text call -> str, correct base kwargs, no tools
    r = asyncio.run(h.agent("hi"))
    assert r == "hello", r
    k = fc.messages.last
    assert k["model"] and k["max_tokens"] > 0
    assert k["messages"][0]["role"] == "user" and k["messages"][0]["content"] == "hi"
    assert "tools" not in k

    # 2. schema call -> forced tool_use, returns validated dict
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
    }
    r2 = asyncio.run(h.agent("hi", schema=schema))
    assert isinstance(r2, dict) and r2.get("ok") is True, r2
    k2 = fc.messages.last
    assert k2["tools"][0]["name"] == "respond"
    assert k2["tools"][0]["input_schema"] == schema
    assert k2["tool_choice"] == {"type": "tool", "name": "respond"}

    # 3. meter counted both successful calls; no guarded errors
    assert h.meter.calls == 2, h.meter.calls
    assert h.meter.in_tok == 20 and h.meter.out_tok == 10, (h.meter.in_tok, h.meter.out_tok)
    assert getattr(h, "errors", 0) == 0

    print("PASS harness contract: kwargs shape + forced tool_use + meter + error counter")


if __name__ == "__main__":
    main()
