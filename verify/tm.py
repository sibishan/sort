"""Reference parser and simulator for the 41080 Turing machine file format.

This file is the canonical definition of the format. The spec sheet is a guide to it.
"""

import argparse
from collections.abc import Iterator
import csv
from dataclasses import dataclass
import io
import os
import sys
import unicodedata

BLANK = "·"
INITIAL, ACCEPT, ERROR = "⎆", "✔", "❗"
RIGHT, LEFT, HALT = "→", "←", "⏹"
DEFAULT_MAX_STEPS = 1_000_000


# --- problems -----------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Problem:
    line: int | None    # None: the problem concerns the whole file
    message: str
    fatal: bool         # fatal: the file is invalid; otherwise reported and repaired

    def __str__(self) -> str:
        kind = "error" if self.fatal else "warning"
        where = "" if self.line is None else f"line {self.line}: "
        return f"{kind}: {where}{self.message}"


class InvalidMachine(Exception):
    def __init__(self, problems: list[Problem]):
        super().__init__("\n".join(map(str, problems)))
        self.problems = problems


def fatal(line: int | None, message: str) -> Problem:
    return Problem(line, message, True)


def recoverable(line: int | None, message: str) -> Problem:
    return Problem(line, message, False)


def any_fatal(problems: list[Problem]) -> bool:
    return any(p.fatal for p in problems)


def in_file_order(problems: list[Problem]) -> list[Problem]:
    return sorted(problems, key=lambda p: (p.line is None, p.line or 0))


# --- data ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Row:
    line: int
    fields: tuple[str, str, str, str, str]


@dataclass(frozen=True, slots=True)
class Rule:
    line: int
    state: str
    symbols: tuple[str, ...]
    move: str
    write: str | None   # None: leave the cell unchanged
    next_state: str


Machine = dict[tuple[str, str], Rule]


# --- character classes --------------------------------------------------------

def is_tape_symbol(c: str) -> bool:
    return len(c) == 1 and c != BLANK and unicodedata.category(c)[0] in "LNPS"


def describe(c: str) -> str:
    return "the blank" if c == BLANK else f"{c!r} (U+{ord(c):04X})"


# --- pass 1: bytes to text ----------------------------------------------------

def decode(data: bytes) -> tuple[str | None, list[Problem]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        line = data[:e.start].count(b"\n") + 1
        return None, [fatal(line, "not valid UTF-8")]
    problems = []
    if text.startswith("\ufeff"):
        problems.append(recoverable(1, "byte-order mark (U+FEFF) at start of file ignored"))
        text = text[1:]
    for n, line in enumerate(io.StringIO(text, newline=""), 1):
        if unicodedata.normalize("NFC", line) != line:
            changed = [c for c in dict.fromkeys(line) if unicodedata.normalize("NFC", c) != c]
            detail = ", ".join(map(describe, changed)) if changed else "a sequence of characters"
            problems.append(fatal(n, f"not in Unicode normal form NFC: {detail} changes under normalisation"))
    return text, problems


# --- pass 2: text to rows -----------------------------------------------------

def split_rows(text: str) -> tuple[list[Row], list[Problem]]:
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t",
                        quoting=csv.QUOTE_NONE, strict=True)
    rows, problems = [], []
    try:
        for fields in reader:
            n = reader.line_num
            if not fields:
                problems.append(recoverable(n, "empty line ignored"))
            elif len(fields) != 5:
                problems.append(fatal(n, f"expected 5 tab-separated fields, found {len(fields)}"))
            else:
                rows.append(Row(n, tuple(fields)))
    except csv.Error as e:
        problems.append(fatal(reader.line_num, f"cannot be read as TSV: {e}"))
    return rows, problems


# --- pass 3: rows to rules ----------------------------------------------------

def symbol_problems(s: str, what: str) -> list[str]:
    """Problems with s as a symbol in a rule: a tape symbol or the blank."""
    if s == "":
        return [f"{what} is empty"]
    if len(s) > 1:
        return [f"{what} {s!r} is {len(s)} characters, not one"]
    if s != BLANK and not is_tape_symbol(s):
        return [f"{what} {describe(s)} is not a tape symbol"]
    return []


def name_problems(s: str, what: str) -> list[str]:
    """Problems with s as a state name, apart from the reserved names."""
    if s == "":
        return [f"{what} is empty"]
    bad = [c for c in dict.fromkeys(s) if not is_tape_symbol(c)]
    if bad:
        verb = "is not a tape symbol" if len(bad) == 1 else "are not tape symbols"
        return [f"{what} {s!r} contains {', '.join(map(describe, bad))}, which {verb}"]
    return []


