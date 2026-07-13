"""Per-project evo state.

Lives at <project>/evo/:
  policy.json      - the champion (the current text "weight") + version + history
  challenger.json  - the mutation/fusion currently under test
  journal.md       - human-readable run log (mode, outcome, feedback, cost)

The champion "weight" is a Python policy-script string (see runtime.harness).
"""

import json
import os
import shutil
from pathlib import Path


def _read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _write_json(p, obj):
    """Atomic write: dump to a temp file in the same dir, fsync, then os.replace().
    Prevents a half-written policy.json (e.g. on a Drive-synced target) from
    bricking the project on the next read."""
    p = Path(p)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


class EvoStore:
    def __init__(self, evo_dir):
        self.dir = Path(evo_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.policy_path = self.dir / "policy.json"
        self.chal_path = self.dir / "challenger.json"
        self.journal_path = self.dir / "journal.md"

    # ---- champion ----
    def exists(self):
        return self.policy_path.exists()

    def init(self, seed_path, name, task_type):
        script = Path(seed_path).read_text(encoding="utf-8")
        _write_json(self.policy_path, {
            "name": name,
            "task_type": task_type,
            "version": 1,
            "script": script,
            "history": [],
        })
        return self.policy()

    def policy(self):
        try:
            return _read_json(self.policy_path)
        except (json.JSONDecodeError, ValueError, OSError) as e:
            bak = self.policy_path.with_name(self.policy_path.name + ".bak")
            if bak.exists():
                print(f"  · WARNING: policy.json unreadable ({e}); restoring from {bak.name}")
                data = _read_json(bak)
                _write_json(self.policy_path, data)
                return data
            raise

    def champion_script(self):
        return self.policy()["script"]

    def promote(self, script, origin, stamp):
        pol = self.policy()
        if self.policy_path.exists():  # keep a rollback of the previous champion weight
            shutil.copy2(self.policy_path,
                         self.policy_path.with_name(self.policy_path.name + ".bak"))
        pol["history"].append({
            "version": pol["version"], "origin": origin, "ts": stamp,
        })
        pol["version"] += 1
        pol["script"] = script
        _write_json(self.policy_path, pol)
        self.clear_challenger()
        return pol["version"]

    # ---- challenger ----
    def challenger(self):
        return _read_json(self.chal_path) if self.chal_path.exists() else None

    def set_challenger(self, script, origin):
        _write_json(self.chal_path, {"script": script, "origin": origin})

    def clear_challenger(self):
        if self.chal_path.exists():
            self.chal_path.unlink()

    # ---- journal ----
    def journal_tail(self, n=5):
        if not self.journal_path.exists():
            return ""
        lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[-n:])

    def log(self, line, stamp):
        new = not self.journal_path.exists()
        with self.journal_path.open("a", encoding="utf-8") as f:
            if new:
                f.write("# evo journal\n\n")
            f.write(f"- **{stamp}** — {line}\n")
