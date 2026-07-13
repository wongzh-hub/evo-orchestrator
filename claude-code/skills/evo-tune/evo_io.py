"""evo-tune IO helper — stores the evolving TEXT policy for a project workflow.

Keeps policy.json (champion), challenger.json, and journal.md under a project's
evo/ directory. Scripts are passed via FILES (not argv) to avoid length limits.

CLI:
  python evo_io.py init   <evodir> <champion_script_file> [name]
  python evo_io.py get    <evodir> champion|challenger          # prints script to stdout
  python evo_io.py set-challenger <evodir> <script_file>
  python evo_io.py promote <evodir>                             # challenger -> champion, version++
  python evo_io.py log    <evodir> "<message>"
  python evo_io.py status <evodir>
"""
import sys
import json
import os
import datetime


def ppath(d): return os.path.join(d, "policy.json")
def cpath(d): return os.path.join(d, "challenger.json")
def jpath(d): return os.path.join(d, "journal.md")
def load(p): return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
def save(p, o): open(p, "w", encoding="utf-8").write(json.dumps(o, ensure_ascii=False, indent=1))
def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def main():
    if len(sys.argv) < 3:
        print("usage: evo_io.py {init|get|set-challenger|promote|log|status} <evodir> [...]")
        sys.exit(2)
    cmd, d = sys.argv[1], sys.argv[2]
    os.makedirs(d, exist_ok=True)
    if cmd == "init":
        script = open(sys.argv[3], encoding="utf-8").read()
        name = sys.argv[4] if len(sys.argv) > 4 else os.path.basename(os.path.abspath(os.path.join(d, "..")))
        save(ppath(d), {"name": name, "version": 1, "champion": script, "created": now(), "history": []})
        open(jpath(d), "a", encoding="utf-8").write(
            f"# evo journal - {name}\n\n- {now()} v1 init champion ({len(script)} chars)\n")
        print("init v1", name)
    elif cmd == "get":
        which = sys.argv[3] if len(sys.argv) > 3 else ""
        if which not in ("champion", "challenger"):
            print("get: which must be 'champion' or 'challenger'")
            sys.exit(2)
        o = load(ppath(d) if which == "champion" else cpath(d))
        if not o:
            sys.exit(2)
        sys.stdout.write(o["champion"] if which == "champion" else o["script"])
    elif cmd == "set-challenger":
        script = open(sys.argv[3], encoding="utf-8").read()
        pol = load(ppath(d)) or {"version": 0}
        save(cpath(d), {"from_version": pol.get("version"), "script": script, "created": now()})
        print("challenger set from v", pol.get("version"))
    elif cmd == "promote":
        pol, ch = load(ppath(d)), load(cpath(d))
        if not pol:
            print("no policy.json to promote into (init first)")
            sys.exit(2)
        if not ch:
            print("no challenger")
            sys.exit(2)
        pol["version"] += 1
        pol["champion"] = ch["script"]
        pol.setdefault("history", []).append({"ts": now(), "event": "promote", "to_version": pol["version"]})
        save(ppath(d), pol)
        os.remove(cpath(d))
        print("promoted to v", pol["version"])
    elif cmd == "log":
        pol = load(ppath(d)) or {"version": "?"}
        open(jpath(d), "a", encoding="utf-8").write(f"- {now()} v{pol.get('version')} {sys.argv[3]}\n")
        print("logged")
    elif cmd == "status":
        pol, ch = load(ppath(d)), load(cpath(d))
        print("champion v", (pol.get("version") if pol else None), "| challenger:", ("yes" if ch else "no"))
        for h in (pol.get("history", []) if pol else [])[-5:]:
            print("  ", h)
    else:
        print("unknown cmd", cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()