def current_state_problems(s: str) -> list[str]:
    if s == INITIAL:
        return []
    if s in (ACCEPT, ERROR):
        return [f"current state cannot be {s}"]
    return name_problems(s, "current state")


def current_symbols_problems(s: str) -> list[str]:
    return [m for x in s.split(" ") for m in symbol_problems(x, "current symbol")]


def move_problems(s: str) -> list[str]:
    return [] if s in (RIGHT, LEFT, HALT) else [f"move {s!r} is not {RIGHT}, {LEFT} or {HALT}"]


def next_symbol_problems(s: str) -> list[str]:
    return [] if s == "" else symbol_problems(s, "next symbol")


def next_state_problems(s: str, move: str) -> list[str]:
    if s in (INITIAL, ERROR):
        return [f"next state cannot be {s}"]
    if s == ACCEPT:
        return [f"only a halt ({HALT}) can enter {ACCEPT}"] if move in (RIGHT, LEFT) else []
    return name_problems(s, "next state")


def row_problems(row: Row) -> list[Problem]:
    """Every problem in one row, each column checked on its own."""
    state, symbols, move, write, next_state = row.fields
    messages = (current_state_problems(state)
                + current_symbols_problems(symbols)
                + move_problems(move)
                + next_symbol_problems(write)
                + next_state_problems(next_state, move))
    listed = [x for x in symbols.split(" ") if x]
    repeated = [x for x in dict.fromkeys(listed) if listed.count(x) > 1]
    return ([fatal(row.line, m) for m in messages]
            + [recoverable(row.line, f"current symbol {x!r} listed more than once; extra copies ignored")
               for x in repeated])


def to_rule(row: Row) -> Rule:
    """Convert a row that has no fatal problems."""
    state, symbols, move, write, next_state = row.fields
    return Rule(row.line, state, tuple(dict.fromkeys(symbols.split(" "))),
                move, write or None, next_state)


# --- pass 4: checks across rules ----------------------------------------------

def duplicate_problems(rules: list[Rule]) -> list[Problem]:
    """No two rules may share a current state and current symbol."""
    first, problems = {}, []
    for r in rules:
        for x in r.symbols:
            if (r.state, x) in first:
                problems.append(fatal(r.line, f"rule for ({r.state}, {x}) already defined on line {first[r.state, x]}"))
            else:
                first[r.state, x] = r.line
    return problems


def halting_consistency_problems(rules: list[Rule]) -> list[Problem]:
    """No state may be entered both by a halt and by a move."""
    halted_into, moved_into = {}, {}
    for r in rules:
        (halted_into if r.move == HALT else moved_into).setdefault(r.next_state, r.line)
    return [fatal(None, f"state {s!r} is entered by a halt (line {halted_into[s]}) "
                        f"and by a move (line {moved_into[s]})")
            for s in sorted(halted_into.keys() & moved_into.keys())]


def halting_state_rule_problems(rules: list[Rule]) -> list[Problem]:
    """No rule may have a halting state as its current state."""
    halting = {}
    for r in rules:
        if r.move == HALT:
            halting.setdefault(r.next_state, r.line)
    return [fatal(r.line, f"rule for halting state {r.state!r} (entered by a halt on line {halting[r.state]})")
            for r in rules if r.state in halting]


# --- entry points -------------------------------------------------------------

def parse(data: bytes) -> tuple[Machine, list[Problem]]:
    """Return the machine and its recoverable problems; raise InvalidMachine on any fatal problem."""
    text, problems = decode(data)
    if text is None:
        raise InvalidMachine(problems)

    rows, found = split_rows(text)
    problems += found
    if any_fatal(found):
        raise InvalidMachine(in_file_order(problems))

    rules = []
    for row in rows:
        found = row_problems(row)
        problems += found
        if not any_fatal(found):
            rules.append(to_rule(row))

    # Rows with fatal problems are left out of these checks. Leaving rules out cannot
    # create a duplicate, a halting conflict or a rule for a halting state, so every
    # problem found here is also a problem in the full file.
    problems += duplicate_problems(rules)
    problems += halting_consistency_problems(rules)
    problems += halting_state_rule_problems(rules)

    problems = in_file_order(problems)
    if any_fatal(problems):
        raise InvalidMachine(problems)
    return {(r.state, x): r for r in rules for x in r.symbols}, problems


