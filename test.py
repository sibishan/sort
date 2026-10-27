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
# TEST CASES
# ---------------------------------------------------------------------------

run_case("[]", "edge case: empty list")
run_case("[3A7F00C29B14E58D]", "edge case: only 1 element in the list")
run_case("[3A7F00C29B14E58D,3A7F00C29B14E58E,F000000000000000]",
         "most steps are spent to compare the first two words, which are equal except for the last digit")
run_case("[3A7F00C29B14E58E,3A7F00C29B14E58D,F000000000000000]",
         "most steps are spent to compare the first two words, which are equal except for the last digit")

run_case("[0000000000000000]", "edge case: single all-zero word")
run_case("[FFFFFFFFFFFFFFFF]", "edge case: single all-F word")
 
# --- Two elements -----------------------------------------------------------
run_case("[0000000000000001,0000000000000002]", "two words, already sorted")
run_case("[0000000000000002,0000000000000001]", "two words, swapped")
run_case("[FFFFFFFFFFFFFFFF,0000000000000000]", "two words, extreme values swapped")
run_case("[3A7F00C29B14E58D,3A7F00C29B14E58D]", "two identical words")
 
# --- Step-count stress: long common prefixes --------------------------------
run_case("[3A7F00C29B14E58D,3A7F00C29B14E58E,F000000000000000]",
         "most steps are spent to compare the first two words, which are equal except for the last digit")
run_case("[3A7F00C29B14E58E,3A7F00C29B14E58D,F000000000000000]",
         "most steps are spent to compare the first two words, which are equal except for the last digit")
run_case("[F000000000000000,3A7F00C29B14E58E,3A7F00C29B14E58D]",
         "long common prefix between the last two words, big word first")
run_case("[3A7F00C29B14E58D,F000000000000000,3A7F00C29B14E58E]",
         "long common prefix between non-adjacent words")
 
# --- Words differing in exactly one position --------------------------------
run_case("[8000000000000000,0000000000000000]", "differ only in the first digit")
run_case("[0000000000000009,000000000000000A]", "last digit crosses the 9/A digit-letter boundary")
run_case("[000000000000000A,0000000000000009]", "last digit crosses the 9/A boundary, swapped")
run_case("[0123456789ABCDEF,0123456789ABCDEE,0123456789ABCDED]",
         "words differ only in the last digit, descending")
run_case("[0123456789ABCDED,0123456789ABCDEE,0123456789ABCDEF]",
         "words differ only in the last digit, already sorted")
run_case("[1000000000000000,0F00000000000000]",
         "first digit decides even though later digits favor the other word")
 
# --- Duplicates -------------------------------------------------------------
run_case("[AAAAAAAAAAAAAAAA,AAAAAAAAAAAAAAAA,AAAAAAAAAAAAAAAA,AAAAAAAAAAAAAAAA]",
         "all words identical")
run_case("[2000000000000000,1000000000000000,2000000000000000,1000000000000000]",
         "two distinct words, each repeated, interleaved")
run_case("[BBBBBBBBBBBBBBBB,0000000000000000,BBBBBBBBBBBBBBBB,0000000000000000,BBBBBBBBBBBBBBBB]",
         "duplicates with a single minimum value repeated")
 
# --- Already sorted / reverse sorted ---------------------------------------
run_case("[0000000000000000,1111111111111111,2222222222222222,3333333333333333,"
         "4444444444444444,5555555555555555,6666666666666666,7777777777777777]",
         "eight words, already sorted")
run_case("[7777777777777777,6666666666666666,5555555555555555,4444444444444444,"
         "3333333333333333,2222222222222222,1111111111111111,0000000000000000]",
         "eight words, reverse sorted")
run_case("[0000000000000000,0000000000000001,0000000000000002,0000000000000003]",
         "consecutive values, already sorted")
run_case("[0000000000000003,0000000000000002,0000000000000001,0000000000000000]",
         "consecutive values, reverse sorted")
 
# --- Realistic / mixed ------------------------------------------------------
run_case("[00000000DEADBEEF,00000000CAFEBABE,0000000000C0FFEE,0000000000000000]",
         "common hex constants with leading zeros")
run_case("[FEDCBA9876543210,0123456789ABCDEF,FFFFFFFFFFFFFFFF,0000000000000000]",
         "all 16 digits ascending vs descending vs extremes")
run_case("[9999999999999999,AAAAAAAAAAAAAAAA,9999999999999998,AAAAAAAAAAAAAAA9]",
         "words straddling the digit-letter boundary")
 
# --- Pseudo-random (fixed seed) ---------------------------------------------
run_case(random_input(2))
run_case(random_input(3))
run_case(random_input(5))
run_case(random_input(8))
run_case(random_input(13))
run_case(random_input(20))
 

