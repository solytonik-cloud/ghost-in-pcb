"""Сверяет цепи из нетлиста KiCad с задуманными в скрипте схемы.

    python check_nets.py make_schematic.py net.net
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
script, netfile = sys.argv[1], sys.argv[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

txt = Path(netfile).read_text(encoding="utf-8")
got = []
for blk in re.split(r"\(net\s*\(code", txt[txt.find("(nets"):])[1:]:
    name = re.search(r'\(name "([^"]*)"', blk).group(1)
    nodes = {f"{a}.{b}" for a, b in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', blk) if not a.startswith("#")}
    if nodes:
        got.append((name, frozenset(nodes)))

src = Path(script).read_text(encoding="utf-8").split("# ---------- Провода")[0]
ns = {"__file__": str(Path(script).resolve())}
exec(src, ns)
want = {k: frozenset(v) for k, v in ns["s"].nets.items()}
gotsets = {v for _, v in got}
bad = [k for k, v in want.items() if v not in gotsets]
print(f"цепей задумано: {len(want)}, в KiCad: {len(got)}, расхождений: {len(bad)}")
for k in bad:
    print(" ", k, sorted(want[k]))
    print("    в KiCad:", [(n, sorted(v)) for n, v in got if v & want[k]])
sys.exit(1 if bad or len(got) != len(want) else 0)
