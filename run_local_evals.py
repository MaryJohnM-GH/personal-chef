import os
import sys
import time
from datetime import datetime

os.environ["LANGSMITH_TRACING"] = "false"  # no traces uploaded for this run

from run_evals import CASES, correct_behavior, no_leak, recipe_format, target
from judges import judge_answer, CRITERIA

# optional: pick categories, e.g.  uv run python run_local_evals.py cooking pii
wanted = set(sys.argv[1:])
cases = [c for c in CASES if not wanted or c["cat"] in wanted]

JUDGED_CATEGORIES = {"recipe", "cooking"}  # only these get quality scores

totals = {"correct_behavior": [], "no_leak": [], "recipe_format": []}
judge_totals = {k: [] for k in CRITERIA}
judge_errors = 0

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

    # LLM-as-a-judge: only for real answers to recipe/cooking cases
    if c["cat"] in JUDGED_CATEGORIES and out["status"].startswith(("ok", "modified")):
        j = judge_answer(c["q"], out["answer"])
        if j["judge_error"]:
            judge_errors += 1
            print("   judge: ERROR (not scored)")
        else:
            for k in CRITERIA:
                judge_totals[k].append(j[k])
            scores = " ".join(f"{k}={j[k]}" for k in CRITERIA)
            print(f"   judge: {scores} | {j['reason']}")
        time.sleep(4)  # stay inside Groq free-tier limits

lines = ["Averages:"]
for k, v in totals.items():
    if v:
        lines.append(f"  {k}: {sum(v) / len(v):.2f}  ({sum(v)}/{len(v)})")
for k, v in judge_totals.items():
    if v:
        lines.append(f"  judge_{k}: {sum(v) / len(v):.2f}  (n={len(v)})")
if judge_errors:
    lines.append(f"  judge errors (not scored): {judge_errors}")

summary = "\n".join(lines)
print("\n" + summary)

# append to the score history file
with open("eval_results.txt", "a", encoding="utf-8") as f:
    cats = " ".join(sorted(wanted)) or "all"
    f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M} | categories: {cats} ---\n")
    f.write(summary + "\n")