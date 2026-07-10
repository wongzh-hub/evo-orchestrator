"""Pairwise comparison — never absolute rating.

Two candidates are always compared head-to-head, and each comparison is run
TWICE with the positions swapped (A-vs-B then B-vs-A) to cancel position bias.
Per-dimension reasons are returned so the loop can detect a SPLIT (neither side
sweeps) and optionally trigger fusion.

Two flavours:
  duel(...)         - compare two policy SCRIPTS on design/structure (cheap, no run)
  duel_outputs(...) - compare two RESULTS produced by running the scripts (mode c)
"""

DIMENSIONS = [
    "decomposition", "fan_out_sizing", "verification",
    "error_handling", "schema_use", "prompt_quality", "cost_awareness",
]

WIN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "winner": {"type": "string", "enum": ["A", "B"]},
        "reasons": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "dimension": {"type": "string"},
                    "favored": {"type": "string", "enum": ["A", "B"]},
                    "note": {"type": "string"},
                },
                "required": ["dimension", "favored", "note"],
            },
        },
    },
    "required": ["winner", "reasons"],
}

DESIGN_RUBRIC = (
    "Judge multi-agent WORKFLOW DESIGN quality (orchestration structure), not prose.\n"
    "Weigh: task decomposition; right-sized fan-out; verification/adversarial coverage;\n"
    "timeout/error/partial-failure handling; schema use for structured returns;\n"
    "agent-prompt quality; cost-awareness (cheap models for bulk, strong for verify).\n"
    "Penalize anti-patterns: needless barriers, silent truncation, no self-heal,\n"
    "over- or under-engineering for THIS task. Longer is NOT better."
)

OUTPUT_RUBRIC = (
    "Judge OUTPUT quality for the same task: factual correctness, completeness,\n"
    "usefulness, and absence of unsupported claims. Length is not quality."
)


# ---- vote tallying (shared by both duel flavours) -------------------------
def _absorb(res, a_id, b_id, votes, reasons):
    """Fold one judge result into running tallies. In that result, slot 'A'
    corresponds to a_id and slot 'B' to b_id."""
    if not res:
        return
    votes[a_id if res["winner"] == "A" else b_id] += 1
    for x in res.get("reasons", []):
        reasons.append({
            "dimension": x["dimension"],
            "favored": a_id if x["favored"] == "A" else b_id,
            "note": x["note"],
        })


def _decide(a_id, b_id, votes, reasons):
    if votes[a_id] != votes[b_id]:
        return a_id if votes[a_id] > votes[b_id] else b_id
    # tie on votes -> break by count of favored dimensions
    fa = sum(1 for r in reasons if r["favored"] == a_id)
    fb = sum(1 for r in reasons if r["favored"] == b_id)
    return a_id if fa >= fb else b_id


def is_split(reasons, min_minority_share=0.4):
    """SPLIT when the leading side holds < (1 - min_minority_share) of the
    favored dimensions, i.e. the loser still owns a meaningful chunk."""
    if not reasons:
        return False
    counts = {}
    for r in reasons:
        counts[r["favored"]] = counts.get(r["favored"], 0) + 1
    total = sum(counts.values())
    top = max(counts.values())
    return (top / total) < (1 - min_minority_share)


# ---- design duel (scripts) ------------------------------------------------
async def _judge_design(h, brief, a_src, b_src, tag):
    prompt = (
        f"{DESIGN_RUBRIC}\n\nTASK BRIEF:\n{brief}\n\n"
        f"--- DESIGN A ---\n{a_src}\n\n--- DESIGN B ---\n{b_src}\n\n"
        "Pick the better-designed workflow for this brief. Return winner (A/B) and "
        "per-dimension reasons (which side each favors + a one-line note)."
    )
    return await h.agent(prompt, label=f"judge {tag}", phase="Judge",
                         model="opus", schema=WIN_SCHEMA)


async def duel(h, brief, A, B):
    """A, B: {'id', 'script'}. Returns winner/loser id, dimension reasons, split."""
    r1 = await _judge_design(h, brief, A["script"], B["script"], f"{A['id']}|{B['id']}")
    r2 = await _judge_design(h, brief, B["script"], A["script"], f"{B['id']}|{A['id']}")
    votes = {A["id"]: 0, B["id"]: 0}
    reasons = []
    _absorb(r1, A["id"], B["id"], votes, reasons)
    _absorb(r2, B["id"], A["id"], votes, reasons)  # positions swapped in r2
    winner = _decide(A["id"], B["id"], votes, reasons)
    loser = B["id"] if winner == A["id"] else A["id"]
    return {"winner": winner, "loser": loser, "reasons": reasons,
            "split": is_split(reasons), "votes": votes}


# ---- output duel (results) ------------------------------------------------
def _render(out, limit=6000):
    import json as _json
    try:
        return _json.dumps(out, ensure_ascii=False, indent=2)[:limit]
    except Exception:  # noqa: BLE001
        return str(out)[:limit]


async def _judge_output(h, brief, a_out, b_out, tag):
    prompt = (
        f"{OUTPUT_RUBRIC}\n\nTASK BRIEF:\n{brief}\n\n"
        f"--- OUTPUT A ---\n{_render(a_out)}\n\n--- OUTPUT B ---\n{_render(b_out)}\n\n"
        "Pick the better output. Return winner (A/B) and per-dimension reasons."
    )
    return await h.agent(prompt, label=f"judge-out {tag}", phase="Judge",
                         model="opus", schema=WIN_SCHEMA)


async def duel_outputs(h, brief, A, B):
    """A, B: {'id', 'out'}. Compare produced results, order-swapped."""
    r1 = await _judge_output(h, brief, A["out"], B["out"], f"{A['id']}|{B['id']}")
    r2 = await _judge_output(h, brief, B["out"], A["out"], f"{B['id']}|{A['id']}")
    votes = {A["id"]: 0, B["id"]: 0}
    reasons = []
    _absorb(r1, A["id"], B["id"], votes, reasons)
    _absorb(r2, B["id"], A["id"], votes, reasons)
    winner = _decide(A["id"], B["id"], votes, reasons)
    loser = B["id"] if winner == A["id"] else A["id"]
    return {"winner": winner, "loser": loser, "reasons": reasons,
            "split": is_split(reasons), "votes": votes}