def load(path: str) -> tuple[Machine, list[Problem]]:
    with open(path, "rb") as f:
        data = f.read()
    return parse(data)


# --- simulation ---------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Config:
    """A configuration. The tape holds every cell up to the head, so tape[head] always exists."""
    state: str
    tape: str
    head: int
    steps: int
    halted: bool


def initial_config(tape: str) -> Config:
    return Config(INITIAL, tape or BLANK, 0, 0, False)


def step(machine: Machine, c: Config) -> Config:
    """Perform one action: count, read, write, update, move."""
    steps = c.steps + 1                                     # count
    rule = machine.get((c.state, c.tape[c.head]))           # read
    if rule is None:
        return Config(ERROR, c.tape, c.head, steps, True)
    tape = c.tape                                           # write
    if rule.write is not None:
        tape = tape[:c.head] + rule.write + tape[c.head + 1:]
    state = rule.next_state                                 # update
    if rule.move == HALT:                                   # move
        return Config(state, tape, c.head, steps, True)
    if rule.move == LEFT:
        if c.head == 0:
            return Config(ERROR, tape, 0, steps, True)
        return Config(state, tape, c.head - 1, steps, False)
    head = c.head + 1
    if head == len(tape):
        tape += BLANK
    return Config(state, tape, head, steps, False)


def trace(machine: Machine, tape: str, max_steps: int = DEFAULT_MAX_STEPS) -> Iterator[Config]:
    """Yield every configuration, starting from the initial one, until a halt or max_steps steps."""
    c = initial_config(tape)
    yield c
    while not c.halted and c.steps < max_steps:
        c = step(machine, c)
        yield c


def run(machine: Machine, tape: str, max_steps: int = DEFAULT_MAX_STEPS) -> Config:
    """Return the last configuration of the trace."""
    for c in trace(machine, tape, max_steps):
        pass
    return c


def tape_string(c: Config) -> str:
    return c.tape.rstrip(BLANK)


# --- printing a trace ---------------------------------------------------------

def display_width(s: str) -> int:
    """Terminal columns taken by s: East Asian wide and fullwidth characters take two."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int) -> str:
    return s + " " * (width - display_width(s))


def state_names(machine: Machine) -> set[str]:
    return {INITIAL, ERROR} | {r.state for r in machine.values()} | {r.next_state for r in machine.values()}


def format_config(c: Config, step_width: int, state_width: int, highlight: bool) -> str:
    """Step, state and tape. The head cell is shown in reverse video if highlight is set;
    otherwise a caret on a second line marks it."""
    prefix = f"{c.steps:>{step_width}}  {pad(c.state, state_width)}  "
    left, cell, right = c.tape[:c.head], c.tape[c.head], c.tape[c.head + 1:]
    if highlight:
        return f"{prefix}{left}\x1b[7m{cell}\x1b[0m{right}"
    return f"{prefix}{c.tape}\n{' ' * (display_width(prefix) + display_width(left))}^"


# --- command line -------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Check a Turing machine file and optionally run it.")
    ap.add_argument("machine", help="machine file (TSV)")
    ap.add_argument("tapes", nargs="*", help="initial tape contents to run the machine on")
    ap.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                    help=f"stop a run after this many steps (default {DEFAULT_MAX_STEPS})")
    ap.add_argument("--trace", action="store_true", help="print every configuration")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")   # some Windows setups default to a legacy encoding

    try:
        machine, problems = load(args.machine)
    except InvalidMachine as e:
        print(f"{args.machine}: invalid", *e.problems, sep="\n  ", file=sys.stderr)
        return 1
    for p in problems:
        print(f"{args.machine}: {p}", file=sys.stderr)
    print(f"{args.machine}: valid, {len(machine)} transitions")

    step_width = len(str(args.max_steps))
    state_width = max(map(display_width, state_names(machine)))
    highlight = sys.stdout.isatty()

    for tape in args.tapes:
        if args.trace:
            print(f"\n{'step':>{step_width}}  {pad('state', state_width)}  tape")
        for c in trace(machine, tape, args.max_steps):
            if args.trace:
                print(format_config(c, step_width, state_width, highlight))
        status = c.state if c.halted else "still running"
        print(f"{tape!r}: {status} after {c.steps} step{'' if c.steps == 1 else 's'}, tape {tape_string(c)!r}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        # The reader closed the output early, as head does. Stop without a traceback.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
