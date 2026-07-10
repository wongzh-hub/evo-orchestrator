"""Model registry + a rough cost table for the token meter.

The runtime is model-agnostic: adding a new model (e.g. a future Fable/Opus)
is one line in MODELS + one in COSTS. Per-role model choice is itself part of
the evolved "weight", so once a model is registered, evolution can start
selecting it for a role.

COSTS are APPROXIMATE USD per 1M tokens (input, output). Verify against current
Anthropic pricing before trusting the dollar figure — the meter is a guide.
"""

# Friendly alias -> Anthropic model ID. Raw IDs are also accepted by resolve().
MODELS = {
    "fable":  "claude-fable-5",
    "opus":   "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
    "haiku":  "claude-haiku-4-5-20251001",
}

# (input_per_mtok, output_per_mtok) in USD. Update to current pricing.
COSTS = {
    "claude-fable-5":             (15.0, 75.0),   # placeholder until published
    "claude-opus-4-8":           (15.0, 75.0),
    "claude-sonnet-4-6":         (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}

DEFAULT_MODEL = "sonnet"


def resolve(name):
    """Alias -> model ID. Unknown names pass through (allows raw IDs)."""
    if not name:
        return MODELS[DEFAULT_MODEL]
    return MODELS.get(name, name)


def cost_of(model_id, in_tok, out_tok):
    ci, co = COSTS.get(model_id, (0.0, 0.0))
    return (in_tok / 1_000_000) * ci + (out_tok / 1_000_000) * co
