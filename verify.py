import json
import sys

sys.path.insert(0, "verify")
import tm

try:
    machine, warnings = tm.load("sort.tsv")
except tm.InvalidMachine as e:
    print("sort.tsv: invalid", *e.problems, sep="\n  ")
    sys.exit(1)
for w in warnings:
    print(f"sort.tsv: {w}")
print(f"sort.tsv: valid, {len(machine)} transitions")

with open("test.json") as f:
    cases = json.load(f)

failed = 0
for n, case in cases.items():
    tape = case["input"]
    words = tape[1:-1].split(",") if tape != "[]" else []
    expected = "[" + ",".join(sorted(words)) + "]"
    final = tm.run(machine, tape)
    ok = final.state == tm.ACCEPT and tm.tape_string(final) == expected
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'} #{n}: {final.state} after {final.steps} steps")
    if not ok:
        print(f"  expected {expected!r}\n  got      {tm.tape_string(final)!r}")

print(f"\n{len(cases) - failed}/{len(cases)} passed")
sys.exit(1 if failed else 0)

"""
OUTPUT
sort.tsv: valid, 3597 transitions
PASS #0: ✔ after 3 steps
PASS #1: ✔ after 35 steps
PASS #2: ✔ after 35 steps
PASS #3: ✔ after 35 steps
PASS #4: ✔ after 715 steps
PASS #5: ✔ after 1325 steps
PASS #6: ✔ after 815 steps
PASS #7: ✔ after 749 steps
PASS #8: ✔ after 885 steps
PASS #9: ✔ after 2141 steps
PASS #10: ✔ after 2851 steps
PASS #11: ✔ after 1631 steps
PASS #12: ✔ after 815 steps
PASS #13: ✔ after 715 steps
PASS #14: ✔ after 1325 steps
PASS #15: ✔ after 3871 steps
PASS #16: ✔ after 1395 steps
PASS #17: ✔ after 815 steps
PASS #18: ✔ after 2177 steps
PASS #19: ✔ after 3871 steps
PASS #20: ✔ after 5401 steps
PASS #21: ✔ after 1225 steps
PASS #22: ✔ after 2075 steps
PASS #23: ✔ after 21161 steps
PASS #24: ✔ after 7673 steps
PASS #25: ✔ after 6313 steps
PASS #26: ✔ after 3461 steps
PASS #27: ✔ after 4313 steps
PASS #28: ✔ after 205 steps
PASS #29: ✔ after 375 steps
PASS #30: ✔ after 2615 steps
PASS #31: ✔ after 16891 steps
PASS #32: ✔ after 33489 steps
PASS #33: ✔ after 81425 steps

34/34 passed
"""