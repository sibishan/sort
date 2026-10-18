import json
import random
import sys
from pathlib import Path

from sim import Machine
from sim.simulator import AMBIGUOUS_ACTION

ROOT = Path(__file__).resolve().parent
MACHINE_FILE = ROOT / "sort.tsv"
OUTPUT_FILE = ROOT / "test.json"
MAX_STEPS = 10_000_000
HEX = "0123456789ABCDEF"

machine = Machine.from_tsv(MACHINE_FILE.read_text(encoding="utf-8"))
results = {}


def trace(text):
    """Step the machine, counting writes (cells whose symbol changed) and cells used."""
    ids = machine.symbol_ids
    tape = {i: ids.get(c, -1) for i, c in enumerate(text)}
    state = head = steps = writes = 0
    max_head = 0
    status = "timeout"
    while steps < MAX_STEPS:
        steps += 1
        read = tape.get(head, 0)
        action = machine.table[state][read] if read >= 0 else None
        if action is None or action is AMBIGUOUS_ACTION:
            status = "errored"
            break
        write, state, move = action
        if write != read:
            tape[head] = write
            writes += 1
        if move == 0:
            status = "accepted" if state == 1 else "rejected"
            break
        if move == -1 and head == 0:
            status = "errored"
            break
        head += move
        max_head = max(max_head, head)
    return {
        "status": status,
        "steps": steps,
        "head": head,
        "writes": writes,
        "space": max(len(text), max_head + 1),
    }


def expected_output(text):
    """The input list with its words sorted; fixed-width uppercase hex sorts as strings."""
    inner = text[1:-1]
    words = inner.split(",") if inner else []
    return "[" + ",".join(sorted(words)) + "]"


def random_input(size):
    """A list of `size` random 16-digit hex words, e.g. run_case(random_input(4))."""
    return "[" + ",".join("".join(random.choice(HEX) for _ in range(16)) for _ in range(size)) + "]"


def run_case(text, comments=""):
    """Run one input, print PASS/FAIL, and save it to test.json as the next test case."""
    t = trace(text)
    with machine.run(text, max_steps=MAX_STEPS) as r:
        final_tape = "".join(r.iter_tokens()).strip(r.blank_symbol)
        sim_view = (r.status, r.steps, r.head_position)
        message = r.message
    if sim_view != (t["status"], t["steps"], t["head"]):
        sys.exit(f"internal mismatch with simulator on {text}: {sim_view} vs {t}")

    key = str(len(results))
    results[key] = {
        "input": text,
        "accepted": t["status"] == "accepted",
        "step count": t["steps"],
        "write complexity": t["writes"],
        "space complexity": t["space"],
        "head position": t["head"],
        "comments": comments,
    }
    OUTPUT_FILE.write_text(json.dumps(results, indent=4, ensure_ascii=False), encoding="utf-8")

    sorted_ok = t["status"] == "accepted" and final_tape == expected_output(text)
    print(f"{'PASS' if sorted_ok else 'FAIL'} #{key}: {t['status']}, {t['steps']} steps, "
          f"{t['writes']} writes, {t['space']} cells, head {t['head']}")
    if not sorted_ok:
        print(f"    input:    {text}\n    expected: {expected_output(text)}\n    got:      {final_tape}")
        if message:
            print(f"    {message}")
    return results[key]


# ---------------------------------------------------------------------------
# !TODO: add more range of test cases
# ---------------------------------------------------------------------------

run_case("[]", "edge case: empty list")
run_case("[3A7F00C29B14E58D]", "edge case: only 1 element in the list")
run_case("[3A7F00C29B14E58D,3A7F00C29B14E58E,F000000000000000]",
         "most steps are spent to compare the first two words, which are equal except for the last digit")
run_case("[3A7F00C29B14E58E,3A7F00C29B14E58D,F000000000000000]",
         "most steps are spent to compare the first two words, which are equal except for the last digit")
run_case(random_input(5))
