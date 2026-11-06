import os
import sys

os.environ["LANGSMITH_TRACING"] = "false"  # no traces uploaded for this run

from run_evals import CASES, correct_behavior, no_leak, recipe_format, target

# optional: pick categories, e.g.  uv run python run_local_evals.py cooking pii
wanted = set(sys.argv[1:])
cases = [c for c in CASES if not wanted or c["cat"] in wanted]

totals = {"correct_behavior": [], "no_leak": [], "recipe_format": []}

for c in cases:
    out = target({"question": c["q"]})
    ref = {"expected": c["expected"], "forbidden": c.get("forbidden", [])}
    results = [f(out, ref) for f in (correct_behavior, no_leak, recipe_format)]
    for r in results:
        totals[r["key"]].append(r["score"])
    ok = all(r["score"] == 1 for r in results)
    print(f"[{'PASS' if ok else 'FAIL'}] ({c['cat']}) {c['q'][:60]!r}")
    if not ok:
        print("   status:", out["status"])
        print("   answer:", out["answer"][:200].replace("\n", " "))

print("\nAverages:")
for k, v in totals.items():
    print(f"  {k}: {sum(v) / len(v):.2f}  ({sum(v)}/{len(v)})")